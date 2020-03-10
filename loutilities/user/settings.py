###########################################################################################
# settings - define default, test and production settings
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/06/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
#
###########################################################################################
'''
settings - define default, test and production settings

see http://flask.pocoo.org/docs/1.0/config/?highlight=production#configuration-best-practices
'''

# standard
import logging

# homegrown
from loutilities.configparser import getitems


class Config(object):
    DEBUG = False
    TESTING = False

    # default database
    # https://flask-sqlalchemy.palletsprojects.com/en/2.x/binds/
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_BINDS = {
        'users': 'sqlite:///:memory:',
    }

    # logging
    LOGGING_LEVEL_FILE = logging.INFO
    LOGGING_LEVEL_MAIL = logging.ERROR

    # flask-security configuration -- see https://pythonhosted.org/Flask-Security/configuration.html
    SECURITY_TRACKABLE = True
    SECURITY_DEFAULT_REMEMBER_ME = True

    # avoid warning
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class Testing(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False

    # need to set SERVER_NAME to something, else get a RuntimeError about not able to create URL adapter
    # must have following line in /etc/hosts or C:\Windows\System32\drivers\etc\hosts file
    #   127.0.0.1 dev.localhost
    SERVER_NAME = 'dev.localhost'

    # need a default secret key - in production replace by config file
    SECRET_KEY = "<test secret key>"

    # need to allow logins in flask-security. see https://github.com/mattupstate/flask-security/issues/259
    LOGIN_DISABLED = False


class RealDb(Config):
    def __init__(self, configfiles):
        if type(configfiles) == str:
            configfiles = [configfiles]

        # connect to database based on configuration
        config = {}
        for configfile in configfiles:
            config.update(getitems(configfile, 'database'))

        # https://flask-sqlalchemy.palletsprojects.com/en/2.x/binds/
        userdbuser = config['userdbuser']
        userpassword = config['userdbpassword']
        userdbserver = config['userdbserver']
        userdbname = config['userdbname']
        userdb_uri = 'mysql://{uname}:{pw}@{server}/{dbname}'.format(uname=userdbuser, pw=userpassword, server=userdbserver,
                                                                 dbname=userdbname)
        self.SQLALCHEMY_BINDS = {
            'users': userdb_uri
        }


class Development(RealDb):
    DEBUG = True


class Production(RealDb):
    pass


