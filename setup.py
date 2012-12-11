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

import ez_setup
import glob
import pdb

# home grown
import version

ez_setup.use_setuptools()
from setuptools import setup, find_packages

def globit(dir, filelist):
    outfiles = []
    for file in filelist:
        filepath = '{0}/{1}'.format(dir,file)
        gfilepath = glob.glob(filepath)
        for i in range(len(gfilepath)):
            f = gfilepath[i][len(dir)+1:]
            gfilepath[i] = '{0}/{1}'.format(dir,f)  # if on windows, need to replace backslash with frontslash
            outfiles += [gfilepath[i]]
    return (dir, outfiles)

setup(
    name = "loutilities",
    version = version.__version__,
    packages = find_packages(),
#    include_package_data = True,
    scripts = [
    ],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires = [
##        'wx>=2.9.4',
        ],

    # If any package contains any of these file types, include them:
    data_files = ([
        ]),


    entry_points = {
        'console_scripts': [
        ],
    },


    zip_safe = False,

    # metadata for upload to PyPI
    description = 'some hopefully useful utilities',
    license = 'Apache License, Version 2.0',
    author = 'Lou King',
    author_email = 'lking@pobox.com',
    url = 'http://github.com/louking/loutilities',
    # could also include long_description, download_url, classifiers, etc.
)

