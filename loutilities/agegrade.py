'''
agegrade - calculate age grade statistics
===================================================
'''

# standard
import argparse
import csv
import os.path
import pickle
import shutil

# home grown

# pypi
# github

# exceptions for this module.  See __init__.py for package exceptions
class missingConfiguration(Exception): pass
class parameterError(Exception): pass

def getagtable(agegradewb):
    '''
    in return data structure:
    
    dist is distance in meters (approx)
    openstd is number of seconds for open standard for this distance
    age is age in years (integer)
    factor is age grade factor
    
    :param agegradewb: excel workbook containing age grade factors (e.g., from http://www.howardgrubb.co.uk/athletics/data/wavacalc10.xls)
    
    :rtype: dict: {
            'road: {'F':{dist:{'OC':openstd,age:factor,age:factor,...},...},'M':{dist:{'OC':openstd,age:factor,age:factor,...},...}},
            'trail: {'F':{dist:{'OC':openstd,age:factor,age:factor,...},...},'M':{dist:{'OC':openstd,age:factor,age:factor,...},...}},
            }

    '''
    
    agegradedata = {
        'road': {
            'F': {},
            'M': {},
            'X': {},
        },
        'track': {
            'F': {},
            'M': {},
            'X': {},
        },
    }
    
    # convert the workbook to csv
    from .csvwt import Xls2Csv

    c = Xls2Csv(agegradewb)
    # note non-binary uses men's age grades
    gen2sheet = {'F':'Women', 'M':'Men', 'X':'Men'}
    sheets = c.getfiles()
    
    for gen in ['F', 'M', 'X']:
        SHEET = open(sheets[gen2sheet[gen]],'r',newline='')
        sheet = csv.DictReader(SHEET)
        
        # convert fields to keys - e.g., '5.0' -> 5, skipping non-numeric keys
        f2age = {}
        for f in sheet.fieldnames:
            try:
                k = int(float(f))
                f2age[f] = k
            except ValueError:
                pass
        
        # add each row to data structure, but skip non-running events
        for r in sheet:
            if r['dist(km)'] == '0.0': continue
            
            # dist is rounded to the nearest meter so it can be used as a key
            dist = int(round(float(r['dist(km)'])*1000))

            # create dist
            surface = 'road' if r['isRoad'] == 1 else 'track'
            openstd = float(r['OC'])
            agegradedata[surface][gen][dist] = {'OC':openstd}
            
            # add each age factor
            for f in sheet.fieldnames:
                if f in f2age:
                    age = f2age[f]
                    agegradedata[surface][gen][dist][age] = float(r[f])
            
            
        SHEET.close()
    
    del c
    return agegradedata


class AgeGrade():
    '''
    AgeGrade object 
    
    agegradewb is in format per http://www.howardgrubb.co.uk/athletics/wmalookup15.html (deprecated)
    if agegradewb parameter is missing, previous configuration is used (deprecated)
    configuration is created through command line: agegrade.py [-a agworkbook | -c agconfigfile] (deprecated)
    
    :param agegradedata: data structure used by this class
        {
            'road: {
                'F':{dist:{'OC':openstd,age:factor,age:factor,...},...},
                'M':{dist:{'OC':openstd,age:factor,age:factor,...},...},
                'X':{dist:{'OC':openstd,age:factor,age:factor,...},...},
            },
            'trail: {
                'F':{dist:{'OC':openstd,age:factor,age:factor,...},...},
                'M':{dist:{'OC':openstd,age:factor,age:factor,...},...},
                'X':{dist:{'OC':openstd,age:factor,age:factor,...},...},
            },
        }
    :param agegradewb: (deprecated) excel workbook containing age grade factors
    :param DEBUG: logger function for debug output
    '''
    def __init__(self, agegradedata=None, agegradewb=None, DEBUG=None):
        from .config import CONFIGDIR
        self.DEBUG = DEBUG

        # use age grade data structure if specified
        if agegradedata:
            self.agegradedata = agegradedata
            
        # use age grade workbook if specified
        elif agegradewb:
            self.agegradedata = getagtable(agegradewb)
        
        # otherwise, pick up the data from the configuration
        else:
            pathn = os.path.join(CONFIGDIR,'agegrade.cfg')
            if not os.path.exists(pathn):
                raise missingConfiguration('agegrade configuration not found, run agegrade.py to configure')
            
            C = open(pathn)
            self.agegradedata = pickle.load(C)
            C.close()
            
    def getfactorstd(self, surface, age, gen, distmeters):
        '''
        interpolate factor and openstd based on distance for this age
        
        :param surface: 'road' or 'track'
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
        distlist = sorted(list(self.agegradedata[surface][gen].keys()))
        lastd = distlist[0]
        for i in range(1,len(distlist)):
            if distmeters <= distlist[i]:
                x0 = lastd
                x1 = distlist[i]
                f0 = self.agegradedata[surface][gen][x0][age]
                f1 = self.agegradedata[surface][gen][x1][age]
                oc0 = self.agegradedata[surface][gen][x0]['OC']
                oc1 = self.agegradedata[surface][gen][x1]['OC']
                break
            lastd = distlist[i]
            
        # interpolate factor and openstd (see http://en.wikipedia.org/wiki/Linear_interpolation)
        factor = f0 + (f1-f0)*((distmeters-x0)/(x1-x0))
        openstd = oc0 + (oc1-oc0)*((distmeters-x0)/(x1-x0))
        
        return factor,openstd
    
    def agegrade(self, age, gen, distmiles, time, surface=None, errorlogger=None):
        '''
        returns age grade statistics for the indicated age, gender, distance, result time
        
        NOTE: non-binary gen X currently returns Men's age grade
        
        :param age: integer age.  If float is supplied, integer portion is used (no interpolation of fractional age)
        :param gen: gender - M, F, X
        :param distmiles: distance (miles)
        :param time: time for distance (seconds)
        :param surface: (optional) 'road' or 'track', default 'road'
        
        :rtype: (age performance percentage, age graded result, age grade factor) - percentage is between 0 and 100, result is in seconds
        '''
        
        # check for some input errors
        gen = gen.upper()
        if gen not in ['F', 'M', 'X']:
            raise parameterError('gen must be M, F, or X')

        # number of meters in a mile
        mpermile = 1609.344     # wavacalc15 has been corrected - now also handles integer distmiles
        
        # some known conversions
        cdist = {26.2:42195,13.1:21098} # wavacalc15 has been corrected
        
        # determine distance in meters
        if distmiles in cdist:
            distmeters = cdist[distmiles]
        else:
            distmeters = distmiles*mpermile
        
        # surface might require some adjustment
        ## if surface not provided, assume road if we have road factors for this distance, else assume track
        ## this maintains backwards compatibility, or for when caller has no access to what surface a race was run on
        initialsurface = surface
        if not surface:
            minroad = min(list(self.agegradedata['road'][gen].keys()))
            # need to round distmeters here because dist keys are rounded integers
            if int(round(distmeters)) >= minroad:
                surface = 'road'
            else:
                surface = 'track'

        ## there are no trail factors, so use road factors if trail requested
        elif surface == 'trail':
            surface = 'road'
        
        # check distance within range.  Make min and max float so exception format specification works
        distlist = list(self.agegradedata[surface][gen].keys())
        minmeters = min(distlist)*1.0
        maxmeters = max(distlist)*1.0
        epsilon = 1 # meter fuzziness
        if distmeters < minmeters-epsilon or distmeters > maxmeters+epsilon:
            if errorlogger:
                errorlogger(f'received age={age} gen={gen} distmiles={distmiles} surface={initialsurface} time={time}, used surface={surface}')
            raise parameterError(
                'distmiles must be between {:0.3f} and {:0.1f}'.format(minmeters / mpermile, maxmeters / mpermile))

        # interpolate factor and openstd based on distance for this age
        age = int(age)
        if age in range(5,100):
            factor,openstd = self.getfactorstd(surface, age, gen, distmeters)
        
        # extrapolate for ages < 5
        elif age < 5:
            if True:
                factor,openstd = self.getfactorstd(surface, 5, gen, distmeters)
            
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
                factor,openstd = self.getfactorstd(surface, 99, gen, distmeters)
            
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
            self.DEBUG(f'dist={distmeters} surf={surface} age={age} gen={gen} openstd={openstd} factor={factor} time={time} agresult={agresult} ag%={agpercentage}\n')
        return agpercentage, agresult, factor

    def result(self,surface, age, gen, distmiles, agpc):
        '''
        returns age grade statistics for the indicated age, gender, distance, result time

        NOTE: non-binary gen X currently returns Men's age grade

        :param surface: 'road' or 'track'
        :param age: integer age.  If float is supplied, integer portion is used (no interpolation of fractional age)
        :param gen: gender - M, F, X
        :param distmiles: distance (miles)
        :param agpc: age grade percentage - between 0 and 100

        :rtype: result in seconds
        '''

        # check for some input errors
        gen = gen.upper()
        if gen not in ['F', 'M', 'X']:
            raise parameterError('gen must be M, F, or X')

        # number of meters in a mile -- close enough for this data set
        mpermile = 1609.344

        # some known conversions
        cdist = {26.2:42195,13.1:21098}

        # determine distance in meters
        if distmiles in cdist:
            distmeters = cdist[distmiles]
        else:
            distmeters = distmiles*mpermile

        # check distance within range.  Make min and max float so exception format specification works
        distlist = list(self.agegradedata[surface][gen].keys())
        minmeters = min(distlist)*1.0
        maxmeters = max(distlist)*1.0
        if distmeters < minmeters or distmeters > maxmeters:
            raise parameterError('distmiles must be between {0:f0.3} and {1:f0.1}'.format(minmeters/mpermile,maxmeters/mpermile))

        # interpolate factor and openstd based on distance for this age
        age = int(age)
        if age in range(5,100):
            factor,openstd = self.getfactorstd(age,gen,distmeters)

        # extrapolate for ages < 5
        elif age < 5:
            # don't do extrapolation
            if True:
                factor,openstd = self.getfactorstd(5,gen,distmeters)

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

        # return result
        time = (openstd/factor)/(agpc/100.0)
        return time

def main(): 
    descr = '''
    Update configuration for agegrade.py.  One of --agworkbook or --agconfigfile must be used,
    but not both.
    
    --agworkbook creates an agconfigfile and puts it in the configuration directory.
    --agconfigfile simply places the indicated file into the configuration directory.
    '''

    from . import version
    from .config import CONFIGDIR

    parser = argparse.ArgumentParser(prog='loutilities', description=descr,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-v', '--version', action='version', version='%(prog)s {}'.format(version.__version__))
    parser.add_argument('-a','--agworkbook',help='filename of age grade workbook.', default=None)
    parser.add_argument('-c','--agconfigfile',help='filename of age grade config file',default=None)
    args = parser.parse_args()

    # must have one of the options
    if not args.agworkbook and not args.agconfigfile:
        print('one of --agworkbook or --agconfigfile must be specified')
        return
        
    # can't have both of the options
    if args.agworkbook and args.agconfigfile:
        print('only one of --agworkbook or --agconfigfile should be specified')
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
            print('{0}: not found'.format(args.agconfigfile))
            return
        except KeyError:
            print('{0}: invalid format'.format(args.agconfigfile))
            return
            
        shutil.copyfile(args.agconfigfile,pathn)

    print('updated {0}'.format(pathn))


# ##########################################################################################
#	__main__
# ##########################################################################################
if __name__ == "__main__":
    main()