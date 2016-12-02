#!/usr/bin/env python

from os import path
from setuptools import setup

# Get the long description from the README file
with open(
        path.join(path.abspath(path.dirname(__file__)),
                  'README.org'),
        encoding='utf-8') as f:
    long_description = f.read()

setup(name="carp",
      version="0.1",
      description="EncFS CLI managing tool",
      long_description=long_description,
      author="Étienne Deparis",
      author_email="etienne@depar.is",
      license="WTFPL",
      url="https://projects.depar.is/carp",
      packages=['carp'],
      classifiers=[
          "Development Status :: 3 - Alpha",
          "Environment :: Console",
          "Intended Audience :: End Users/Desktop",
          "Intended Audience :: System Administrators",
          "License :: What The F*** Public License (WTFPL)",
          "Programming Language :: Python :: 3"
      ],
      keywords="encfs")
