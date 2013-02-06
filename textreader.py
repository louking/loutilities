#!/usr/bin/python
###########################################################################################
#   textreader - read text out of various file types
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
textreader - read text out of various file types
===================================================
'''

# standard
import pdb
import argparse

# pypi
import xlrd
import docx

# github

# home grown
import version
from loutilities import *

VALIDFTYPES = ['xls','xlsx','docx','txt']
DOCXTABSIZE = 8
TXTABSIZE = 8

########################################################################
class TextReader():
########################################################################
    '''
    abstract text reader for several different file types
    creation of object opens TextReader file
    
    :param filename: name of file to open
    '''

    #----------------------------------------------------------------------
    def __init__(self,filename):
    #----------------------------------------------------------------------
        """
        open TextReader file
        
        :param filename: name of file to open
        """
        self.ftype = filename.split('.')[-1] # get extension
        if self.ftype not in VALIDFTYPES:
            raise parameterError, 'Invalid filename {0}: must have extension in {1}'.format(filename,VALIDFTYPES)
        
        # handle excel files
        if self.ftype in ['xls','xlsx']:
            self.workbook = xlrd.open_workbook(filename)
            self.sheet = self.workbook.sheet_by_index(0)    # only first sheet is considered
            self.currrow = 0
            self.nrows = self.sheet.nrows
            self.delimited = True               # rows are already broken into columns
            self.workbook.release_resources()   # sheet is already loaded so we can save memory
            
        # handle word files
        elif self.ftype in ['docx']:
            doc = docx.opendocx(filename)
            self.lines = iter(docx.getdocumenttext(doc))
            self.delimited = False
            
        # handle txt files
        elif self.ftype in ['txt']:
            self.TXT = open(filename,'r')
            self.delimited = False
            
        self.delimiters = None
        self.opened = True
        
    #----------------------------------------------------------------------
    def next(self):
    #----------------------------------------------------------------------
        """
        read next line from TextReader file
        raises StopIteration when end of file reached
        
        :rtype: list of cells for the current row
        """
        
        # check if it is ok to read
        if not self.opened:
            raise ValueError, 'I/O operation on a closed file'
        
        # handle excel files
        if self.ftype in ['xls','xlsx']:
            if self.currrow >= self.nrows:
                raise StopIteration
            
            row = self.sheet.row_values(self.currrow)
            self.currrow += 1
            return row
        
        # handle word files
        elif self.ftype in ['docx']:
            line = next(self.lines)
            line = line.expandtabs(DOCXTABSIZE)
            if self.delimiters:
                splitline = self.delimit(line)
                return splitline
            else:
                return line

        # handle txt files
        elif self.ftype in ['txt']:
            line = next(self.TXT)
            line = line.expandtabs(TXTABSIZE)
            if self.delimiters:
                splitline = self.delimit(line)
                return splitline
            else:
                return line

    #----------------------------------------------------------------------
    def close(self):
    #----------------------------------------------------------------------
        """
        close TextReader file
        """
        
        self.opened = False
        
        # handle excel files
        if self.ftype in ['xls','xlsx']:
            pass    # resources have already been released
        
        # handle word files
        elif self.ftype in ['docx']:
            pass    # nothing going on here, either
        
        # handle txt files
        elif self.ftype in ['txt']:
            self.TXT.close()
        

    #----------------------------------------------------------------------
    def getdelimited(self):
    #----------------------------------------------------------------------
        """
        return state whether file is delimited
        
        :rtype: True if delimited
        """
        
        return self.delimited       

    #----------------------------------------------------------------------
    def setdelimiter(self,delimiters):
    #----------------------------------------------------------------------
        """
        set delimiters for file as specified in delimiters
        
        :param delimiters: list of character positions to set delimiters at
        """
        
        # do some validation
        if self.delimited:
            raise parameterError, 'cannot set delimiters for file which is already delimited'
        if type(delimiters) != list:
            raise parameterError, 'delimiters must be a list of increasing integers'
        lastdelimiter = -1
        for delimiter in delimiters:
            if type(delimiter) != int or delimiter <= lastdelimiter:
                raise parameterError, 'delimiters must be a list of increasing integers'
            lastdelimiter = delimiter
            
        self.delimiters = delimiters
        self.delimited = True
        
    #----------------------------------------------------------------------
    def delimit(self,s):
    #----------------------------------------------------------------------
        """
        split a string based on delimiters
        
        :param s: string to be split
        :rtype: list of string elements, stripped of white space
        """
        
        if not self.delimiters:
            raise parameterError, 'cannot split string if delimiters not set'
        
        rval = []
        for i in range(len(self.delimiters)):
            start = self.delimiters[i]
            end = self.delimiters[i+1] if i+1 < len(self.delimiters) else None   # last one goes to end of s
            rval.append(s[start:end].strip())
            
        return rval
            
################################################################################
def main():
################################################################################

    parser = argparse.ArgumentParser(version='{0} {1}'.format('running',version.__version__))
    parser.add_argument('filename',help='name of file for testing')
    #parser.add_argument('--nowuaccess',help='use option to inhibit wunderground access using apikey',action="store_true")
    #parser.add_argument('-l','--loglevel',help='set logging level (default=%(default)s)',default='WARNING')
    #parser.add_argument('-o','--logfile',help='logging output file (default=stdout)',default=sys.stdout)
    args = parser.parse_args()
    
    # act on arguments
    filename = args.filename
    
    # open file, print some lines, then close
    ff = TextReader(filename)
    for i in range(6):
        print(ff.readline())
    ff.close()

# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()

