#!/usr/bin/python
"""Harry's webapp-virtualenvifier

This program attempts to "virtualenv-ify" an existing Python project, by:
- scanning its source tree for imports
- creating a virtualenv in its project root
- pip installing any detected dependencies into the virtualenv
- modifying the file at /var/www/wsgi.py to activate the virtualenv

Usage:
    virtualenvify <target_directory> [--update-wsgi]
                                     [--always-copy-local]
                                     [--fake]
    virtualenvify -h | --help

Options:
    -h --help            show this screen
    --fake               preview only, do not write anything to disk.
                         [default: False]
    --update-wsgi        for web apps, update /var/www/wsgi.py with
                         virtualenv activation code [default: False]
    --always-copy-local  always copy locally installed version of
                         packages [default: False]

"""

from datetime import datetime
from distutils import sysconfig
from docopt import docopt
import imp
from pip.commands import freeze
import os
from StringIO import StringIO
import re
import shutil
import sys
import subprocess
from textwrap import dedent

class NoSuchPackageException(Exception):
    pass


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
    """
    Manually parse source code for "from x import ..." or "import x, y" type lines
    Lots of special-casing, may be best to actually parse the code using ast
    some day
    """
    modules = set()
    line_continuation = '\\\n'
    source_code = source_code.replace(line_continuation, '')
    for line in source_code.split('\n'):
        line = line.split('#')[0].split(';')[0]

        if line.startswith('from') and 'import' in line:
            main_package = line.split()[1].split('.')[0]
            modules.add(main_package)
            debug_modules[main_package] = line

        elif line.startswith('import'):
            if line.startswith('import,'):
                continue
            words = FIND_WORDS.findall(line)
            if len(words) > 2 and ',' not in line:
                continue
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
                with open(os.path.join(top, filename), 'U') as f:
                    imports |= get_imports(f.read())
    return imports - std_lib - user_modules


def build_virtualenv(target_directory, fake):
    commands = ['virtualenv', '--no-site-packages', target_directory ]
    if fake:
        print 'Virtualenv command-line would be:'
        print ' '.join(commands)
    else:
        print 'Building virtualenv in', target_directory
        subprocess.check_call(commands)


def copy_package_from_existing_install(package_name, target_directory):
    #TODO: improve this to catch anything in /usr/local/bin
    _, installed_location, __ = imp.find_module(package_name)
    venv_site_packages = os.path.join(
        target_directory, 'lib', 'python2.7', 'site-packages'
    )
    if os.path.isdir(installed_location):
        dest = os.path.join(venv_site_packages, package_name)
        print 'copying from', installed_location, 'to', dest
        shutil.copytree(installed_location, dest)
    else:
        dest = os.path.join(venv_site_packages, os.path.basename(installed_location))
        print 'copying from', installed_location, 'to', dest
        shutil.copy(installed_location, dest)



def pip_install_package(package_name, target_directory, copy_local=False):
    if copy_local:
        copy_package_from_existing_install(package_name, target_directory)
        return 'copied from existing installation'

    p = subprocess.Popen(
        [
            os.path.join(target_directory, 'bin', 'pip'),
            'install', package_name
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    p.wait()
    stdout = p.stdout.read()

    msg_success = "Successfully installed %s" % package_name
    msg_not_found = "No distributions at all found for %s" % package_name
    msg_compile_failure = "error: command 'gcc' failed with exit status 1"
    if msg_success in stdout:
        print stdout
        return 'installed successfully'
    if msg_not_found in stdout:
        print stdout
        return 'could not install'
    if msg_compile_failure in stdout:
        print 'This package requires compilation. Attempting to copy existing version'
        copy_package_from_existing_install(package_name, target_directory)
        return 'copied from existing installation'


def install_packages(packages, target_directory, copy_local):
    print 'Installing dependencies into virtualenv'
    report = 'Package installation report:\n'
    for package in packages:
        response = pip_install_package(package, target_directory, copy_local)
        report += "%s: %s\n" % (package, response)
    return report


def update_wsgi(target_directory, fake):
    full_path = os.path.abspath(target_directory)
    activate_path = os.path.join(full_path, 'bin', 'activate_this.py')
    activation_code = dedent(
        """
        # This activates the virtualenv for your web app
        activate_this = %r
        execfile(activate_this, dict(__file__=activate_this))
        """ % (activate_path,)
    )
    with open('/var/www/wsgi.py') as f:
        old_contents = f.read()

    if old_contents.startswith(activation_code):
        print 'activation code already found in WSGI file'
        return

    new_contents = activation_code + old_contents
    if fake:
        print 'new wsgi file contents would be:'
        print new_contents
        return

    print 'backing up old wsgi file'
    timestamp = datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
    shutil.copy(
        '/var/www/wsgi.py',
        '/var/www/wsgi.py.%s.bak' % (timestamp,)
    )
    print 'updating wsgi file'
    with open('/var/www/wsgi.py', 'w') as f:
        f.write(new_contents)
    print 'wsgi file updated to:'
    print new_contents



def main(args):
    target_directory = args['<target_directory>']
    imported_packages = get_imported_packages(target_directory)
    print "The following external package import have been detected:"
    print "\n".join(imported_packages)

    build_virtualenv(target_directory, args['--fake'])

    report = None
    if not args['--fake']:
        report = install_packages(
            imported_packages, target_directory,
            args['--always-copy-local']
        )

    if args['--update-wsgi']:
        update_wsgi(target_directory, args['--fake'])

    if report is not None:
        print report


if __name__ == '__main__':
    args = docopt(__doc__)
    main(args)


