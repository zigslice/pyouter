#!/usr/bin/env python

from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(name="pyouter",
      version="0.1.1",
      description="Python command line tasks router",
      long_description=long_description,
      long_description_content_type='text/markdown',
      author="Fan Fei Long, Liu xin",
      author_email="fanfeilong@gmail.com",
      url="https://github.com/fanfeilong/pyouter",
      license="MIT",
      classifiers=[
          "Topic :: Utilities",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3 :: Only",
          "License :: OSI Approved :: MIT License"
      ]
      )
