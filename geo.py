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

# compute haversine distance with elevation accounted for
# https://stackoverflow.com/questions/14560999/using-the-haversine-formula-in-javascript
# https://math.stackexchange.com/questions/2075092/haversine-formula-that-includes-an-altitude-parameter
#----------------------------------------------------------------------
def haversineDistance(coords1, coords2, isMiles=True):
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

    R = 6371 # km

    x1 = lat2 - lat1
    dLat = math.radians(x1)
    x2 = lon2 - lon1
    dLon = math.radians(x2)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c

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

#----------------------------------------------------------------------
def elevation_gain(elevations, isMiles=True, upthreshold=7, downthreshold=7, debug=False):
#----------------------------------------------------------------------
    '''
    calculate elevation gain over a series of elevation points

    NOTE: thresholds of 7 meters approximately matches strava

    :param elevations: list of elevation points in meters
    :param isMiles:  if True return miles, if False return km
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


