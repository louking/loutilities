'''
transform - transformation methods
'''

# homegrown
from .csvu import str2num

class Transform():
    '''
    transform objects using a mapping object

    mapping is dict like {'targetattr_n':'sourceattr_n', 'targetattr_m':f(source), ...}
    if order of operation is importand use OrderedDict

    source and target may be dict-like or class-like

    :param mapping: mapping dict with key for each target attr, value is key in source or function(source)
    :param sourceattr: True if getattr works with source, otherwise uses __getitem__ (as dict)
    :param targetattr: True if setattr works with target, otherwise uses __setitem__ (as dict)
    :param knownstrings: list of mapping keys for which numeric conversion isn't attempted
    '''

    def __init__(self, mapping, sourceattr=True, targetattr=True, knownstrings=[]):
        self.mapping = mapping
        self.sourceattr = sourceattr
        self.targetattr = targetattr
        self.knownstrings = knownstrings

    def transform(self, source, target):
        '''
        set target values based on source object

        :param source: source object (dict-like or class-like)
        :param target: target object (dict-like or class-like)
        '''

        # create target values based on mapping
        for key in self.mapping:
            # call the function to fill target
            if hasattr(self.mapping[key], '__call__'):
                callback = self.mapping[key]
                value = callback(source)
            
            # simple map from source field
            else:
                sourceattr = self.mapping[key]
                if self.sourceattr:
                    value = getattr(source, sourceattr)
                else:
                    value = source[sourceattr]

            # maybe convert to number or boolean before saving in target
            # skip keys which are known to be strings
            if isinstance(value, str) and key not in self.knownstrings:
                value = str2num(value)
                if value in ['false', 'False']:
                    value = False
                elif value in ['true', 'True']:
                    value = True

            # save value in target
            if self.targetattr:
                setattr(target, key, value)
            else:
                target[key] = value

