#!/usr/bin/python
###########################################################################################
#   filtercsv - filter a csv file based on indicated filter
#
#   Date        Author      Reason
#   ----        ------      ------
#   05/08/13    Lou King    Create
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
filtercsv - filter a csv file based on indicated filter
===============================================================

Usage::

    TBA
                            
    
'''

# standard
import argparse
import csv
import textwrap
import json
import sys

# pypi

# github

# other

# home grown
from . import version

class invalidParameter(Exception): pass

#----------------------------------------------------------------------
def main():
#----------------------------------------------------------------------
    '''
    filter standard input to standard output
    '''
    descr = textwrap.dedent('''\
            reads stdin and applies FILTER argument to produce stdout
    
            FILTER is a string representing a dict or list of dicts.
            
            The keys of each dict are column headers for which all of the values
            of the dict must be matched for the filter to pass a row in the input
            file (AND function)
            
            If the filter needs to test that a value of the filter and the row NOT
            match, TBD
            
            if a list of dicts is provided, the row passes if any of the dicts match
            (OR function)
            ''')
    parser = argparse.ArgumentParser(prog='filtercsv',
                                     description=descr,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     version='{0} {1}'.format('loutilities',version.__version__))
    parser.add_argument('filter',help='list of dicts or single dict. All items within dict must match for any dict in the list to pass filter')
    args = parser.parse_args()
    
    # convert stdout to binary mode if on windows
    if sys.platform == "win32":
        import os, msvcrt
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    # normalize filter to list of dicts
    #print 'FILTER={}'.format(args.filter)
    filt = json.loads(args.filter)
    if not isinstance(filt, list):
        filt = [filt]
    for f in filt:
        if not isinstance(f, dict):
            raise invalidParameter('FILTER must be dict or list of dicts')
    
    # get the header line, which is always sent to the output file
    hdr = next(sys.stdin)
    sys.stdout.write(hdr)

    # use csv to get a list of the hdr, to handle any errant commas
    H = csv.reader([hdr])
    hdrlist = next(H)
    
    # parse the rest of stdin as a DictReader, stdout as DictWriter
    IN = csv.DictReader(sys.stdin,fieldnames=hdrlist)
    OUT = csv.DictWriter(sys.stdout,hdrlist)
    
    # for each input line, check against all the filters
    for line in IN:
        for f in filt:
            # hope for the best
            match = True
            
            # AND function -- all within dict must match
            for col in list(f.keys()):
                if f[col] != line[col]:
                    match = False
                    break
            
            # OR function -- match found within any of the dicts means pass through the filter
            if match:
                break
        
        # if match found, send to output
        if match:
            OUT.writerow(line)
            
    # clean up
    sys.stdin.close()
    sys.stdout.close()
    
# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()

