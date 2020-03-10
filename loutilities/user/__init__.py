# pypi
from flask import Flask
from flask_security import Security, SQLAlchemyUserDatastore

# homegrown
from loutilities.configparser import getitems
from loutilities.user.model import User, Role

# hold application here
app = None
user_datastore = None

def create_app(config_obj, configfiles=None):
    '''
    apply configuration object, then configuration files
    '''
    global app
    app = Flask('loutilities')
    app.config.from_object(config_obj)
    if configfiles:
        # backwards compatibility
        if type(configfiles) == str:
            configfiles = [configfiles]
        for configfile in configfiles:
            appconfig = getitems(configfile, 'app')
            app.config.update(appconfig)

    from .model import db
    db.init_app(app)

    global user_datastore
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    security = Security(app, user_datastore)

    # need to force app context else get
    #    RuntimeError: Working outside of application context.
    #    RuntimeError: Attempted to generate a URL without the application context being pushed.
    # see http://kronosapiens.github.io/blog/2014/08/14/understanding-contexts-in-flask.html
    with app.app_context():
        # set up scoped session
        from sqlalchemy.orm import scoped_session, sessionmaker
        # the following code causes binds not to work, because the session is artificially
        # set to the base database engine via bind parameter
        # db.session = scoped_session(sessionmaker(autocommit=False,
        #                                          autoflush=False,
        #                                          bind=db.engine))
        # db.query = db.session.query_property()

    return app