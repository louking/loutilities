###########################################################################################
# namesplitter - name splitting method
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/02/14        Lou King        Create
#
#   Copyright 2014 Lou King
#
#   Licensed under the Apache License, Version 2.0 (the "License")
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http:#www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
###########################################################################################
'''
namesplitter - name splitting method
=========================================

name splitting, adapted from the following

* https:#code.google.com/p/php-name-parser/source/browse/trunk/parser.php

also reviewed

* https:#github.com/pahanix/full-name-splitter

see http:#www.w3.org/International/questions/qa-personal-names for more information on international name formats

'''
# standard
import re

# homegrown

SALUTATIONS = 'mr master mister mrs miss ms dr rev fr'.split()  # NOT USED - see is_salutation

# these are some common prefixes that identify a compound last names - what am I missing?
PREFIXES = 'de da la du di del dei pietro vda. dello della degli delle van vanden vere von der den heer ten ter vande vanden vander voor ver aan mc ben st. st'.split()
SUFFIXES = 'I II III IV V Senior Junior Jr Sr PhD APR RPh PE MD MA DMD CME'.split()

# split full names into the following parts:
# - prefix / salutation  (Mr., Mrs., etc)
# - given name / first name
# - middle initials
# - surname / last name
# - suffix (II, Phd, Jr, etc)
def split_full_name(full_name):
    full_name = full_name.strip()
    # split into words
    unfiltered_name_parts = full_name.split(' ')
    # completely ignore any words in parentheses
    name_parts = []
    for word in unfiltered_name_parts:
        if word == '': continue # special case, too many spaces
        if (word[0] != "("):
            name_parts.append(word)

    num_words = len(name_parts)

    # is the first word a title? (Mr. Mrs, etc)
    salutation = is_salutation(name_parts[0])
    suffix = is_suffix(name_parts[len(name_parts)-1])

    # set the range for the middle part of the name (trim prefixes & suffixes)
    start = 1 if (salutation) else 0
    end = num_words-1 if (suffix) else num_words

    # initialize
    fname = ''
    initials = ''
    lname = ''
    
    # concat the first name [emulate php 'for ($i=$start; $i < $end-1; $i++)']
    i = start
    while i < end-1:
        word = name_parts[i]
        # move on to parsing the last name if we find an indicator of a compound last name (Von, Van, etc)
        # we use i != start to allow for rare cases where an indicator is actually the first name (like "Von Fabella")
        if (is_compound_lname(word) and i != start):
            break
        # is it a middle initial or part of their first name?
        # if we start off with an initial, we'll call it the first name
        if (is_initial(word)):
            # is the initial the first word?  
            if (i == start):
                ## if so, do a look-ahead to see if they go by their middle name
                ## for ex: "R. Jason Smith" => "Jason Smith" & "R." is stored as an initial
                ## but "R. J. Smith" => "R. Smith" and "J." is stored as an initial
                #if (is_initial(name_parts[i+1])):
                #    fname += " "+word.upper()
                #else:
                #    initials += " "+word.upper()
                
                # don't need the above logic, just store as part of first name
                fname += " "+word.upper()
            # otherwise, just go ahead and save the initial
            else:
                initials += " "+word.upper()
            
        else:
            fname += " "+fix_case(word)
        #[emulate php 'for ($i=$start; $i < $end-1; $i++)']
        i += 1
    
    # check that we have more than 1 word in our string
    if (end-start > 1):
        # concat the last name [emulate php 'for ($i; $i < $end; $i++)']
        while i < end:
            lname += " "+fix_case(name_parts[i])
            i += 1
    else:
        # otherwise, single word strings are assumed to be first names
        fname = fix_case(name_parts[i])

    # return the various parts
    name = {}
    name['salutation'] = salutation
    name['fname'] = fname.strip()
    name['initials'] = initials.strip()
    name['lname'] = lname.strip()
    name['suffix'] = suffix
    return name

# detect and format standard salutations
# I'm only considering english honorifics for now & not words like
def is_salutation(word):
    # ignore periods
    word = word.replace('.','').lower()
    # returns normalized values
    if (word in ["mr","master","mister"]):
        return "Mr."
    elif (word == "mrs"):
        return "Mrs."
    elif (word in ["miss","ms"]):
        return "Ms."
    elif (word == "dr"):
        return "Dr."
    elif (word == "rev"):
        return "Rev."
    elif (word == "fr"):
        return "Fr."
    else:
        return False

#  detect and format common suffixes
def is_suffix(word):
    # ignore periods
    word = word.replace('.','')
    # these are some common suffixes - what am I missing?
    suffix_array = SUFFIXES
    for suffix in suffix_array:
        if (suffix.lower() == word.lower()):
            return suffix
    return False

# detect compound last names like "Von Fange"
def is_compound_lname(word):
    return word.lower() in PREFIXES

# single letter, possibly followed by a period
def is_initial(word):
    return ((len(word) == 1) or (len(word) == 2 and word[1] == "."))

# detect mixed case words like "McDonald"
# returns False if the string is all one case
def is_camel_case(word):
    #if (re.match(r"|[A-Z]+|s", word) and re.match(r"|[a-z]+|s", word)):
    if (re.match(r"([A-Z]*[a-z'][a-z']*[A-Z']|[a-z']*[A-Z'][A-Z']*[a-z'])[A-Za-z]*", word)):
        return True
    return False

# ucfirst words split by dashes or periods
# ucfirst all upper/lower strings, but leave camelcase words alone
def fix_case(word):
    # uppercase words split by dashes, like "Kimura-Fay"
    word = safe_ucfirst("-",word)
    # uppercase words split by periods, like "J.P."
    word = safe_ucfirst(".",word)
    return word

# helper def for fix_case
def safe_ucfirst(separator, word):
    # uppercase words split by the separator (ex. dashes or periods)
    parts = word.split(separator)
    words = []
    for word in parts:
        words.append(word if is_camel_case(word) else word.lower().capitalize())
    return separator.join(words)

#----------------------------------------------------------------------
def main():
#----------------------------------------------------------------------
    '''
    test name splitting function
    '''
    #standard -- only needed for testing
    import argparse
    import csv
    
    # homegrown
    import version


    parser = argparse.ArgumentParser(version='{0} {1}'.format('loutilities',version.__version__))
    #parser = argparse.ArgumentParser()
    parser.add_argument('filename',help='csv file containing "name" column')
    args = parser.parse_args()
    
    # act on arguments
    filename = args.filename
    outfile = '.'.join(filename.split('.')[:-1])+'-annotated.csv'

    # get access to file, create output file
    _IN = open(filename,'rb')
    IN = csv.DictReader(_IN)
    outfields = []
    for field in IN.fieldnames:
        outfields.append(field)
        if field == 'name':
            outfields += ['fname','lname','names']
    _OUT = open(outfile,'wb')
    OUT = csv.DictWriter(_OUT,outfields)
    OUT.writeheader()
    
    try:
        for rec in IN:
            names = split_full_name(rec['name'])
            rec['fname'] = ' '.join([names['fname'],names['initials']]).strip()
            rec['lname'] = names['lname']
            if names['suffix']:
                rec['lname'] += ' '+names['suffix']
            rec['lname'] = rec['lname'].strip()
            rec['names'] = names
            OUT.writerow(rec)
    
    finally:
        _IN.close()
        _OUT.close()


# ###############################################################################
# ###############################################################################
if __name__ == "__main__":
    main()

