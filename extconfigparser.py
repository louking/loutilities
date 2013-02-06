#!/usr/bin/python
###########################################################################################
#   extconfigparser - extend ConfigParser.RawConfigParser option interpretation
#
#   Date        Author      Reason
#   ----        ------      ------
#   12/29/12    Lou King    Create
#
#   Copyright 2012 Lou King
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
extconfigparser - extend ConfigParser.RawConfigParser option interpretation
=============================================================================
'''

# standard
import pdb
import argparse
import ConfigParser

# pypi

# github

# home grown
import version

########################################################################
class ExtConfigParser(ConfigParser.RawConfigParser):
########################################################################
    '''
    extend :class:`ConfigParser.RawConfigParser` to allow list and dict values
    
    :params params: see http://docs.python.org/2/library/configparser.html#rawconfigparser-objects
    '''

    #----------------------------------------------------------------------
    def get(self,section,option):
    #----------------------------------------------------------------------
        '''
        Get and option value for the named section.
        Try to interpret as int, float, boolean, list, or dict
        '''
        
        value = ConfigParser.RawConfigParser.get(self,section,option)
        
        # if possible list, dict or number, try to evaluate
        if rval[0] in '[{.' + string.digits:
            try:
                rval = eval(value)
        
            # couldn't make sense of it, just return a string and let the caller deal with it
            except SyntaxError:
                rval = value
        
        else:
            rval = value
            
        return rval
                
