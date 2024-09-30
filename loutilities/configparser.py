###########################################################################################
#   configparser - enhanced ConfigParser
#
#   Date        Author      Reason
#   ----        ------      ------
#   06/20/16    Lou King    create
#
#   Copyright 2016 Lou King
###########################################################################################

'''
configparser - enhanced ConfigParser
===================================================
uses pypi's configparser.ConfigParser.SafeConfigParser to parse INI file, but preserves case for keys
'''

# standard
from collections import OrderedDict
from configparser import ConfigParser

# pypi

config = ConfigParser()

# preserve case for keys, see https://docs.python.org/3/library/configparser.html#configparser.optionxform
config.optionxform = lambda option: option

# copy configuration into dict
def getitems(filepath, section):
    '''
    get items in section
    convert to integer, float, etc., as appropriate
    
    :param filepath: file to read config from
    :param section: section to read items from
    :rtype: OrderedDict containing {key:item, ...} (case is preserved for keys)
    '''
    config.read_file(open(filepath))
    thisconfig = config.items(section)
    outdict = OrderedDict()

    # apply configuration to app
    # eval is safe because this configuration is controlled at root
    for key,value in thisconfig:
        try:
            outdict[key] = eval(value)
        except:
            outdict[key] = value

    return outdict

