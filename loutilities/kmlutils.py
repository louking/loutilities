# ###############################################################################
# kmlutils - utilities for access to kml file
#
# REVISION HISTORY:
#	02/10/11    L King      Create
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
#
# ###############################################################################
"""
kmlutils - utilities for access to kml file
=============================================================

Provides methods to write KML files
"""

# standard
from xml.dom.minidom import getDOMImplementation as domimpl
import pdb

# home grown
# NONE

class invalidChildattrs(Exception): pass

# ###############################################################################
class kmldoc():
# ###############################################################################
    """
    Represents kml document
    
    :param name: name of high level document
    :rtype: kmldoc instance
    """

    # ###############################################################################
    def __init__(self, name):
    # ###############################################################################
    
        self.doc = domimpl().createDocument ("http://www.opengis.net/kml/2.2","kml",None)
        self.kml = self.doc.documentElement
        self.kml.setAttribute ("xmlns","http://www.opengis.net/kml/2.2")
        self.name = name
        ne = self.doc.createElement("name")
        ne.appendChild (self.doc.createTextNode(self.name))
        self.kml.appendChild(ne)
        self.dd = self.doc.createElement('Document')
        self.kml.appendChild(self.dd)
    
    # ###############################################################################
    def save(self,filename):
    # ###############################################################################
        """
        save document in the indicated filename
        
        :param filename: name of file to save kml output to
        """
        
        OUT = open(filename,'w')
        self.doc.writexml(OUT,addindent='  ',newl='\n')

    # ###############################################################################
    def appendChildAttrs(self, element, attrs):
    # ###############################################################################
        """
        recursively append the attributes indicated by attrs to the element
        
        :param element: element to append children to
        :param attrs: ellist | attrtree
        
            * attrtree - dict with keywords for element's child attributes (may be nested)
            * ellist - list of elements to be appended, can have embedded attrtrees
            * Note: attrtree can contain embedded ellists or attrtrees
        """
        
        if type(attrs) == dict:
            for attr in attrs:
                atel = self.doc.createElement(attr)
                
                # dict means that this has attr name/value pairs which needs to be appended
                if type(attrs[attr]) == dict:
                    self.appendChildAttrs(atel, attrs[attr])
                
                # list might have dict as above, or elements, which need to be appended
                elif type(attrs[attr]) == list:
                    for elattr in attrs[attr]:
                        if type(elattr) == dict:
                            self.appendChildAttrs(atel, elattr)
                        else:
                            atel.appendChild(elattr)
                
                # otherwise we're assuming this is just a text node
                else:
                    atel.appendChild(self.doc.createTextNode(attrs[attr]))
                element.appendChild(atel)
        
        elif type(attrs) == list:
            for elattr in attrs:
                if type(elattr) == dict:
                    self.appendChildAttrs(element, elattr)
                else:
                    element.appendChild(elattr)
                    
        else:
            raise invalidChildattrs
        
    # ###############################################################################
    def namedel(self, name, attrs, childattrs):
    # ###############################################################################
        """
        return a named element with initial attributes
        
        :param name: tagname for the element
        :param attrs: dictionary with keywords for element's attributes
        :param childattrs: ellist | attrtree
        
            * attrtree - dict with keywords for element's child attributes (may be nested)
            * ellist - list of elements to be appended, can have embedded attrtrees
            * Note: attrtree can contain embedded ellists or attrtrees
        """

        element = self.doc.createElement(name)
        for attr in attrs:
            element.setAttribute(attr, attrs[attr])
        self.appendChildAttrs(element, childattrs)
        return element

# ###############################################################################
class style():
# ###############################################################################
    """
    represents a style
    
    :param kml: kml instance
    :param name: name of style
    :param childattrs: dictionary with keywords for style attributes (may be nested)
    """
    
    # ###############################################################################
    def __init__(self, kml, name, childattrs):
    # ###############################################################################
    
        self.kml = kml
        self.name = name
        self.childattrs = childattrs

    # ###############################################################################
    def el(self):
    # ###############################################################################
        """
        return kml element for this object
        """
    
        element = self.kml.doc.createElement('Style')
        element.setAttribute('id',self.name)
        self.kml.appendChildAttrs(element, self.childattrs)
        return element
    
    # ###############################################################################
    def elurl(self):
    # ###############################################################################

        element = self.kml.doc.createElement('styleUrl')
        element.appendChild(self.kml.doc.createTextNode ('#{0}'.format(self.name)))
        return element
        
# ###############################################################################
class coordinates():
# ###############################################################################
    """
    represents a list of coordinates
    
    :param kml: kml instance
    :param clist: list of coordinates
    """
    
    # ###############################################################################
    def __init__(self, kml, clist):
    # ###############################################################################
    
        self.kml = kml
        self.clist = clist

    # ###############################################################################
    def el(self):
    # ###############################################################################
        """
        return kml element for this object
        """
    
        element = self.kml.doc.createElement('coordinates')
        element.appendChild (self.kml.doc.createTextNode (" ".join([c.str() for c in self.clist])))
        return element
        
# ###############################################################################
class coordinate():
# ###############################################################################
    """
    represents a coordinate
    
    :param lat: latitude (decimal degrees)
    :param long: longitude (decimal degrees)
    :param alt: altitude (meters) 
    """

    # ###############################################################################
    def __init__(self, lat, long, alt=None):
    # ###############################################################################
    
        self.lat = lat
        self.long = long
        self.alt = alt

    # ###############################################################################
    def str(self):
    # ###############################################################################
        """
        return kml string for this coordinate
        """
    
        if self.alt != None:
            return '{0},{1},{2}'.format(self.long, self.lat, self.alt)
        else:
            return '{0},{1}'.format(self.long, self.lat)
            

# ###############################################################################
def main():
# ###############################################################################

    kml = kmldoc('test doc')
    
    styred = style(kml, 'red-outline', 
        {'LineStyle':{'color':'ff0000ff'}, 
        'PolyStyle':{'fill':'0'},
        })
    
    styblue = style(kml, 'blue-outline', 
        {'LineStyle':{'color':'ffff0000'}, 
        'PolyStyle':{'fill':'0'},
        })
    
    stygreen = style(kml, 'green-outline', 
        {'LineStyle':{'color':'ff00ff00'}, 
        'PolyStyle':{'fill':'0'},
        })
    
    kml.dd.appendChild(styred.el())
    kml.dd.appendChild(styblue.el())
    kml.dd.appendChild(stygreen.el())
    
    cl = []
    for i in range(30):
        cl.append(coordinate(i,i+1,i+2))
    cs = coordinates(kml,cl)
    kml.dd.appendChild(cs.el())
    
    place = kml.namedel('Placemark',attrs={'id':'poly'},childattrs=[{'name':'poly'},stygreen.elurl(),{'Polygon':{'outerBoundaryIs':{'LinearRing':[cs.el()]}}}] )
    kml.dd.appendChild(place)
    
    kml.save('kmlutilstest.kml')

# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()
