"""Harry's webapp-virtualenvifier

Usage:
    virtualenvify <target_directory>
"""
from distutils import sysconfig
from docopt import docopt
import imp
from pip.commands import freeze
import os
from StringIO import StringIO
import re
import sys
import subprocess
from textwrap import dedent
from unittest import TestCase
FIND_WORDS = re.compile(r'\w+')

def get_batteries_included():
    old_stdout = sys.stdout
    try:
        sys.stdout = StringIO()
        fc = freeze.FreezeCommand()
        fc.run(*fc.parser.parse_args([]))
        return sys.stdout.getvalue().split('\n')
    finally:
        sys.stdout = old_stdout


def get_standard_library():
    python_dir = sysconfig.get_python_lib(standard_lib=True)
    std_lib = []
    std_lib += [path.split('.')[0] for path in os.listdir(python_dir) if path.endswith('.py')]
    def is_module_directory(path):
        full_path = os.path.join(python_dir, path)
        return os.path.isdir(full_path) and '__init__.py' in os.listdir(full_path)
    std_lib += [path for path in os.listdir(python_dir) if is_module_directory(path)]
    std_lib += sys.builtin_module_names
    return std_lib


def get_imports(source_code):
    modules = set()
    import_lines = [l for l in source_code.split('\n') if l.startswith('import') or l.startswith('from')]
    for line in import_lines:
        words = FIND_WORDS.findall(line)
        if words[0] == 'from':
            modules.add(words[1])
        else:
            modules.update(words[1:])
    return modules


def get_imported_packages(target_directory):
    std_lib = set(get_standard_library())
    imports = set()
    user_modules = set()
    for top, dirs, files in os.walk(target_directory):
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


    def test_get_imported_packages(self):
        import matplotlib
        packages = get_imported_packages(os.path.dirname(matplotlib.__file__))
        self.assertNotIn(',', ''.join(packages))
        self.assertNotIn(';', ''.join(packages))
        for p in packages:
            f, pathname, desc = imp.find_module(p)
            self.assertIn('site-packages', pathname)

