###########################################################################################
# users_init - command line database initialization - clean database initialize users
#
#       Date            Author          Reason
#       ----            ------          ------
#       12/20/18        Lou King        Create
#
#   Copyright 2018 Lou King.  All rights reserved
###########################################################################################
'''
users_init - command line database initialization - clean database initialize users
=========================================================================================
run from 3 levels up, like python -m loutilities.user.scripts.users_init

'''
# standard
from os.path import join, dirname
from glob import glob
from shutil import rmtree
from csv import DictReader, DictWriter

# pypi

# homegrown
from loutilities.transform import Transform
from loutilities.user import create_app
from loutilities.user.settings import Development
from loutilities.user.model import db
from loutilities.user.applogging import setlogging
from loutilities.user.model import User, Role

class parameterError(Exception): pass

#--------------------------------------------------------------------------
def init_db(defineowner=True):
#--------------------------------------------------------------------------

    # must wait until user_datastore is initialized before import
    from loutilities.user import user_datastore
    from flask_security import hash_password

    # special processing for user roles because need to remember the roles when defining the owner
    # define user roles here
    userroles = [
        {'name':'super-admin',    'description':'everything'},
    ]

    # initialize roles, remembering what roles we have
    allroles = {}
    for userrole in userroles:
        rolename = userrole['name']
        allroles[rolename] = Role.query.filter_by(name=rolename).one_or_none() or user_datastore.create_role(**userrole)

    # define owner if desired
    if defineowner:
        from flask import current_app
        rootuser = current_app.config['APP_OWNER']
        rootpw = current_app.config['APP_OWNER_PW']
        name = current_app.config['APP_OWNER_NAME']
        given_name = current_app.config['APP_OWNER_GIVEN_NAME']
        owner = User.query.filter_by(email=rootuser).first()
        if not owner:
            owner = user_datastore.create_user(email=rootuser, password=hash_password(rootpw), name=name, given_name=given_name)
            for rolename in allroles:
                user_datastore.add_role_to_user(owner, allroles[rolename])
        db.session.flush()
        owner = User.query.filter_by(email=rootuser).one()

    # and we're done, let's accept what we did
    db.session.commit()

scriptdir = dirname(__file__)
# one level up
scriptfolder = dirname(scriptdir)
configdir = join(scriptfolder, 'config')
configfile = "users.cfg"
configpath = join(configdir, configfile)

# create app and get configuration
app = create_app(Development(configpath), configpath)

# set up database
db.init_app(app)

# set up scoped session
with app.app_context():
    # turn on logging
    setlogging()

    # clear and initialize the user database
    db.drop_all(bind='users')
    db.create_all(bind='users')
    init_db()
    db.session.commit()

