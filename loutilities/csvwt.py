#!/usr/bin/python
###########################################################################################
#   csvwt - write csv from various file types
#
#   Date        Author      Reason
#   ----        ------      ------
#   02/07/13    Lou King    Create
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
csvwt - write csv from various file types
===================================================
'''

# standard
import pdb
import argparse
import tempfile
import collections
import os
from collections import OrderedDict
import csv

# pypi
import xlrd
import unicodecsv   # standard csv does not handle unicode data

# github

# other
from sqlalchemy.orm import class_mapper # see http://www.sqlalchemy.org/ written with 0.8.0b2

# home grown
import version
from loutilities import *

class invalidParameter(Exception): pass

########################################################################
class _objdict(dict):
########################################################################
    '''
    subclass dict to make it work like an object

    see http://goodcode.io/articles/python-dict-object/
    '''
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("No such attribute: " + name)

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        if name in self:
            del self[name]
        else:
            raise AttributeError("No such attribute: " + name)

#----------------------------------------------------------------------
def record2csv(inrecs, mapping, outfile=None): 
#----------------------------------------------------------------------
    '''
    convert list of dict or object records to a csv list or file based on a specified mapping
    
    :param inrecs: list of dicts or objects
    :param mapping: OrderedDict {'outfield1':'infield1', 'outfield2':outfunction(inrec), ...} or ['inoutfield1', 'inoutfield2', ...]
    :param outfile: optional output file
    :rtype: lines from output file
    '''

    # analyze mapping for outfields
    if type(mapping) == list:
        mappingtype = list
    elif type(mapping) in [dict, OrderedDict]:
        mappingtype = dict
    else:
        raise invalidParameter(
            "invalid mapping type {}. mapping type must be list, dict or OrderedDict").with_traceback(
            format(type(mapping)))

    outfields = []
    for outfield in mapping:
        invalue = mapping[outfield] if mappingtype==dict else outfield

        if type(invalue) not in [str,unicode] and not callable(invalue):
            raise invalidParameter('invalid mapping {}. mapping values must be str or function'.format(outvalue))

        outfields.append(outfield)

    # create writeable list, csv file
    outreclist = wlist()
    coutreclist = csv.DictWriter(outreclist, outfields)
    coutreclist.writeheader()

    for inrec in inrecs:
        # convert to object if necessary
        if type(inrec) == dict:
            inrec = _objdict(inrec)

        outrow = {}
        for outfield in mapping:
            infield = mapping[outfield] if mappingtype==dict else outfield
            if type(infield) == str:
                outvalue = getattr(inrec, infield, None)

            else:
                # a function call is requested
                outvalue = infield(inrec)

            outrow[outfield] = outvalue
        
        coutreclist.writerow(outrow)

    # write file if desired
    if outfile:
        with open(outfile,'wb') as out:
            out.writelines(outreclist)

    return outreclist

########################################################################
class Base2Csv():
########################################################################
    '''
    base class for any file to csv conversion
    
    :param outdir: directory to put output file(s) -- if None, temporary directory is used
    '''
    
    #----------------------------------------------------------------------
    def __init__(self,filename,outdir=None,hdrmap=None):
    #----------------------------------------------------------------------
        '''
        '''

        self.tempdir = False
        if outdir is None:
            self.tempdir = True
            outdir = tempfile.mkdtemp(prefix='csvwt-')
        self.dir = outdir
        
        self.files = collections.OrderedDict()
        
    #----------------------------------------------------------------------
    def __del__(self):
    #----------------------------------------------------------------------
        '''
        release resources
        '''

        if self.tempdir:
            for name in self.files:
                os.remove(self.files[name])
            os.rmdir(self.dir)
            
    #----------------------------------------------------------------------
    def getfiles(self):
    #----------------------------------------------------------------------
        '''
        get sheetnames and file pathnames produced
        
        :rtype: OrderedDict{sheet:pathname,...}
        '''
        
        return self.files

########################################################################
class Xls2Csv(Base2Csv):
########################################################################
    '''
    create csv file(s) from xlsx (or xls) sheets
    
    :param filename: name of file to convert
    :param outdir: directory to put output file(s) -- if None, temporary directory is used
    :param hdrmap: maps input header to csv header -- if None, input header is used as csv header
    '''

    #----------------------------------------------------------------------
    def __init__(self,filename,outdir=None,hdrmap=None):
    #----------------------------------------------------------------------
        '''
        '''
        
        # create outdir if necessary, self.out, self.files
        Base2Csv.__init__(self,outdir)
        
        # go through each sheet, and save as csv file
        # from http://www.gossamer-threads.com/lists/python/python/833610
        wb = xlrd.open_workbook(filename) 
        for name in wb.sheet_names(): 
            sheet = wb.sheet_by_name(name) 
            if sheet.nrows == 0: continue   # skip empty sheets
            
            # get header
            inhdr = sheet.row_values(0)
            if hdrmap is not None:
                # NOTE: this has the effect of filtering input columns
                outhdr = [hdrmap[k] for k in hdrmap]
            else:
                hdrmap = dict(zip(inhdr,inhdr))
                outhdr = inhdr
                
            # create output csv file and write header
            self.files[name] = '{0}/{1}.csv'.format(self.dir,name)
            OUT = open(self.files[name], 'wb')
            writer = unicodecsv.DictWriter(OUT,outhdr)
            writer.writeheader()
            
            # copy all the rows in the original sheet to the csv file
            for row in xrange(1,sheet.nrows):
                inrow = dict(zip(inhdr,sheet.row_values(row)))
                outrow = {}
                for incol in inhdr:
                    if incol in hdrmap:
                        outrow[hdrmap[incol]] = inrow[incol]
                writer.writerow(outrow)
            
            # we're done with this sheet
            OUT.close()
        
        # and done with the workbook
        wb.release_resources()
        
########################################################################
class Db2Csv(Base2Csv):
########################################################################
    '''
    create csv file(s) from db tables
        
    :param outdir: directory to put output file(s) -- if None, temporary directory is used
    '''

    #----------------------------------------------------------------------
    def __init__(self,outdir=None):
    #----------------------------------------------------------------------
        '''
        '''
        
        # create outdir if necessary, self.out, self.files
        Base2Csv.__init__(self,outdir)
        
    #----------------------------------------------------------------------
    def addtable(self,name,session,model,hdrmap=None,**kwargs):
    #----------------------------------------------------------------------
        '''
        insert a new element or update an existing on based on kwargs query
        
        hdrmap may be of the form {infield1:{outfield:function,...},infield2:outfield2,...},
        
            where:
                
                outfield is the column name
                function is defined as function(session,value), session is database session and value is the value of the inrow[infield]
                
                this allows multiple output columns, each tranformed from the input by a different function
        
        :param name: 'sheet' name, used to name output file
        :param session: session within which update occurs
        :param model: table model
        :param hdrmap: maps input table column names to csv header -- if None, input table column names are used as csv header
        :param **kwargs: used for db filter
        '''
        # TODO: currently this only handles flat tables, i.e., if workbook originally was used to make
        # the tables and one sheet made multiple tables, this won't be able to recreate the csv sheet.
        # Not sure what it would take to recreate the csv in that case, but probably has something to do
        # with Mapper.col and Mapper.col.attr -- wish sqlalchemy docs were a bit more clear on this
    
        # get the column names from the model
        inhdr = []
        for col in class_mapper(model).columns:
            inhdr.append(col.key)
        
        # figure out mapping from inhdr to outhdr, and create outhdr
        if hdrmap is not None:
            # NOTE: this has the effect of filtering input columns
            outhndlr = [hdrmap[k] for k in hdrmap]
            outhdr = []
            for k in outhndlr:
                if type(k) == str:
                    outhdr.append(k)
                elif type(k) == dict:
                    # assumes only one level
                    for subk in k:
                        if type(subk) != str:
                            raise parameterError('{0}: invalid hdrmap {1}'.format(filename, hdrmap))
                        outhdr.append(subk)
                else:
                    raise parameterError('{0}: invalid hdrmap {1}'.format(filename, hdrmap))
        else:
            hdrmap = dict(zip(inhdr,inhdr))
            outhdr = inhdr

        # create output csv file and write header
        self.files[name] = '{0}/{1}.csv'.format(self.dir,name)
        OUT = open(self.files[name], 'wb')
        writer = unicodecsv.DictWriter(OUT,outhdr)
        writer.writeheader()
            
        # copy all the rows in the table to the csv file
        for inrow in session.query(model).filter_by(**kwargs).all():
            outrow = {}
            for incol in inhdr:
                if incol in hdrmap:
                    outcol = hdrmap[incol]
                    if type(outcol) == str:
                        outrow[outcol] = getattr(inrow,incol)
                    # must be dict, call function(session,value) to determine value transformation
                    else:
                        # tranform input for each configured output column
                        for subk in outcol:
                            outrow[subk] = outcol[subk](session,getattr(inrow,incol))
            writer.writerow(outrow)
        
        # we're done with this sheet
        OUT.close()
        
###############################################################################
class wlist(list):
###############################################################################
    '''
    extends list to include a write method, in order to allow csv.writer to output to the list
    '''

    #----------------------------------------------------------------------
    def write(self, line):
    #----------------------------------------------------------------------
        '''
        write method to be added to list object.  Appends line to the list
        
        :param line: line to append to the list
        '''
        self.append(line)   
    
################################################################################
def main():
################################################################################
    '''
    unit tests
    '''

    parser = argparse.ArgumentParser(version='{0} {1}'.format('loutilities',version.__version__))
    parser.add_argument('-d','--dbfilename',help='name of db file for testing')
    #parser.add_argument('--nowuaccess',help='use option to inhibit wunderground access using apikey',action="store_true")
    #parser.add_argument('-l','--loglevel',help='set logging level (default=%(default)s)',default='WARNING')
    #parser.add_argument('-o','--logfile',help='logging output file (default=stdout)',default=sys.stdout)
    args = parser.parse_args()
    
    # act on arguments
    dbfilename = args.dbfilename
    
    # use running.racedb model to test
    from running import racedb
    racedb.setracedb(dbfilename)
    s = racedb.Session()
    
    dd = Db2Csv()

    # note it is ok to split name like this, because it will just get joined together when the csv is processed in clubmember
    hdrmap = {'dateofbirth':'DOB','gender':'Gender',
              'name':{'First':lambda f: ' '.join(f.split(' ')[0:-1]),'Last':lambda f: f.split(' ')[-1]},
              'hometown':{'City':lambda f: ','.join(f.split(',')[0:-1]), 'State': lambda f: f.split(',')[-1]}
                }
    dd.addtable('Sheet1',s,racedb.Runner,hdrmap,active=True)
    files = dd.getfiles()
    
    pdb.set_trace()
    


# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()

