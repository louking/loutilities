'''
nicknames - determine if names are related, e.g., nicknames for each other

adapted from https://github.com/carltonnorthern/nickname-and-diminutive-names-lookup
'''
import collections
import csv
from os.path import join, dirname, abspath

class NameDenormalizer(object):
    '''
    denormalize any name

    usage:
        $ nn = NameDenormalizer()
        $ nn.get('jeff')
        {'geoff', 'jefferson', 'jeffrey', 'jefferey', 'geoffrey', 'sonny'}
    '''
    def __init__(self, filename=None):
        filename = filename or join(dirname(abspath(__file__)), 'nicknames.csv')
        lookup = collections.defaultdict(list)
        with open(filename) as f:
            reader = csv.reader(f)
            for line in reader:
                matches = set(line)
                for match in matches:
                    lookup[match].append(matches)
        self.lookup = lookup

    def __getitem__(self, name):
        name = name.lower()
        if name not in self.lookup:
            raise KeyError(name)
        names = set().union(*self.lookup[name])
        if name in names:
            names.remove(name)
        return names

    def get(self, name, default=None):
        '''
        get a set of names which work for the indicated name

        :param name: name to get set for
        :param default: return this if none found (default None)
        :return: set of names, or default
        '''
        try:
            return self[name]
        except KeyError:
            return default