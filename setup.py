#!/usr/bin/env python

from distutils.core import setup

setup(
    name='virtualenvify',
    version='0.1.0',
    description='Transform an existing Python project into a virtualenv',
    author='Harry Percival',
    author_email='hjwp2@cantab.net',
    url='https://github.com/hjwp/virtualenvify',
    download_url='https://github.com/hjwp/virtualenvify/raw/master/dist/virtualenvify-0.1.0.zip',
    packages=[],
    scripts=['virtualenvify.py'],
    requires=['docopt', 'virtualenv',],
    classifiers= [
        'Environment :: Console',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
    ],
)

