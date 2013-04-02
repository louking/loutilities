#!/usr/bin/python
###########################################################################################
#   apikey - manage api keys for a given package
#
#   Date        Author      Reason
#   ----        ------      ------
#   04/01/13    Lou King    Create
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
apikey - manage api keys for a given package
===================================================
'''

# standard
import pdb
import argparse
import os
import os.path
import ConfigParser
import tempfile

# pypi
import appdirs

# github

# other

# home grown
import version
from loutilities import *

class unknownKey(Exception): pass

########################################################################
class ApiKey():
########################################################################
    '''
    base class for API key management
    result of object creation is a apikeys.cfg file with an [apikeys] section, possibly empty
    
    keys are stored in the following locations
    * Windows: C:\\Users\\<username>\\AppData\\Local\\<author>\\<appname>\\apikeys.cfg
    * Linux: /home/<username>/.config/<appname>/apikeys.cfg
    * Mac OS X: /Users/<username>/Library/Application Support/<appname>/apikeys.cfg
    
    use :meth:`addkey` to add a key, :meth:`getkey` to retrieve a key
    
    :param author: author of software for which keys are being managed
    :param appname: application name for which keys are being managed
    '''
    
    keyssection = 'apikeys'
    
    #----------------------------------------------------------------------
    def __init__(self,author,appname):
    #----------------------------------------------------------------------
        '''
        '''

        configdir = appdirs.user_data_dir(appname,author)
        if not os.path.exists(configdir):
            os.makedirs(configdir)
        self.fname = os.path.join(configdir,'apikeys.cfg')
        if not os.path.exists(self.fname):
            # maybe something bad happened in the middle of an updatekey operation
            # if so, try to recover
            if os.path.exists(self.fname+'.save'):
                os.rename(self.fname+'.save',self.fname)
            # otherwise, create the empty file
            else:
                touch = open(self.fname,'w')
                touch.close()
                
        # pull in all the existing keys
        self.cp = ConfigParser.ConfigParser()
        self.cp.read(self.fname)
        
        # create the section storing the keys if necessary
        if not self.cp.has_section(self.keyssection):
            self.cp.add_section(self.keyssection)
        
    #----------------------------------------------------------------------
    def getkey(self,keyname):
    #----------------------------------------------------------------------
        '''
        return the key indicated by keyname
        if key doesn't exist, unknownKey is raised
        
        :param keyname: name of key for later retrieval
        '''
        try:
            return self.cp.get(self.keyssection,keyname)
        
        except ConfigParser.NoOptionError:
            raise unknownKey
        
    #----------------------------------------------------------------------
    def updatekey(self,keyname,keyvalue):
    #----------------------------------------------------------------------
        '''
        update or add a key to key file
        
        :param keyname: name of key for later retrieval
        :param keyvalue: value of key
        '''
        
        # write all the keys to a temporary file
        self.cp.set(self.keyssection,keyname,keyvalue)
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
        
#----------------------------------------------------------------------
def main():
#----------------------------------------------------------------------
    '''
    add key to key file
    '''

    parser = argparse.ArgumentParser(version='{0} {1}'.format('loutilities',version.__version__))
    parser.add_argument('application',help='name of application for which keys are to be stored')
    parser.add_argument('keyname',help='name of key to create/update in key configuration file')
    parser.add_argument('keyvalue',help='value of key to be put into key configuration file')
    parser.add_argument('-a','--author',help='name of software author. (default %(default)s)',default='Lou King')
    args = parser.parse_args()
    
    # act on arguments
    application = args.application
    author = args.author
    keyname = args.keyname
    keyvalue = args.keyvalue
    
    apikey = ApiKey(author,application)
    apikey.updatekey(keyname,keyvalue)
    

# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()

