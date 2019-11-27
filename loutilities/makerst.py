#!/usr/bin/python
###########################################################################################
#   makerst - make a bunch of autodoc rst files
#
#   Date        Author      Reason
#   ----        ------      ------
#   03/25/13    Lou King    Create
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
makerst - make a bunch of autodoc rst files
===================================================
'''

# standard
import os.path
import glob

# pypi

# github

# other

# home grown

#----------------------------------------------------------------------
def main():
#----------------------------------------------------------------------
    '''
    make a bunch of autodoc rst files
    '''
    
    srcpath = './doc/source'
    if not os.path.exists(srcpath):
        srcpath = './doc'
        if not os.path.exists(srcpath):
            print('Could not find ./doc/source or ./doc.  Exiting')
            return
    
    # keep track of files created
    created = []
    
    # for each python file, create an rst file, if one doesn't already exist
    for f in glob.glob('*.py'):
        modname = os.path.splitext(f)[0]
        if modname in ['__init__','setup','version']: continue
        
        rstfname = '.'.join([modname,'rst'])
        fullrstpath = os.path.join(srcpath,rstfname)
        if os.path.exists(fullrstpath): continue
        
        RST = open(fullrstpath,'w')
        RST.write('.. automodule:: {0}\n'.format(modname))
        RST.write('    :members:\n')
        RST.close()
        

################################################################################
################################################################################
if __name__ == "__main__":
    main()
