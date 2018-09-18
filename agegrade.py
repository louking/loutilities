#!/usr/bin/python
###########################################################################################
# agegrade - calculate age grade statistics
#
#	Date		Author		Reason
#	----		------		------
#       02/17/13        Lou King        Create
#       03/20/14        Lou King        Moved from runningclub
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
agegrade - calculate age grade statistics
===================================================
'''

# standard
import pdb
import argparse
import csv
import pickle
import os.path
import shutil
from math import floor

# pypi

# github

# home grown
import version
from config import *
from loutilities import csvwt

# exceptions for this module.  See __init__.py for package exceptions
class missingConfiguration(Exception): pass

#----------------------------------------------------------------------
def getagtable(agegradewb):
#----------------------------------------------------------------------
    '''
    in return data structure:
    
    dist is distance in meters (approx)
    openstd is number of seconds for open standard for this distance
    age is age in years (integer)
    factor is age grade factor
    
    :param agegradewb: excel workbook containing age grade factors (e.g., from http://www.howardgrubb.co.uk/athletics/data/wavacalc10.xls)
    
    :rtype: {'F':{dist:{'OC':openstd,age:factor,age:factor,...},...},'M':{dist:{'OC':openstd,age:factor,age:factor,...},...}}
    '''
    
    agegradedata = {}
    
    # convert the workbook to csv
    c = csvwt.Xls2Csv(agegradewb)
    gen2sheet = {'F':'Women','M':'Men'}
    sheets = c.getfiles()
    
    for gen in ['F','M']:
        SHEET = open(sheets[gen2sheet[gen]],'rb')
        sheet = csv.DictReader(SHEET)
        
        # convert fields to keys - e.g., '5.0' -> 5, skipping non-numeric keys
        f2age = {}
        for f in sheet.fieldnames:
            try:
                k = int(float(f))
                f2age[f] = k
            except ValueError:
                pass
        
        # create gender
        agegradedata[gen] = {}
        
        # add each row to data structure, but skip non-running events
        for r in sheet:
            if r['dist(km)'] == '0.0': continue
            
            # dist is rounded to the nearest meter so it can be used as a key
            dist = int(round(float(r['dist(km)'])*1000))

            # kludge to use only road events -- affects distances 5km and beyond (issue #55)
            # this works because Howard Grubb's spreadsheet has road first, then track for events which matter
            # as of wavacalc10.xls, includes 5k, 6k, 4M, 8k, 5M, 10k distances
            if dist in agegradedata[gen]: continue
            
            # create dist
            openstd = float(r['OC'])
            agegradedata[gen][dist] = {'OC':openstd}
            
            # add each age factor
            for f in sheet.fieldnames:
                if f in f2age:
                    age = f2age[f]
                    agegradedata[gen][dist][age] = float(r[f])
            
            
        SHEET.close()
    
    del c
    return agegradedata

########################################################################
class AgeGrade():
########################################################################
    '''
    AgeGrade object 
    
    agegradewb is in format per http://www.howardgrubb.co.uk/athletics/wmalookup06.html
    if agegradewb parameter is missing, previous configuration is used
    configuration is created through command line: agegrade.py [-a agworkbook | -c agconfigfile]
    
    :param agegradewb: excel workbook containing age grade factors
    :param DEBUG: file handle for debug output
    '''
    #----------------------------------------------------------------------
    def __init__(self,agegradewb=None,DEBUG=None):
    #----------------------------------------------------------------------
        self.DEBUG = DEBUG
        # write header for csv file.  Must match order within self.agegrade if self.DEBUG statement
        if self.DEBUG:
            self.DEBUG.write('distmeters,age,gen,openstd,factor,time,agresult,agpercentage\n')

        # use age grade workbook if specified
        if agegradewb:
            self.agegradedata = getagtable(agegradewb)
        
        # otherwise, pick up the data from the configuration
        else:
            pathn = os.path.join(CONFIGDIR,'agegrade.cfg')
            if not os.path.exists(pathn):
                raise missingConfiguration, 'agegrade configuration not found, run agegrade.py to configure'
            
            C = open(pathn)
            self.agegradedata = pickle.load(C)
            C.close()
            
    #----------------------------------------------------------------------
    def getfactorstd(self,age,gen,distmeters):
    #----------------------------------------------------------------------
        '''
        interpolate factor and openstd based on distance for this age
        
        :param age: integer age.  If float is supplied, integer portion is used (no interpolation of fractional age)
        :param gen: gender - M or F
        :param distmeters: distance (meters)
        
        :rtype: (factor, openstd) - factor (age grade factor) is between 0 and 1, openstd (open standard) is in seconds
        '''
        
        # round distmeters to the nearest meter as distlist keys are rounded to the nearest meter
        # need to do this so exact match doesn't get interpolated
        # alternate, possibly better, solution would be to use keys in millimeters rather than meters
        # but that would require reloading the data -- that might be fine, but is a bit risky
        # don't use int because need float arithmetic for interpolate
        distmeters = round(distmeters)

        # find surrounding Xi points, and corresponding Fi, OCi points
        distlist = self.agegradedata[gen].keys()
        distlist.sort()
        lastd = distlist[0]
        for i in range(1,len(distlist)):
            if distmeters <= distlist[i]:
                x0 = lastd
                x1 = distlist[i]
                f0 = self.agegradedata[gen][x0][age]
                f1 = self.agegradedata[gen][x1][age]
                oc0 = self.agegradedata[gen][x0]['OC']
                oc1 = self.agegradedata[gen][x1]['OC']
                break
            lastd = distlist[i]
            
        # interpolate factor and openstd (see http://en.wikipedia.org/wiki/Linear_interpolation)
        factor = f0 + (f1-f0)*((distmeters-x0)/(x1-x0))
        openstd = oc0 + (oc1-oc0)*((distmeters-x0)/(x1-x0))
        
        return factor,openstd
    
    #----------------------------------------------------------------------
    def agegrade(self,age,gen,distmiles,time):
    #----------------------------------------------------------------------
        '''
        returns age grade statistics for the indicated age, gender, distance, result time
        
        :param age: integer age.  If float is supplied, integer portion is used (no interpolation of fractional age)
        :param gen: gender - M or F
        :param distmiles: distance (miles)
        :param time: time for distance (seconds)
        
        :rtype: (age performance percentage, age graded result, age grade factor) - percentage is between 0 and 100, result is in seconds
        '''
        
        # check for some input errors
        gen = gen.upper()
        if gen not in ['F','M']:
            raise parameterError, 'gen must be M or F'

        # number of meters in a mile
        mpermile = 1609.344     # wavacalc15 has been corrected - now also handles integer distmiles
        
        # some known conversions
        cdist = {26.2:42195,13.1:21098} # wavacalc15 has been corrected
        
        # determine distance in meters
        if distmiles in cdist:
            distmeters = cdist[distmiles]
        else:
            distmeters = distmiles*mpermile
        
        # check distance within range.  Make min and max float so exception format specification works
        distlist = self.agegradedata[gen].keys()
        minmeters = min(distlist)*1.0
        maxmeters = max(distlist)*1.0
        if distmeters < minmeters or distmeters > maxmeters:
            raise parameterError, 'distmiles must be between {:0.3f} and {:0.1f}'.format(minmeters/mpermile,maxmeters/mpermile)

        # interpolate factor and openstd based on distance for this age
        age = int(age)
        if age in range(5,100):
            factor,openstd = self.getfactorstd(age,gen,distmeters)
        
        # extrapolate for ages < 5
        elif age < 5:
            if True:
                factor,openstd = self.getfactorstd(5,gen,distmeters)
            
            # don't do extrapolation
            else:
                age1 = 5
                age2 = 6
                factor1,openstd1 = self.getfactorstd(age1,gen,distmeters)
                factor2,openstd2 = self.getfactorstd(age2,gen,distmeters)
                factor = factor1 + (1.0*(age-age1)/(age2-age1))*(factor2-factor1)
                openstd = openstd1 + (1.0*(age-age1)/(age2-age1))*(openstd2-openstd1)
            
         # extrapolate for ages > 99
        elif age > 99:
            if True:
                factor,openstd = self.getfactorstd(99,gen,distmeters)
            
            # don't do extrapolation
            else:    
                age1 = 98
                age2 = 99
                factor1,openstd1 = self.getfactorstd(age1,gen,distmeters)
                factor2,openstd2 = self.getfactorstd(age2,gen,distmeters)
                factor = factor1 + (1.0*(age-age1)/(age2-age1))*(factor2-factor1)
                openstd = openstd1 + (1.0*(age-age1)/(age2-age1))*(openstd2-openstd1)
        
        # return age grade statistics
        agpercentage = 100*(openstd/factor)/time
        agresult = time*factor
        if self.DEBUG:
            # order must match header written in self.__init__
            self.DEBUG.write('{},{},{},{},{},{},{},{}\n'.format(distmeters,age,gen,openstd,factor,time,agresult,agpercentage))
        return agpercentage,agresult,factor

#----------------------------------------------------------------------
def main(): 
#----------------------------------------------------------------------
    descr = '''
    Update configuration for agegrade.py.  One of --agworkbook or --agconfigfile must be used,
    but not both.
    
    --agworkbook creates an agconfigfile and puts it in the configuration directory.
    --agconfigfile simply places the indicated file into the configuration directory.
    '''
    
    parser = argparse.ArgumentParser(description=descr,formatter_class=argparse.RawDescriptionHelpFormatter,
                                     version='{0} {1}'.format('loutilities',version.__version__))
    parser.add_argument('-a','--agworkbook',help='filename of age grade workbook.', default=None)
    parser.add_argument('-c','--agconfigfile',help='filename of age grade config file',default=None)
    args = parser.parse_args()

    # must have one of the options
    if not args.agworkbook and not args.agconfigfile:
        print 'one of --agworkbook or --agconfigfile must be specified'
        return
        
    # can't have both of the options
    if args.agworkbook and args.agconfigfile:
        print 'only one of --agworkbook or --agconfigfile should be specified'
        return

    # configuration file will be here    
    pathn = os.path.join(CONFIGDIR,'agegrade.cfg')

    # workbook specified
    if args.agworkbook:
        agegradedata = getagtable(args.agworkbook)
        C = open(pathn,'w')
        pickle.dump(agegradedata,C)
        C.close()
    
    # config file specified
    else:
        # make sure this is a pickle file
        try:
            C = open(args.agconfigfile)
            test = pickle.load(C)
            C.close()
        except IOError:
            print '{0}: not found'.format(args.agconfigfile)
            return
        except KeyError:
            print '{0}: invalid format'.format(args.agconfigfile)
            return
            
        shutil.copyfile(args.agconfigfile,pathn)
        
    print 'updated {0}'.format(pathn)
    
# ##########################################################################################
#	__main__
# ##########################################################################################
if __name__ == "__main__":
    main()