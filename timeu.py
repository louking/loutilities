# ###############################################################################
# timeu -- time methods
#
# Author: L King
#
# REVISION HISTORY:
#   12/10/10    L King      Create
#   12/20/10    L King      Update doc string
#   03/18/11    L King      Fix some doc strings
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
# ###############################################################################
"""
timeu -- time methods
============================

Common time methods
"""

#standard
import pdb
import datetime
import calendar

# ###############################################################################
def epoch2dt (epochtime):
# ###############################################################################
    """
    get a datetime object corresponding to an epoch time
    
    :param epochtime: epoch time to convert
    :rtype: datetime object
    """
    
    return datetime.datetime.utcfromtimestamp(epochtime)

# ###############################################################################
def dt2epoch (dt):
# ###############################################################################
    """
    get an epoch time corresponding to a datetime object 
    
    :param dt: datetime object to convert
    :rtype: int (epoch time)
    """
    
    return int(calendar.timegm((dt).timetuple()))


# ###############################################################################
class asctime ():
# ###############################################################################
    """
    asctime -- provide formatting methods for ascii time format
    
    :param ascformat: time format for ascii conversion.  See http://docs.python.org/release/2.6.6/library/datetime.html#strftime-and-strptime-behavior for formats
    """
    
    # #######################################################################################
    def __init__(self, ascformat):
    # #######################################################################################
        self.ascformat = ascformat
    
    # ###############################################################################
    def asc2dt (self,asctime):
    # ###############################################################################
        """
        convert ASCII time to datetime object
        
        :param asctime: ASCII time
        :rtype: datetime.datetime object
        """

        return datetime.datetime.strptime (asctime, self.ascformat)

    # ###############################################################################
    def dt2asc (self,dt):
    # ###############################################################################
        """
        convert datetime object to ASCII TIME
        
        :param dt: datetime.datetime object
        :rtype: ASCII time
        """

        return datetime.datetime.strftime (dt, self.ascformat)
    
    # ###############################################################################
    def asc2epoch (self,asctime):
    # ###############################################################################
        """
        convert ASCII time to epoch time
        
        :param asctime: ASCII time
        :rtype: int (epoch time)
        """

        return dt2epoch(datetime.datetime.strptime (asctime, self.ascformat))

    # ###############################################################################
    def epoch2asc (self,epoch):
    # ###############################################################################
        """
        convert epoch time to ASCII time
        
        :param epoch: int (epoch time)
        :rtype: ASCII time
        """

        return datetime.datetime.strftime (epoch2dt(epoch), self.ascformat)
    
    