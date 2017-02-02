#!/usr/bin/env python

import re
from os import path
from setuptools import setup

# Get the long description from the README file
with open(path.join(path.abspath(path.dirname(__file__)),
                    "README.md"),
          encoding="utf-8") as f:
    long_description = f.read()

with open(path.join(path.abspath(path.dirname(__file__)),
                    "carp", "version.py"),
          encoding="utf-8") as f:
    version_content = f.read()

version_match = re.search(r"VERSION = \"(\d(?:\.\d)*)\"", version_content)
version_number = "dev"
if version_match:
    version_number = version_number[1]

setup(name="carp",
      version=version_number,
      description="EncFS managing libs",
      long_description=long_description,
      author="Étienne Deparis",
      author_email="etienne@depar.is",
      license="WTFPL",
      url="https://projects.depar.is/carp",
      packages=["carp"],
      classifiers=[
          "Development Status :: 3 - Alpha",
          "Environment :: Console",
          "Intended Audience :: End Users/Desktop",
          "Intended Audience :: System Administrators",
          "License :: What The F*** Public License (WTFPL)",
          "Programming Language :: Python :: 3"
      ],
      keywords="encfs")
