'''
user - package supports user management for xtilities products
=========================================================================================
'''

# pypi
from flask import Flask, g
from flask_security import Security, SQLAlchemyUserDatastore, LoginForm, ForgotPasswordForm

# homegrown
from loutilities.configparser import getitems
from loutilities.user.model import User, Role

# hold application here
app = None
user_datastore = None

# TODO: should these messages be localized? See https://flask-security-too.readthedocs.io/en/stable/customizing.html#localization
user_messages = {
    'ACCOUNT_NOT_PERMITTED' : 'Account not permitted for this application'
}

# login_form for application management
class UserLoginForm(LoginForm):
    def validate(self):
        # if some error was detected from standard validate(), we're done
        if not super().validate():
            return False

        # if all ok otherwise, check roles to verify user allowed for this application
        ## collect applications
        apps = set()
        for thisrole in self.user.roles:
            apps |= set(thisrole.applications)
        ## disallow login if this app isn't in one of user's roles
        if g.loutility not in apps:
            self.email.errors.append(user_messages['ACCOUNT_NOT_PERMITTED'])
            return False

        return True

# forgot_password for application management
class UserForgotPasswordForm(ForgotPasswordForm):
    def validate(self):
        # if some error was detected from standard validate(), we're done
        if not super().validate():
            return False

        # if all ok otherwise, check roles to verify user allowed for this application
        ## collect applications
        apps = set()
        for thisrole in self.user.roles:
            apps |= set(thisrole.applications)
        ## disallow login if this app isn't in one of user's roles
        if g.loutility not in apps:
            self.email.errors.append(user_messages['ACCOUNT_NOT_PERMITTED'])
            return False

        return True

# extend flask_security.Security to support application verification
class UserSecurity(Security):
    def __init__(self, app=None, datastore=None, register_blueprint=True, **kwargs):
        '''
        replaces flask_security.Security

        add login_form=UserLoginForm if caller hasn't already supplied
        :param kwargs:
        '''
        if not 'login_form' in kwargs:
            kwargs['login_form'] = UserLoginForm
        if not 'forgot_password_form' in kwargs:
            kwargs['forgot_password_form'] = UserForgotPasswordForm
        return super().__init__(app, datastore, register_blueprint, **kwargs)

# used only for database initialization
# TODO: future use for loutilities.com landing page
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