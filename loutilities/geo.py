###########################################################################################
#
#       Date            Author          Reason
#       ----            ------          ------
#       12/14/17        Lou King        Create
#
#   Copyright 2015 Lou King.  All rights reserved
###########################################################################################

# standard
import xml.etree.ElementTree as ET
import math

###########################################################################################
class LatLng():
###########################################################################################
    #----------------------------------------------------------------------
    def __init__(self, file, filetype, getelev=False):
    #----------------------------------------------------------------------
        if filetype not in ['gpx', 'kml']:
            raise 'invalid type: ' + filetype
        self.filetype = filetype
        self.file = file
        self.getelev = getelev
        self._xml = ET.parse(self.file)

        # set namespace, assume ns is always the same as root
        self.root = self._xml.find('.')
        if self.root.tag[0] == '{':
            self.namespace = '{{{}}}'.format(self.root.tag[1:].split('}')[0])
        else:
            self.namespace = ''

        self._points = self._parse()

    #----------------------------------------------------------------------
    def getpoints(self):
    #----------------------------------------------------------------------
        return self._points  
  
    #----------------------------------------------------------------------
    def _parse(self):
    #----------------------------------------------------------------------
        if (self.filetype == 'kml'):
            return self._parsekml()
        elif (self.filetype == 'gpx'):
            return self._parsegpx()
  
    #----------------------------------------------------------------------
    def _parsekml(self):
    #----------------------------------------------------------------------
        coordstag = './{ns}Document/{ns}Placemark/{ns}LineString/{ns}coordinates'.format(ns=self.namespace)

        coordinates = self.root.find(coordstag)
        coords = coordinates.text.strip().split(' ')
        points = []
        for coord in coords:
            latlng = coord.split(',')
            point = [float(latlng[1]), float(latlng[0])]
            if self.getelev and len(latlng) >= 3: 
                point.append(float(latlng[2]))
            points.append(point)
        return points
  
    #----------------------------------------------------------------------
    def _parsegpx(self):
    #----------------------------------------------------------------------
        trkpttag = './{ns}trk/{ns}trkseg/{ns}trkpt'.format(ns=self.namespace)

        xmlpts = self.root.findall(trkpttag)
        points = []
        for xmlpt in xmlpts:
            point = [
                     float(xmlpt.attrib['lat']),
                     float(xmlpt.attrib['lon'])
                    ]
            if self.getelev:
                ele = xmlpt.find("{ns}ele".format(ns=self.namespace))
                if ele is not None: 
                    point.append(float(ele.text))
            points.append(point)
        return points

###########################################################################################
class GeoDistance():
###########################################################################################
    '''
    calculation functions which depend on Earth radius

    :param R: radius of Earth at nominal desired latitude
    '''

    #----------------------------------------------------------------------
    def __init__(self, R):
    #----------------------------------------------------------------------
        self.R = R

    # compute haversine distance with elevation accounted for
    # https://stackoverflow.com/questions/14560999/using-the-haversine-formula-in-javascript
    # https://math.stackexchange.com/questions/2075092/haversine-formula-that-includes-an-altitude-parameter
    #----------------------------------------------------------------------
    def haversineDistance(self, coords1, coords2, isMiles=True):
    #----------------------------------------------------------------------
        '''
        calculate the distance between two lat,lng,ele coordinates

        Note: the ele item in the coordinate tuple is optional

        :param coords1: [lat, lng, ele] or [lat, lng] lat,lng dec degrees, ele meters
        :param coords2: [lat, lng, ele] or [lat, lng]
        :param isMiles: if True return miles, if False return km
        :rtype: distance between the points
        '''
        lat1 = coords1[0]
        lon1 = coords1[1]
        ele1 = coords1[2] if len(coords1)>=3 else 0.0 # units feet or meters

        lat2 = coords2[0]
        lon2 = coords2[1]
        ele2 = coords2[2] if len(coords2)>=3 else 0.0

        x1 = lat2 - lat1
        dLat = math.radians(x1)
        x2 = lon2 - lon1
        dLon = math.radians(x2)
        a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dLon / 2) * math.sin(dLon / 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        d = self.R * c

        if isMiles:
            d /= 1.609344

        # account for elevation. ok if difference is negative because squaring
        if isMiles:
            ele1 /= 5280
            ele2 /= 5280
        else:
            ele1 /= 1000
            ele2 /= 1000
        
        de = ele2 - ele1
        d = math.sqrt(d*d + de*de)

        return d

    # from https://gis.stackexchange.com/questions/157693/getting-all-vertex-lat-long-coordinates-every-1-meter-between-two-known-points
    #----------------------------------------------------------------------
    def getDestinationLatLng(self, coord, azimuth, distance):
    #----------------------------------------------------------------------
        '''
        returns the lat and lng of destination point 
        given the start lat, long, azimuth, and distance

        :param coord: [lat,lng]
        :param azimuth: direction in degrees
        :param distance: distance in meters
        :rtype: [lat, lng]
        '''
        brng = math.radians(azimuth) 
        d = distance/1000 
        lat1 = math.radians(coord[0]) 
        lon1 = math.radians(coord[1]) 
        lat2 = math.asin(math.sin(lat1) * math.cos(d/self.R) + math.cos(lat1) * math.sin(d/self.R) * math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d/self.R) * math.cos(lat1), math.cos(d/self.R) - math.sin(lat1) * math.sin(lat2))

        lat2 = math.degrees(lat2)
        lon2 = math.degrees(lon2)
        return [lat2, lon2]

# from https://gis.stackexchange.com/questions/157693/getting-all-vertex-lat-long-coordinates-every-1-meter-between-two-known-points
#----------------------------------------------------------------------
def calculateBearing(coord1, coord2):
#----------------------------------------------------------------------
    '''
    calculates the azimuth in degrees from start point to end point

    :param coord1: start point [lat, lng]
    :param coord2: end point [lat, lng]
    :rtype: azimuth in degrees
    '''
    startLat = math.radians(coord1[0])
    startLong = math.radians(coord1[1])
    endLat = math.radians(coord2[0])
    endLong = math.radians(coord2[1])

    dLong = endLong - startLong
    dPhi = math.log(math.tan(endLat/2.0+math.pi/4.0)/math.tan(startLat/2.0+math.pi/4.0))
    if abs(dLong) > math.pi:
        if dLong > 0.0:
            dLong = -(2.0 * math.pi - dLong)
        else:
            dLong = (2.0 * math.pi + dLong)

    bearing = (math.degrees(math.atan2(dLong, dPhi)) + 360.0) % 360.0;
    return bearing


#----------------------------------------------------------------------
def elevation_gain(elevations, isMiles=True, upthreshold=8, downthreshold=8, debug=False):
#----------------------------------------------------------------------
    '''
    calculate elevation gain over a series of elevation points

    NOTE: thresholds of 8 meters approximately matches strava

    :param elevations: list of elevation points in meters
    :param isMiles:  if True return feet, if False return m
    :param upthreshold: threshold of increase when to decide climbing, meters
    :param downthreshold: threshold of decrease when to decide descending, meters
    :param debug: if True, return tuple with gain, debuginfo
    :rtype: gain[, debuginfo] - gain in meters or feet depending on isMiles
    '''
    # highup keeps track of the highest elevation reached while climbing
    # lowdown keeps track of the lowest elevation reached while descending
    # decision is made to switch from climbing to descending and visa versa
    # when threshold is passed in appropriate direction
    if debug: debuginfo = ['ele,state,highup,lowdown,totclimb\n']
    state = 'unknown'
    thisel = elevations[0]
    highup   = thisel
    lowdown  = thisel
    totclimb = 0.0
    if debug: debuginfo.append('{},{},{},{},{}\n'.format(thisel,state,highup,lowdown,totclimb))
    for thisel in elevations[1:]:
        if state == 'unknown':
            if thisel >= highup + upthreshold:
                state = 'climbing'
                highup = thisel
            elif thisel <= lowdown - downthreshold:
                state = 'descending'
                lowdown = thisel

        elif state == 'climbing':
            if thisel > highup:
                highup = thisel

            elif thisel <= highup - downthreshold:
                state = 'descending'
                totclimb += highup - lowdown
                lowdown = thisel

        elif state == 'descending':
            if thisel < lowdown:
                lowdown = thisel

            elif thisel >= lowdown + upthreshold:
                state = 'climbing'
                highup = thisel

        if debug: debuginfo.append('{},{},{},{},{}\n'.format(thisel,state,highup,lowdown,totclimb))

    # may need to add last climb in
    if state == 'climbing':
        totclimb += highup - lowdown
        if debug:
            debuginfo.pop()
            debuginfo.append('{},{},{},{},{}\n'.format(thisel,state,highup,lowdown,totclimb))

    # convert to feet
    if isMiles:
        totclimb = (totclimb/1609.344) * 5280
    
    if debug: return totclimb, debuginfo

    return totclimb


