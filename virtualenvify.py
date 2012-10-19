"""Harry's webapp-virtualenvifier

Usage:
    virtualenvify <target_directory>
"""
from distutils import sysconfig
from docopt import docopt
import imp
from pip.commands import freeze
from pprint import pprint
import os
from StringIO import StringIO
import re
import sys
import subprocess
from textwrap import dedent
from unittest import TestCase


def get_batteries_included():
    old_stdout, old_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = StringIO()
        fc = freeze.FreezeCommand()
        fc.run(*fc.parser.parse_args([]))
        return sys.stdout.getvalue().split('\n')
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


def get_standard_library():
    python_dir = sysconfig.get_python_lib(standard_lib=True)
    file_modules = [path.split('.')[0] for path in os.listdir(python_dir) if path.endswith('.py')]
    def is_module_directory(path):
        full_path = os.path.join(python_dir, path)
        return os.path.isdir(full_path) and '__init__.py' in os.listdir(full_path)
    directory_modules = [path for path in os.listdir(python_dir) if is_module_directory(path)]
    other_directories = [p for p in sys.path if p.startswith(python_dir) and 'site-packages' not in p]
    other_modules = []
    for directory in other_directories:
        if os.path.isdir(directory):
            other_modules += [f[:-3] for f in os.listdir(directory) if f.endswith('.py') or f.endswith('.so')]
    return file_modules + directory_modules + other_modules + list(sys.builtin_module_names)


debug_modules = {}
FIND_WORDS = re.compile(r'[^ ,]+')
def get_imports(source_code):
    modules = set()
    for line in source_code.replace('\\\n', '').split('\n'):
        line = line.split('#')[0].split(';')[0]

        if line.startswith('from') and 'import' in line:
            main_package = line.split()[1].split('.')[0]
            modules.add(main_package)
            debug_modules[main_package] = line

        elif line.startswith('import'):
            words = FIND_WORDS.findall(line)
            words = [w.split('.')[0] for w in words]
            while 'as' in words:
                as_position = words.index('as')
                modules.add(words[as_position - 1])
                debug_modules[words[as_position - 1]] = line
                words.pop(as_position + 1)
                words.pop(as_position)
                words.pop(as_position - 1)

            modules.update(words[1:])
            for w in words[1:]:
                debug_modules[w] = line
    return modules


def get_imported_packages(target_directory):
    std_lib = set(get_standard_library())
    imports = set()
    user_modules = set()
    for top, dirs, files in os.walk(target_directory):
        if '__init__.py' in files:
            user_modules.add(os.path.basename(top))
        for filename in files:
            if filename.endswith('.py'):
                user_modules.add(filename[:-3])
                with open(os.path.join(top, filename)) as f:
                    imports |= get_imports(f.read())

    return imports - std_lib - user_modules


def main(target_directory):
    imported_packages = get_imported_packages(target_directory)
    print "The following external package import have been detected:"
    print "\n".join(imported_packages)
    print "I will try and install these into your virtualenv"
    print debug_modules


if __name__ == '__main__':
    args = docopt(__doc__)
    main(args['<target_directory>'])

class VirtualenvifyTests(TestCase):

    def test_get_batteries_included(self):
        batteries = get_batteries_included()
        command_line_output = subprocess.check_output(['pip', 'freeze'])
        self.assertEqual(command_line_output.split('\n'), batteries)

    def test_get_standard_libary(self):
        stdlib = get_standard_library()
        self.assertIn('random', stdlib)
        self.assertIn('sys', stdlib)
        self.assertIn('unittest', stdlib)
        self.assertIn('cStringIO', stdlib)
        self.assertIn('CDROM', stdlib)
        self.assertIn('Tkinter', stdlib)

    def test_get_imports(self):
        self.assertItemsEqual(get_imports(dedent(
            """
            import foo
            pass
            """)),
            ['foo']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            #do something else here
            def someone():
                return 2
            import foo
            print someone()
            import bar
            pass
            """)),
            ['foo', 'bar']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            from baz import foo
            pass
            """)),
            ['baz']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import os, sys
            pass
            """)),
            ['os', 'sys']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import os,sys
            pass
            """)),
            ['os', 'sys']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import folsom.prison
            from orange.blossom import special
            pass
            """)),
            ['folsom', 'orange']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            from jimminy import os,sys
            pass
            """)),
            ['jimminy']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            from somewhere import (
                a, b, c
                d,e,
                f
            )
            pass
            """)),
            ['somewhere']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import notacomment # comments go here
            pass
            """)),
            ['notacomment']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import things_before_a_semicolon; who = uses + these + anyway?
            pass
            """)),
            ['things_before_a_semicolon']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            ''' a multiline coment taken
            from a real-life test
            in which the word from occurs randomly in a line
            """)),
            []
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import something.somewhere as something_else, edgecase, annoying as rename
            pass
            """)),
            ['something', 'edgecase', 'annoying']
        )

        self.assertItemsEqual(get_imports(dedent(
            """
            import many, things, \\
                    on, multiple, lines
            pass
            """)),
            ['many', 'things', 'on', 'multiple', 'lines']
        )


    def test_get_imported_packages(self):
        import matplotlib
        packages = get_imported_packages(os.path.dirname(matplotlib.__file__))
        pprint(debug_modules)
        self.assertNotIn(',', ''.join(packages))
        self.assertNotIn(';', ''.join(packages))
        self.assertNotIn('\\', ''.join(packages))
        for p in packages:
            if p not in ('PyObjCTools', 'Foundation', 'AppKit', 'fltk', 'gtk', 'gobject', 'pango', '_tkagg', 'wx'): # not installed
                f, pathname, desc = imp.find_module(p)
                self.assertIn('site-packages', pathname)
                self.assertNotIn('matplotlib', pathname)

