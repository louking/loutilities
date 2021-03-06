#!/usr/bin/python
###########################################################################################
#   config - configuration constants
#
#   Date        Author      Reason
#   ----        ------      ------
#   01/21/13    Lou King    Create
#   03/20/14    Lou King    Adapted from runningclub
#
#   Copyright 2013 Lou King
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
###########################################################################################
'''
config - configuration constants
================================================================================
'''

# standard
import os.path

# pypi
import appdirs

# github

# other

# home grown

# general purpose exceptions
class accessError(Exception): pass
class parameterError(Exception): pass
class dbConsistencyError(Exception): pass
class softwareError(Exception): pass

# configuration location for running scripts
CONFIGDIR = appdirs.user_data_dir('loutilities','Lou King')
if not os.path.exists(CONFIGDIR): os.makedirs(CONFIGDIR)

