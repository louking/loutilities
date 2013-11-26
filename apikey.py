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

# pypi
import appdirs

# github

# other

# home grown
import version
import extconfigparser
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
        configfname = 'apikeys.cfg'
        self.cf = extconfigparser.ConfigFile(configdir,configfname)
        
    #----------------------------------------------------------------------
    def getkey(self,keyname):
    #----------------------------------------------------------------------
        '''
        return the key indicated by keyname
        if key doesn't exist, unknownKey is raised
        
        :param keyname: name of key for later retrieval
        :rtype: value of key
        '''
        try:
            return self.cf.get(self.keyssection,keyname)
        
        except extconfigparser.unknownSection:
            raise unknownKey
        
        except extconfigparser.unknownOption:
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
        self.cf.update(self.keyssection,keyname,keyvalue)
        
    #----------------------------------------------------------------------
    def list(self):
    #----------------------------------------------------------------------
        '''
        Return a list of (keyname, value) pairs for each option in the given section.
        
        :rtype: [(keyname,value),...]
        '''
        return self.cf.items(self.keyssection)
        
#----------------------------------------------------------------------
def main():
#----------------------------------------------------------------------
    '''
    add key to key file
    '''

    parser = argparse.ArgumentParser(version='{0} {1}'.format('loutilities',version.__version__))
    parser.add_argument('application',help='name of application for which keys are to be stored')
    parser.add_argument('keyname',help='name of key to create/update in key configuration file',nargs='?',default=None)
    parser.add_argument('keyvalue',help='value of key to be put into key configuration file',nargs='?',default=None)
    parser.add_argument('-a','--author',help='name of software author. (default %(default)s)',default='Lou King')
    parser.add_argument('-l','--list',action='store_true',help='print list of keyname,values.  If set, keyname, value arguments are ignored')
    args = parser.parse_args()
    
    # act on arguments
    application = args.application
    author = args.author
    keyname = args.keyname
    keyvalue = args.keyvalue
    plist = args.list
    
    if not plist and not(keyname and keyvalue):
        print 'KEYNAME and VALUE must be supplied'
        return
    
    apikey = ApiKey(author,application)

    if not plist:
        apikey.updatekey(keyname,keyvalue)
        
    else:
        for keyname,value in apikey.list():
            print '{}={}'.format(keyname,value)
    

# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()

