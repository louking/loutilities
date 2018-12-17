#!/usr/bin/python
###########################################################################################
# sqlalchemy_helpers  -- helper functions for sqlalchemy access
#
#       Date            Author          Reason
#       ----            ------          ------
#       06/30/18        Lou King        Create (copied from https://github.com/louking/rrwebapp/blob/master/rrwebapp/racedb.py)
#
#   Copyright 2018 Lou King.  All rights reserved
###########################################################################################
'''
sqlalchemy_helpers  -- helper functions for sqlalchemy access
===================================================

'''

# standard

# pypi
from sqlalchemy.orm import object_mapper

# github

# other

# home grown
import version

class dbConsistencyError(Exception): pass
class parameterError(Exception): pass

#----------------------------------------------------------------------
def getunique(session, model, **kwargs):
#----------------------------------------------------------------------
    '''
    retrieve a row from the database, raising exception of more than one row exists for query criteria
    
    :param session: session within which update occurs
    :param model: table model
    :param kwargs: query criteria
    
    :rtype: single instance of the row, or None
    '''

    instances = session.query(model).filter_by(**kwargs).all()

    # error if query returned multiple rows when it was supposed to be unique
    if len(instances) > 1:
        raise dbConsistencyError('found multiple rows in {0} for {1}'.format(model,kwargs))
    
    if len(instances) == 0:
        return None
    
    return instances[0]

#----------------------------------------------------------------------
def update(session, model, oldinstance, newinstance, skipcolumns=[]):
#----------------------------------------------------------------------
    '''
    update an existing element based on kwargs query
    
    :param session: session within which update occurs
    :param model: table model
    :param oldinstance: instance of table model which was found in the db
    :param newinstance: instance of table model with updated fields
    :param skipcolumns: list of column names to update
    :rtype: boolean indicates whether any fields have changed
    '''

    updated = False
    
    # update all columns except those we were told to skip
    for col in object_mapper(newinstance).columns:
        # skip indicated keys
        if col.key in skipcolumns: continue
        
        # if any columns are different, update those columns
        # and return to the caller that it's been updated
        if getattr(oldinstance,col.key) != getattr(newinstance,col.key):
            setattr(oldinstance,col.key,getattr(newinstance,col.key))
            updated = True
    
    return updated

#----------------------------------------------------------------------
def insert_or_update(session, model, newinstance, skipcolumns=[], **kwargs):
#----------------------------------------------------------------------
    '''
    insert a new element or update an existing element based on kwargs query
    
    :param session: session within which update occurs
    :param model: table model
    :param newinstance: instance of table model which is to become representation in the db
    :param skipcolumns: list of column names to skip checking for any changes
    :param kwargs: query criteria
    '''


    # get instance, if it exists
    instance = getunique(session,model,**kwargs)
    
    # remember if we update anything
    updated = False

    # found a matching object, may need to update some of its attributes
    if instance is not None:
        updated = update(session,model,instance,newinstance,skipcolumns)
    
    # new object, just add to database
    else:
        session.add(newinstance)
        updated = True

    if updated:
        session.flush()
        
    return updated
