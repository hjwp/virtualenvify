
import imp
import os
from pprint import pprint
import shutil
import subprocess
import tempfile
from textwrap import dedent
import unittest

from virtualenvify import (
        NoSuchPackageException,
        build_virtualenv,
        debug_modules,
        get_batteries_included,
        get_standard_library,
        get_imports,
        get_imported_packages,
        install_packages,
        pip_install_package,
)

class PackageInstallingTests(unittest.TestCase):

    @classmethod
    def setUpClass(self):
        self.tempdir = tempfile.mkdtemp()
        build_virtualenv(self.tempdir, fake=False)

    @classmethod
    def tearDownClass(self):
        shutil.rmtree(self.tempdir)


    def test_pip_install_package_for_known_package(self):
        response = pip_install_package('virtualenvify', self.tempdir)
        self.assertIn(
            'virtualenvify.py',
            os.listdir(os.path.join(self.tempdir, 'bin'))
        )
        self.assertEqual(response, 'installed successfully')


    def test_pip_install_package_for_unknown_package(self):
        response = pip_install_package('doesnotexist', self.tempdir)
        self.assertNotIn(
            'doesnotexist',
            os.listdir(os.path.join(self.tempdir, 'bin'))
        )
        self.assertEqual(response, 'could not install')


    def test_pip_install_package_for_compilation_required_falls_back_to_copying_our_version(self):
        response = pip_install_package('fiona', self.tempdir)
        self.assertIn(
            'fiona',
            os.listdir(
                os.path.join(self.tempdir, 'lib', 'python2.7', 'site-packages')
            )
        )
        self.assertEqual(response, 'copied from existing installation')
        _, path_to_our_version, __ = imp.find_module('fiona')
        for filename in os.listdir(path_to_our_version):
            if filename.endswith('.py') or filename.endswith('.so'):
                self.assertTrue(os.path.exists(
                    os.path.join(self.tempdir, 'lib', 'python2.7', 'site-packages', 'fiona', filename)
                ))


    def test_install_packages_does_them_sequentially_catches_errors_and_returns_report(self):
        report = install_packages(['aafigure', 'doesnotexist', 'psutil'], self.tempdir)
        self.assertEqual(report,
                'Package installation report:\n'
                'aafigure: installed successfully\n'
                'doesnotexist: could not install\n'
                'psutil: copied from existing installation\n'
        )



class ImportFindingTests(unittest.TestCase):

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


    def test_get_imported_packages(self):
        try:
            _, path_to_matplotlib, __ = imp.find_module('matplotlib')
        except ImportError:
            raise Warning('Could not import Matplotlib - unable to run this test')
        packages = get_imported_packages(path_to_matplotlib)
        #pprint(debug_modules)
        self.assertNotIn(',', ''.join(packages))
        self.assertNotIn(';', ''.join(packages))
        self.assertNotIn('\\', ''.join(packages))
        self.assertNotIn('sys', packages)
        for p in packages:
            if p not in ('PyObjCTools', 'Foundation', 'AppKit', 'fltk', 'gtk', 'gobject', 'pango', '_tkagg', 'wx'): # not installed
                f, pathname, desc = imp.find_module(p)
                self.assertIn('site-packages', pathname)
                self.assertNotIn('matplotlib', pathname)


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
            and also, annoyingly, the word
            import occurs on a line
            possibly with a comma, as in
            import, stuff
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


if __name__ == '__main__':
    unittest.main()
