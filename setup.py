#!/usr/bin/python

# Copyright 2012 Lou King
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import glob
import pdb

# home grown
from loutilities import version

from setuptools import setup, find_packages

setup(
    name = "loutilities",
    version = version.__version__,
    packages = find_packages(),
#    include_package_data = True,
    scripts = [
        'loutilities/agegrade.py',
        'loutilities/apikey.py',
        'loutilities/applytemplate.py',
        'loutilities/filtercsv.py',
        'loutilities/makerst.py',
    ],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires = [
          # 'unicodecsv>=0.13.0',
        ],

    # include data files as appropriate
    package_data={
        '': [
            'tables-assets/static/*',
            'tables-assets/static/user/*',
            'tables-assets/static/user/admin/*',
            'tables-assets/templates/*',
            'tables-assets/templates/security/*',
            'tables-assets/templates/security/email/*',
            '*.csv',
        ],
    },

    entry_points = {
        'console_scripts': [
            'agegrade = loutilities.agegrade:main',
            'apikey = loutilities.apikey:main',
            'applytemplate = loutilities.applytemplate:main',
            'filtercsv = loutilities.filtercsv:main',
            'makerst = loutilities.makerst:main',
        ],
    },


    zip_safe = False,

    # metadata for upload to PyPI
    description = 'some hopefully useful utilities',
    long_description=open("README.md").read(),
    license = 'Apache License, Version 2.0',
    author = 'Lou King',
    author_email = 'lking@pobox.com',
    url = 'http://github.com/louking/loutilities',
    # could also include long_description, download_url, classifiers, etc.
)

