#!/usr/bin/env python3

from distutils.core import setup

setup(name='butterfly_bot',
      version='0.1.0',
      description="Library for building butterfly's discord chat bots",
      author='Lina Edwards',
      author_email='lina@butterflysky.dev',
      packages=['butterfly_bot'],
      install_requires=[
          'openai>=0.10.2',
      ]
      )
