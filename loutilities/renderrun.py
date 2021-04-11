#!/usr/bin/python
###########################################################################################
# renderrun - common functions for rendering information related to running
#
#	Date		Author		Reason
#	----		------		------
#       02/24/13        Lou King        Create
#       03/07/14        Lou King        Copied from runningclub
#
#   Copyright 2013,2014 Lou King
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
renderrun - common functions for rendering information related to running
==============================================================================

'''

# standard
import math

# pypi

# github

# other

# home grown
from . import timeu

dbtime = timeu.asctime('%Y-%m-%d')
rndrtim = timeu.asctime('%m/%d/%Y')

class softwareError(Exception): pass

#----------------------------------------------------------------------
def getprecision(distance,surface='road'): 
#----------------------------------------------------------------------
    '''
    get the precision for rendering, based on distance
    
    precision might be different for time vs. age group adjusted time
    
    :param distance: distance (miles)
    :param surface: 'road', 'track' or 'trail', default 'road'
    :rtype: (timeprecision,agtimeprecision)
    '''
    
    meterspermile = 1609    # close enough, and this is the value used in agegrade.py
    
    # See rule 165 from http://www.usatf.org/usatf/files/f1/f101f17f-1b8b-4f1b-ac9c-d9022155aa94.pdf
    # all hand timed track races have resolution to 0.1 seconds; all road races have resolution to 1 seconds
    # all times are rounded up (done by caller of this method)
    # TODO: allow configuration of timing method (hand timed vs automatically timed)

    # track events
    if surface=='track':
        timeprecision = 1
        agtimeprecision = 1

    # road and trail events
    else:
        timeprecision = 0
        agtimeprecision = 0

    return timeprecision, agtimeprecision

#----------------------------------------------------------------------
def renderdate(dbdate): 
#----------------------------------------------------------------------
    '''
    create date for display
    
    :param dbdate: date from database ('yyyy-mm-dd')
    '''
    try:
        dtdate = dbtime.asc2dt(dbdate)
        rval = rndrtim.dt2asc(dtdate)
    except ValueError:
        rval = dbdate
    return rval

#----------------------------------------------------------------------
def adjusttime(rawtime,precision,useceiling=True): 
#----------------------------------------------------------------------
    '''
    adjust raw time based on precision
    
    :param rawtime: time in seconds
    :param precision: number of places after decimal point
    :param useceiling: True if ceiling function to be used (round up)
    
    :rtype: adjusted time in seconds (float)
    '''
    # shift time based on precision
    multiplier = 10**precision

    # multiply whole time by multiplier to get integral time
    # then take ceiling or round
    # then divide by multiplier to get whole and fractional part
    fixedtime = rawtime * multiplier
    if useceiling:
        adjfixedtime = math.ceil(fixedtime)
    else:
        adjfixedtime = round(fixedtime)
    adjtime = adjfixedtime / multiplier
    
    return adjtime

#----------------------------------------------------------------------
def rendertime(dbtime,precision,useceiling=True): 
#----------------------------------------------------------------------
    '''
    create time for display
    
    :param dbtime: time in seconds
    :param precision: number of places after decimal point
    :param useceiling: True if ceiling function to be used (round up)
    '''
    
    if precision > 0:
        ''' old code
        multiplier = 10**precision
        # note round up per USATF rule 165
        fracdbtime = dbtime - int(dbtime)
        if useceiling:
            frac = int(math.ceil(fracdbtime*multiplier))
        else:
            frac = int(round(fracdbtime*multiplier))
        if frac < multiplier:
            rettime = fracformat.format(frac)
            remdbtime = int(dbtime)
        else:
            rettime = fracformat.format(0)
            remdbtime = int(dbtime+1)
        '''
        
        # adjust time based on precision
        adjtime = adjusttime(dbtime,precision,useceiling)
        
        # update the rendering what will be returned to include fractional part and what remains
        wholetime = int(adjtime)
        fractime = adjtime - wholetime
        fracformat = '{{0:0.{0}f}}'.format(precision)
        rettime = fracformat.format(fractime)
        remdbtime = wholetime
        
        # retttime should have leading 0.  remove it
        if rettime[0] != '0':
            raise softwareError('formatted adjusted time fraction does not have leading 0: {0}'.format(adjtime))
        rettime = rettime[1:]
        
    else:
        # note round up per USATF rule 165
        if useceiling:
            remdbtime = int(math.ceil(dbtime))
        else:
            remdbtime = int(round(dbtime))
        rettime = ''
    
    thisunit = remdbtime%60
    firstthru = True
    while remdbtime > 0:
        if not firstthru:
            rettime = ':' + rettime
        firstthru = False
        rettime = '{0:02d}'.format(thisunit) + rettime
        remdbtime //= 60
        thisunit = remdbtime%60
        
    while rettime[0] == '0':
        rettime = rettime[1:]
        
    return rettime
