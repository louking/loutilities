#!/usr/bin/python
###########################################################################################
#   extconfigparser - extended configuration handling
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
extconfigparser - extended configuration handling
=============================================================================

extend ConfigParser.ConfigParser option interpretation
provide ConfigFile high level configuration file handling

'''

# standard
import pdb
import argparse
from ConfigParser import ConfigParser,NoOptionError
import string

# pypi

# github

# home grown
import version

class unknownOption(Exception): pass

#----------------------------------------------------------------------
def _parsevalue(self,value):
#----------------------------------------------------------------------
    '''
    try to interpret value as dict, list or number
    '''
    if value[0] in '[{.' + string.digits:
        try:
            rval = eval(value)
    
        # couldn't make sense of it, just return a string and let the caller deal with it
        except SyntaxError:
            rval = value
    
    else:
        rval = value
        
    return rval
    
########################################################################
class ExtConfigParser(ConfigParser):
########################################################################
    '''
    extend :class:`ConfigParser.ConfigParser` to allow list and dict values
    
    :params params: see http://docs.python.org/2/library/configparser.html#configparser-objects
    '''

    #----------------------------------------------------------------------
    def get(self,section,option,**kwargs):
    #----------------------------------------------------------------------
        '''
        Get an option value for the named section. If vars is provided, it must be a dictionary. The option is looked up in vars (if provided), section, and in defaults in that order.

        All the '%' interpolations are expanded in the return values, unless the raw argument is true. Values for interpolation keys are looked up in the same manner as the option.

        Try to interpret value as int, float, boolean, list, or dict
        '''
        
        value = ConfigParser.get(self,section,option,**kwargs)
        
        # if possible list, dict or number, try to evaluate
        return _parsevalue(value)
    
    #----------------------------------------------------------------------
    def items(self,section,**kwargs):
    #----------------------------------------------------------------------
        '''
        Return a list of (name, value) pairs for each option in the given section. Optional arguments have the same meaning as for the get() method.
        
        Try to interpret values as int, float, boolean, list, or dict
        '''
        retlist = []
        for name,value in ConfigParser.items(self,section,**kwargs):
            rval = (name,_parsevalue(value))
            retlist.append(rval)
            
        return retlist

########################################################################
class ConfigFile():
########################################################################
    '''
    configuration file handler
    result of object creation is a named configuration file, possibly empty
    
    use :meth:`update` to add or update a config option, :meth:`get` to retrieve a config option
    
    :param configdir: where configuration file is to be stored
    :param configfname: filename for configuration file
    '''
    
    #----------------------------------------------------------------------
    def __init__(self,configdir,configfile):
    #----------------------------------------------------------------------
        '''
        '''

        if not os.path.exists(configdir):
            os.makedirs(configdir)
        self.fname = os.path.join(configdir,configfname)
        if not os.path.exists(self.fname):
            # maybe something bad happened in the middle of an update operation
            # if so, try to recover
            if os.path.exists(self.fname+'.save'):
                os.rename(self.fname+'.save',self.fname)
            # otherwise, create the empty file
            else:
                touch = open(self.fname,'w')
                touch.close()
                
        # pull in all the existing keys
        self.cp = ConfigParser()
        self.cp.read(self.fname)
        
        # create the section storing the keys if necessary
        if not self.cp.has_section(self.keyssection):
            self.cp.add_section(self.keyssection)
        
    #----------------------------------------------------------------------
    def get(self,section,option):
    #----------------------------------------------------------------------
        '''
        return the value of the option indicated by option
        if option doesn't exist, unknownOption is raised
        
        :param section: section within which option should be found
        :param option: name of option for later retrieval
        '''
        try:
            return self.cp.get(section,keyname)
        
        except NoOptionError:
            raise unknownOption
        
    #----------------------------------------------------------------------
    def update(self,section,option,value):
    #----------------------------------------------------------------------
        '''
        update or add an option to a configuration file
        
        :param section: section within which option should be updated
        :param option: name of option to be updated or created
        :param value: value of option
        '''
        
        # if section doesn't exist yet, create it
        if not self.cp.has_section(section):
            self.cp.add_section(section)
            
        # write all the keys to a temporary file
        self.cp.set(section,option,value)
        temp = tempfile.NamedTemporaryFile(delete=False)
        self.cp.write(temp)
        tempname = temp.name
        temp.close()
        
        # on windows, atomic rename to existing file causes error, so the old file is saved first
        # if crash occurs in the middle of this, at least the old information isn't lost
        # .save file will be recovered the next time the ApiKey object is created
        os.rename(self.fname,self.fname+'.save')
        os.rename(tempname,self.fname)
        os.remove(self.fname+'.save')