Virtualenvify
=============

A script to build a virtualenv for an existing project, auto-detecting package
imports and installing them into the env

This program attempts to "virtualenv-ify" an existing Python project, by:
- scanning its source tree for imports
- creating a virtualenv in its project root
- pip installing any detected dependencies into the virtualenv
- modifying the file at /var/www/wsgi.py to activate the virtualenv

Usage:
    virtualenvify <target_directory> [--no-wsgi] [--fake]
    virtualenvify -h | --help

Options:
    -h --help   show this screen
    --fake      preview changes only, do not write anything to disk. [default: False]
    --no-wsgi   for non-web-apps, do not touch wsgi.py. [default: False]


