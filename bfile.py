################################################################################
# bfile - binary file handler
#   supports one file, can be opened for input or output
#
#   Date        Author      Reason
#   ----        ------      ------
#   09/24/09    L King      Create
#   10/07/09    L King      Add seek method
#   11/29/10    L King      Add brecord class
#   12/16/10    L King      Allow optional rangecheck within brecord class
#   01/05/11    L King      - In brecord class, add ability to specify expressions 
#                             in the "countfield" for repeated records
#                           - Handle unexpected end of file more gracefully
#   01/27/11    L King      instantiate recursive handler correctly based in current 
#                           handler's input parameters
#   01/28/11    L King      add getcountfields, getfieldorder methods to brecord class
#   01/04/12    L King      add byteorder parameter to bfile class
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
################################################################################
"""
bfile -- binary file handling
====================================

An object of this class supports one file, which can be opened for input or output.  Current implementation assumes file contains big-endian data.

Example use of :class:`bfile.bfile` opens a file, then reads a 2 byte unsigned field, then a 4 byte unsigned field::

    foo = bfile.bfile()
    foo.open(foofile, "rb")
    
    barnone     = foo.uget(2)
    barsome	= foo.uget(4)

    foo.close()
    
Example use of :class:`bfile.brecord` (note highest level is :attr:`foostruct` dictionary)::
    
    import bfile
    
    # need to create the lower level dictionaries first, else python will complain

    # make a convenience copy of the bfile.brecord sign indicators
    (U, TS, S, F) = (bfile.U, bfile.TS, bfile.S, bfile.F)

    # dictionary which describes file structure has scalars such as 'BARNONE', and subrecords such as 
    # 'satcontactrecs'.  Note use of tuples (e.g., "(0, 2, U)", with parens) for scalars, and lists 
    # (e.g., "[9,'NUM_SAT_CONTACTS', satcontactcomm, None]" with square brackets) for subrecords.  Use of list is 
    # required for subrecords because the data within is changed by bfile.brecord itself, and tuples are immutable
    
    # note range field is optional, and it must be a single entry 
    # to verify a min,max range, use the tuple value (min,max) -- **tuples (in parens) are assumed to be min,max!!**
    # to verify within a discrete set of values, use a list, e.g., [1,2,5] or range(6)
    
    foo                     = dict(#   ndx   len sign    range
        BARNONE             = (0,   1,  U,      (0,15)),
        SAT_PN              = (1,   1,  U,      (0,15)),
        ANT_REF_NUM         = (2,   1,  U,      (0,3)),
        T_START_TIME        = (3,   4,  TS),    # note no range specified here
        T_STOP_TIME         = (4,   4,  TS),
        CONTACT_ENRGY       = (5,   4,  U,      (0,480000)),
        NUM_SAT_PWR         = (6,   1,  U,      (1,20)),
                         #    ndx   count           structure       handler(added later)
        satpwrsegs          = [7,   'NUM_SAT_PWR',  satpwrsegcomm,  None],
        NUM_RHPOL_PWR       = (8,   1,  U),
        rhpolpwrsegrecs     = [9,   'NUM_RHPOL_PWR', polpwrsegcomm, None],
        NUM_LHPOL_PWR       = (10,  1,  U),
        lhpolpwrsegrecs     = [11,  'NUM_LHPOL_PWR', polpwrsegcomm, None],
        NUM_BEAMS_F         = (12,  1,  U),
        fwdbeamrecs         = [13,  'NUM_BEAMS_F',  fwdbeamreccomm, None],
        NUM_BEAMS_R         = (14,  1,  U),
        rvsbeamrecs         = [15,  'NUM_BEAMS_R',  rvsbeamreccomm, None],
        )

    raistruct = dict(      #  ndx  len sign     range
        GATEWAY_ID          = (0,   2,  U,      (1,100)),
        START_TIME          = (1,   4,  TS),
        STOP_TIME           = (2,   4,  TS),
        NUM_ALERTING        = (3,   1,  U,      [0,1,2,4]),
        ACCESS_CHAN         = (4,   2,  U),
        REV_ANCHOR_FREQ     = (5,   2,  U,      (4,496)),
        BACH_PWR_OFFSET     = (6,   2,  U,      range(100,900,25)),
        NUM_PAGING          = (7,   1,  U,      [2,4,8]),
        NUM_SAT_CONTACTS    = (8,   2,  U,      (1,512)),
                         #    ndx   count           structure       handler(added later)
        satcontactrecs      = [9,   'NUM_SAT_CONTACTS', foo, None],
        )
    
    # create the handler object
    raih = bfile.brecord(raistruct)


"""

# standard
from __future__ import print_function
import pdb
import struct
import sys
import re

class invalidRangeCheck(Exception): pass

# ###############################################################################
def rangecheck (start,  fieldname, value, *range, **kwargs):
# ###############################################################################
    """
    range check data
    
    :param start: number of bytes into the file at the start of the field
    :param fieldname: name of the field
    :param value: value of the field
    :param range: verify value is within this range
    
        * If two values supplied, range[0] is min, range[1] is max
        * If tuple supplied, (min,max) is assumed
        * If list supplied, valid values are in the list
        
    :param rangeerr=sys.stdout: file to send output to
    """
    
    maxwidth = 30
    
    # default for rangeerr keyword arg is sys.stdout
    rangeerr = kwargs.get('rangeerr', sys.stdout)
    
    # save original parameters for possible exception
    origrange = range
    
    # if one value supplied, might be a tuple.  If a tuple, detuple it
    if len(range) == 1 and type(range[0]) == tuple:
        range = range[0]
        
    # if range[0] is a list or a set, then ignore range[1]
    if type(range[0]) == list or type(range[0]) == set:
        if not value in range[0]:
            iset = range[0]
            pset = format(iset)[0:maxwidth]
            if iset != pset: 
                pset += '...'
            print ('{0:06x}:\tRange Error: {1}={2} ({3})'.format(start, fieldname, value, pset), file=rangeerr)
    
    # If range[0] is int or float then it means min, and range[1] is max, else ignore
    elif type(range[0]) == int or type(range[0]) == float:
        if value < range[0] or value > range[1]:
            print ('{0:06x}:\tRange Error: {1}={2} ({3}..{4})'.format(start, fieldname, value,range[0],range[1]), file=rangeerr)

    else:
        raise invalidRangeCheck, 'start={0}, fieldname={1}, range={2}'.format(start,fieldname,origrange)

# ###############################################################################
class Struct:
    def __init__(self,
#	deal with fact that version 2.4 doesn't support struct.Struct class
        format):
#			format to pass into struct.xxx methods
# ###############################################################################

        self.format = format

# ###############################################################################
#	expose two methods
    def pack (self, *v):
        return struct.pack(self.format, *v)
    def unpack (self, string):
        return struct.unpack(self.format, string)


tf = '%Y-%m-%d-%H:%M:%S'

class unexpectedEOF(Exception): pass
class parameterError(Exception): pass

# ###############################################################################
class bfile:
# ###############################################################################
    """
    Create an object of this class to work with an associated with a binary file
    
    :param byteorder: indicate byte order character, per struct fmt param '>' is big-endian (default), '<' is little-endian, see http://docs.python.org/release/2.6.6/library/struct.html#byte-order-size-and-alignment
    """
# ###############################################################################
    def __init__(self, byteorder='>'):
# ###############################################################################

        self.__currloc = 0
        
        allowedbyteorder = ['>','<','@','=','!']
        if byteorder not in allowedbyteorder:
            raise parameterError, 'byteorder must be one of {0}'.format(allowedbyteorder)

        # some handy structures
        self.sint8 = Struct (byteorder+'b')
        self.uint8 = Struct (byteorder+'B')
        self.sint16 = Struct (byteorder+'h')
        self.uint16 = Struct (byteorder+'H')
        self.sint32 = Struct (byteorder+'l')
        self.uint32 = Struct (byteorder+'L')
        self.sint64 = Struct (byteorder+'q')
        self.uint64 = Struct (byteorder+'Q')
        self.float32 = Struct (byteorder+'f')
        self.float64 = Struct (byteorder+'d')

        self.ustruct = {1:self.uint8, 2:self.uint16, 4:self.uint32, 8:self.uint64}
        self.sstruct = {1:self.sint8, 2:self.sint16, 4:self.sint32, 8:self.sint64}
        self.fstruct = {4:self.float32, 8:self.float64}

        
# ###############################################################################
    def open (self, filename, mode):
# ###############################################################################
        """
        open file object

        :param filename: name of file to open
        :param mode: mode to open file - must include 'b' to support binary read / write
        """

        self.file = open(filename,mode)
        self.__currloc = 0

# ###############################################################################
    def close (self): 
# ###############################################################################
        """
        close the file object
        """
        self.file.close()

# ###############################################################################
    def uget (self, numbytes):
# ###############################################################################
        """
        get unsigned bytes

        
        :param numbytes: number of bytes to read from the file
        :rtype: str with bytes from file
        """

        self.__currloc += numbytes
        data = self.file.read(numbytes)
        if len(data) < numbytes: raise unexpectedEOF
        (rtnval,) = self.ustruct[numbytes].unpack(data)
        return rtnval

# ###############################################################################
    def sget (self, numbytes):
# ###############################################################################
        """
        get signed bytes

        
        :param numbytes: number of bytes to read from the file
        :rtype: str with bytes from file
        """

        self.__currloc += numbytes
        data = self.file.read(numbytes)
        if len(data) < numbytes: raise unexpectedEOF
        (rtnval,) = self.sstruct[numbytes].unpack(data)
        return rtnval

# ###############################################################################
    def fget (self, numbytes):
# ###############################################################################
        """
        get floating point bytes

        
        :param numbytes: number of bytes to read from the file
        :rtype: str with bytes from file
        """

        self.__currloc += numbytes
        data = self.file.read(numbytes)
        if len(data) < numbytes: raise unexpectedEOF
        (rtnval,) = self.fstruct[numbytes].unpack(data)
        return rtnval

# ###############################################################################
    def uput (self, numbytes, buffer):
# ###############################################################################
        """
        put unsigned bytes

        :param numbytes: number of bytes to write to the file
        :param buffer: str with bytes to be written to file
        """

        self.__currloc += numbytes
        self.file.write(self.ustruct[numbytes].pack(buffer))

# ###############################################################################
    def sput (self, numbytes, buffer):
# ###############################################################################
        """
        put signed bytes

        :param numbytes: number of bytes to write to the file
        :param buffer: str with bytes to be written to file
        """

        self.__currloc += numbytes
        self.file.write(self.sstruct[numbytes].pack(buffer))

# ###############################################################################
    def fput (self, numbytes, buffer):
# ###############################################################################
        """
        put floating point bytes

        :param numbytes: number of bytes to write to the file
        :param buffer: str with bytes to be written to file
        """

        self.__currloc += numbytes
        self.file.write(self.fstruct[numbytes].pack(buffer))

# ###############################################################################
    def get (self, numbytes):
# ###############################################################################
        """
        get raw bytes

        
        :param numbytes: number of bytes to read from the file
        :rtype: str with bytes from file
        """

        self.__currloc += numbytes
        rtnval = self.file.read(numbytes)
        return rtnval

# ###############################################################################
    def put (self, buffer):
# ###############################################################################
        """
        put raw bytes

        :param buffer: str with bytes to be written to file
        """

        numbytes = len(buffer)
        self.__currloc += numbytes
        self.file.write(buffer)

# ###############################################################################
    def seek (self, loc):
# ###############################################################################
        """
        seek a new location
        
        :param loc: location to put the read or write pointer for the file
        :rtype: int with the previous location
        """
        
        prevloc = self.file.tell()
        self.file.seek(loc)
        self.__currloc = loc     
        return prevloc

# ###############################################################################
    def currloc (self):
# ###############################################################################
        """
        return the current location in the file
        
        :rtype: int with current location
        """

        return self.__currloc

# ###############################################################################
# Keep these constants, exceptions and functions with brecord class
# ###############################################################################
(NDXNDX,LENNDX,SIGNNDX,RNGNDX) = range(4)      # LENNDX points at an int
(NDXNDX,CNTFNDX,STRUCNDX,HNDLRNDX) = range(4)    # CNTFNDX points at a string
(U,TS,S,F) = range(4)   # U = unsigned, TS = timestamp, S = signed, F = float

class invalidSubrecCount(Exception): pass
class invalidStruct(Exception): pass
class invalidInputKeyNotFound(Exception): pass
class invalidCount(Exception): pass

# ###############################################################################
def exprfilter(exprstr, varprefix, varsuffix):
# ###############################################################################
    """
    filter an expression string with certain operators, to an updated expression
    string, that has varprefix before each variables (i.e., any part of the string
    which isn't an operator) and has varsuffix after each variable
    
    valid operators are ( ) * +
    
    :param exprstr: expression string, e.g., '((XXX+YY)*Z)'
    :param varprefix: prefix to put on variables within exprstr, e.g., 'x['
    :param varsuffix: suffix to put on variables within exprstr, e.g., ']'
    :rtype: string with variables updated based on varprefix, varsuffix, e.g., '((x[XXX]+x[YY])*x[Z])'.  This is suitable for call to :func:`eval()`
    """
    
    
    p = re.compile('[()*+]')
    
    # verify the expression has the correct number of parenthesis
    operators = p.findall(exprstr)
    parencheck = 0
    for o in operators:
        if o == '(':
            parencheck += 1
        elif o == ')':
            parencheck -= 1
    if parencheck != 0:
        raise invalidCount, 'unmatched parenthesis in {0}'.format(exprstr)
    
    # create iterator which demarcates the operators vs. the variables
    # incrementally add operators and updated variables to expression
    iter = p.finditer(exprstr)
    retval = ''
    lastend = 0
    for m in iter:
        if lastend == m.start():
            retval += m.group() # add the operator for this group
        else:
            retval += varprefix + exprstr[lastend:m.start()] + varsuffix
            retval += m.group() # add the operator for this group
        lastend = m.end()
    if lastend != len(exprstr):
        retval += varprefix + exprstr[lastend:len(exprstr)] + varsuffix
    
    return retval

# ###############################################################################
class brecord():
# ###############################################################################
    """
    Generic binary record
    
    :param recstruct: dictionary containing binary record structure
    
        where
            recstruct = 
                {'fieldname':(index,length,sign[,range]), ...}            "scalar field"
                
                or  {'recordname':[index,countfield,structure,None], ...}  "record field" (4th entry of list must be "None")
                
                    index = incremented from 0 for each field -- this needs to be maintained because python 2.6 does not support ordered dictionaries
                    
                    length = length in bytes of field
                    
                    sign = bfile.U - unsigned, bfile.TS - timestamp, bfile.S - signed, bfile.F - float
                    
                    range = optional tuple with two values for (min,max), or list with possible values for [val1,val2, ..., valn]
                    
                    countfield = 'fieldname' of field which has the count for the number of records in this list
                    
                    structure = recstruct pointing to sub-record (recursive)
                    
                    None = must be 'None' (see example) - placeholder for internal use of :class:`bfile.brecord`

    :param dorangecheck: if True, upon :meth:`get`, perform range check with errors to rangeerr, default False
    :param rangeerr: file handle, default sys.stdout
    """
    
    # ###############################################################################
    def __init__(self, recstruct, dorangecheck=False, rangeerr=sys.stdout, rangeignore=[]):
    # ###############################################################################
        self.recstruct = recstruct
        
        fieldlist = []
        r = self.recstruct  # local convenience
        for field in r.keys():
            fieldlist += [(r[field][NDXNDX], (field, r[field]))]  # pull out the field index, to sort
        fieldlist.sort()
        
        self.ordered = [fieldent[1] for fieldent in fieldlist]
        self._dorangecheck = dorangecheck
        self._rangeerr = rangeerr
        self._rangeignore = rangeignore
 
    # ###############################################################################
    def get(self, BF, kwargs):
    # ###############################################################################
        """
        Retrieves a record from a binary file.
        Perform range check on fields if :class:`brecord` instantiated with dorangecheck=True
        
        :param BF: bfile object opened in read mode
        :param kwargs: {'errdisplayfields':list} of fields which should be displayed upon unexpectedEOF exception
        :rtype: dictionary with the data from the record, with appropriate field keys.  Subrecords are ordered lists with these dictionaries.
        """
        
        # dump requested fields if this dictionary has them
        def _dumperrfields(d,fields):
            dumpstr = ''
            for f in d.keys():
                if f in fields:
                    dumpstr += '{0}={1}, '.format(f,d[f])
            if len(dumpstr) > 0:
                print('Unexpected end of file within record having {0}'.format(dumpstr[0:-2]))
            
        retval = {}
        
        # get the error display fields, default []
        errdisplayfields = kwargs.get('errdisplayfields',[])
            
        # Look at each field data in the ordered list.
        for f in self.ordered:
            field = f[0]
            length = f[1][LENNDX]   # take a chance -- it might be the length if a scalar field
            start = BF.currloc()    # for rangecheck, need to know the number of bytes processed in the file
            
            # For scalar fields, just get from the file
            if type(length) == int:
                try:
                    if f[1][SIGNNDX] == U or f[1][SIGNNDX] == TS:
                        retval[field] = BF.uget(length)
                    elif f[1][SIGNNDX] == S:
                        retval[field] = BF.sget(length)
                    elif f[1][SIGNNDX] == F:
                        retval[field] = BF.fget(length)
                    else:
                        raise invalidStruct, f
                    
                    # Perform range check if desired, and if field has a range to be checked, and if we're not supposed to ignore this field
                    dorangecheck = self._dorangecheck and len(f[1]) >= RNGNDX+1 and not field in self._rangeignore
                    if dorangecheck: 
                        rangecheck(start,field,retval[field],f[1][RNGNDX],rangeerr=self._rangeerr)
           
                except unexpectedEOF:
                    print('Unexpected end of file in {0}'.format(field))
                    _dumperrfields (retval, errdisplayfields)
                    raise
                    
            # If a "record field", create a handler if necessary, 
            # then get the appropriate number of those records (note this is recursive)
            else:
                # fill list with entries containing subrecord
                retval[field] = []
                countfield = f[1][CNTFNDX]

                # evaluate the expression indicated by the countfield
                # assumes count field was seen before the records
                count = eval(exprfilter(countfield,'retval["','"]'))

                # create a handler if necessary
                if f[1][HNDLRNDX] == None:
                    recstruct = f[1][STRUCNDX]
                    handler = brecord(recstruct,self._dorangecheck, self._rangeerr, self._rangeignore)
                    f[1][HNDLRNDX] = handler
                handler = f[1][HNDLRNDX]
                
                # get the records from the file.  store in a list
                for subrec in range(count):
                    try:
                        retval[field] += [handler.get(BF,kwargs)]
                    except unexpectedEOF:
                        print('Unexpected end of file in {0}'.format(field))
                        _dumperrfields (retval, errdisplayfields)
                        raise
            
        return retval
        
    # ###############################################################################
    def put(self, BF, record):
    # ###############################################################################
        """
        Inserts a record into a binary file
        
        :param BF: bfile object opened in write mode
        :param record: dictionary with the data from the record, with appropriate field keys.  Subrecords are ordered lists with these dictionaries.
        """
        
        # Look at each field data in the ordered list.
        for f in self.ordered:
            field = f[0]
            
            # unfortunately this doesn't provide a lot of information
            if not field in record.keys():
                raise invalidInputKeyNotFound, field
                
            length = f[1][LENNDX]  # take a chance -- it might be the length if a scalar field
            # For scalar fields, just put to the file
            if type(length) == int:
                if f[1][SIGNNDX] == U or f[1][SIGNNDX] == TS:
                    BF.uput(length, record[field])
                elif f[1][SIGNNDX] == S:
                    BF.sput(length, record[field])
                elif f[1][SIGNNDX] == F:
                    BF.fput(length, record[field])
                else:
                    raise invalidStruct, f
            
            # If a "record field", create a handler if necessary, 
            # then put the appropriate number of those records (note this is recursive)
            else:
                # fill list with entries containing subrecord
                countfield = f[1][CNTFNDX]

                # evaluate the expression indicated by the countfield
                # assumes count field was seen before the records
                count = eval(exprfilter(countfield,'record["','"]'))

                # create a handler if necessary
                if f[1][HNDLRNDX] == None:
                    recstruct = f[1][STRUCNDX]
                    handler = brecord(recstruct)
                    f[1][HNDLRNDX] = handler
                handler = f[1][HNDLRNDX]
                if len(record[field]) != count:
                    raise invalidSubrecCount, '{0}, count={1}, #subrecs={2}'.format(field, count, len(record[field]))
                
                # put the records to the file, from the list
                for subrec in record[field]:
                    handler.put(BF, subrec)

    # ###############################################################################
    def gettsfields(self):
    # ###############################################################################
        """
        Get timestamp fields.  Useful in case timestamps need to be shifted in time.
        
        :rtype: parallel dictionary to recstruct (see :class:`bfile.brecord`), which has True value for fields that are of type TS (timestamp)
        """
    
        retval = {}

        # Look at each field data in the ordered list.
        for f in self.ordered:
            field = f[0]
            
            length = f[1][LENNDX]  # take a chance -- it might be the length if a scalar field
            # For scalar fields, just put to the file
            if type(length) == int:
                if f[1][SIGNNDX] == TS:
                    retval[field] = True    # flag timestamp fields
                else:
                    retval[field] = False
            
            # If a "record field", create a handler if necessary, 
            # then put the appropriate number of those records (note this is recursive)
            else:
                # create a handler if necessary
                if f[1][HNDLRNDX] == None:
                    recstruct = f[1][STRUCNDX]
                    handler = brecord(recstruct)
                    f[1][HNDLRNDX] = handler
                handler = f[1][HNDLRNDX]
                
                # get the time stamps for the subrecord
                retval[field] = handler.gettsfields()
        
        return retval
        
    # ###############################################################################
    def getcountfields(self):
    # ###############################################################################
        """
        Get count fields.  Useful to automatically process a brecord file
        
        :rtype: parallel dictionary to recstruct (see :class:`bfile.brecord`), which has False value for scalars and {'count':countfield,'rec':subrecord} dictionary for subrecords
        """
    
        retval = {}

        # Look at each field data in the ordered list.
        for f in self.ordered:
            field = f[0]
            
            length = f[1][LENNDX]  # take a chance -- it might be the length if a scalar field
            # For scalar fields, just put to the file
            if type(length) == int:
                retval[field] = False
            
            # If a "record field", create a handler if necessary, 
            # then put the appropriate number of those records (note this is recursive)
            else:
                # create a handler if necessary
                if f[1][HNDLRNDX] == None:
                    recstruct = f[1][STRUCNDX]
                    handler = brecord(recstruct)
                    f[1][HNDLRNDX] = handler
                handler = f[1][HNDLRNDX]
                
                # get this count field and the count fields for the subrecord
                retval[field] = {'count':f[1][CNTFNDX],'rec':handler.getcountfields()}
        
        return retval
        
    # ###############################################################################
    def getfieldorder(self):
    # ###############################################################################
        """
        Get fields in order.  Useful to automatically process a brecord file.
        
        :rtype: list which is parallel to recstruct (see :class:`bfile.brecord`), ordered list of fieldnames, or (fieldname, [subfields...]) recursively
        """
    
        retval = []

        # Look at each field data in the ordered list.
        for f in self.ordered:
            field = f[0]
            
            length = f[1][LENNDX]  # take a chance -- it might be the length if a scalar field
            # For scalar fields, just put to the file
            if type(length) == int:
                retval += [field]
            
            # If a "record field", create a handler if necessary, 
            # then put the appropriate number of those records (note this is recursive)
            else:
                # create a handler if necessary
                if f[1][HNDLRNDX] == None:
                    recstruct = f[1][STRUCNDX]
                    handler = brecord(recstruct)
                    f[1][HNDLRNDX] = handler
                handler = f[1][HNDLRNDX]
                
                # get this count field and the count fields for the subrecord
                retval += [(field, handler.getfieldorder())]
        
        return retval
        
