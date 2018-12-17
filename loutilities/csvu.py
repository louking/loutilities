#!/usr/bin/python
###########################################################################################
#   csvu - csv and string utilities
#
#   Date        Author      Reason
#   ----        ------      ------
#   11/25/13    Lou King    Create
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

# standard
import unicodedata
import csv

# pypi
#from IPython.core.debugger import Tracer; debug_here = Tracer()

# github

# other

# home grown

#----------------------------------------------------------------------
def unicode2ascii(ustr):
#----------------------------------------------------------------------
    '''
    convert non-ascii unicode characters to ascii
    
    :param ustr: unicode or str
    :rtype: str
    '''
    if type(ustr) == str:
        return ustr
    else:
        return unicodedata.normalize('NFKD',ustr).encode('ascii','ignore')

#----------------------------------------------------------------------
def str2num(ustr):
#----------------------------------------------------------------------
    '''
    convert string to float, number, ascii
    
    :param ustr: unicode or str
    :rtype: int, float or str as appropriate, or None if ustr was None
    '''
    if ustr is None:
        return None
    
    try:
        return int(ustr)
    except ValueError:
        try:
            return float(ustr)
        except ValueError:
            return unicode2ascii(ustr).strip()

#######################################################################
class DictReaderStr2Num(csv.DictReader):
#######################################################################
    '''
    extend csv.DictReader to convert strings to numbers 
    '''

    #----------------------------------------------------------------------
    def next(self):
    #----------------------------------------------------------------------
        row = csv.DictReader.next(self)
        for key in row:
            row[key] = str2num(row[key])
        return row
        

