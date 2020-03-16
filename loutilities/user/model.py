###########################################################################################
# model - database model for common users database
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/02/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
###########################################################################################

# pypi
from flask_sqlalchemy import SQLAlchemy
from flask_security import UserMixin, RoleMixin

# set up database - SQLAlchemy() must be done after app.config SQLALCHEMY_* assignments
db = SQLAlchemy()
Table = db.Table
Column = db.Column
Integer = db.Integer
Float = db.Float
Boolean = db.Boolean
String = db.String
Text = db.Text
Date = db.Date
Time = db.Time
DateTime = db.DateTime
Sequence = db.Sequence
Enum = db.Enum
UniqueConstraint = db.UniqueConstraint
ForeignKey = db.ForeignKey
relationship = db.relationship
backref = db.backref
object_mapper = db.object_mapper
Base = db.Model

# some string sizes
DESCR_LEN = 512
INTEREST_LEN = 32
APPLICATION_LEN = 32
# role management, some of these are overloaded
USERROLEDESCR_LEN = 512
ROLENAME_LEN = 32
EMAIL_LEN = 100
NAME_LEN = 256
PASSWORD_LEN = 255
UNIQUIFIER_LEN = 255

# applications
APP_CONTRACTS = 'contracts'
APP_MEMBERS = 'members'
APP_ROUTES = 'routes'
APP_SCORES = 'scores'
APP_ALL = [APP_CONTRACTS, APP_MEMBERS, APP_ROUTES, APP_SCORES]

userinterest_table = Table('users_interests', Base.metadata,
                           Column('user_id', Integer, ForeignKey('user.id')),
                           Column('interest_id', Integer, ForeignKey('interest.id')),
                           info={'bind_key': 'users'},
                          )

appinterest_table = Table('apps_interests', Base.metadata,
                           Column('application_id', Integer, ForeignKey('application.id')),
                           Column('interest_id', Integer, ForeignKey('interest.id')),
                           info={'bind_key': 'users'},
                          )

approle_table = Table('apps_roles', Base.metadata,
                           Column('application_id', Integer, ForeignKey('application.id')),
                           Column('role_id', Integer, ForeignKey('role.id')),
                           info={'bind_key': 'users'},
                          )

class Interest(Base):
    __tablename__ = 'interest'
    __bind_key__ = 'users'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    interest            = Column(String(INTEREST_LEN))
    users               = relationship("User",
                                       secondary=userinterest_table,
                                       backref=backref("interests"))
    applications        = relationship("Application",
                                       secondary=appinterest_table,
                                       backref=backref("interests"))
    description         = Column(String(DESCR_LEN))
    public              = Column(Boolean)

class Application(Base):
    __tablename__ = 'application'
    __bind_key__ = 'users'
    id              = Column(Integer(), primary_key=True)
    version_id      = Column(Integer, nullable=False, default=1)
    application     = Column(String(APPLICATION_LEN))

# user role management
# adapted from
#   https://flask-security-too.readthedocs.io/en/stable/quickstart.html (SQLAlchemy Application)

class RolesUsers(Base):
    __tablename__ = 'roles_users'
    __bind_key__ = 'users'
    id = Column(Integer(), primary_key=True)
    user_id = Column('user_id', Integer(), ForeignKey('user.id'))
    role_id = Column('role_id', Integer(), ForeignKey('role.id'))

class Role(Base, RoleMixin):
    __tablename__ = 'role'
    __bind_key__ = 'users'
    id                  = Column(Integer(), primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    name                = Column(String(ROLENAME_LEN), unique=True)
    description         = Column(String(USERROLEDESCR_LEN))
    applications        = relationship("Application",
                                       secondary=approle_table,
                                       backref=backref("roles"))

class User(Base, UserMixin):
    __tablename__ = 'user'
    __bind_key__ = 'users'
    id                  = Column(Integer, primary_key=True)
    version_id          = Column(Integer, nullable=False, default=1)
    email               = Column( String(EMAIL_LEN), unique=True )  # = username
    password            = Column( String(PASSWORD_LEN) )
    name                = Column( String(NAME_LEN) )
    given_name          = Column( String(NAME_LEN) )
    last_login_at       = Column( DateTime() )
    current_login_at    = Column( DateTime() )
    last_login_ip       = Column( String(100) )
    current_login_ip    = Column( String(100) )
    login_count         = Column( Integer )
    active              = Column( Boolean() )
    fs_uniquifier       = Column( String(UNIQUIFIER_LEN) )
    confirmed_at        = Column( DateTime() )
    roles               = relationship('Role', secondary='roles_users',
                          backref=backref('users', lazy='dynamic'))

class ManageLocalTables():
    def __init__(self, db, appname, localusermodel, localinterestmodel):
        '''
        operations on localuser model for callers of User model

        :param db: SQLAlchemy instance used by caller
        :param appname: name of application, must match Application.application
        :param localusermodel: model class for User, in the slave database
        :param localinterestmodel: model class for Interest, in the slave database
        '''
        self.db = db
        self.localusermodel = localusermodel
        # see https://stackoverflow.com/questions/21301452/get-table-name-by-table-class-in-sqlalchemy
        self.localusertable = localusermodel.__table__.name
        self.localinterestmodel = localinterestmodel
        self.localinteresttable = localinterestmodel.__table__.name

        self.application = Application.query.filter_by(application=appname).one()

    def _updateuser(self):
        # don't try to update before table exists
        if not db.engine.has_table(self.localusertable): return

        # alllocal will be used to determine what localuser model rows need to be deactivated
        # this detects deletions in User table

        alllocal = {}
        for localuser in self.localusermodel.query.all():
            alllocal[localuser.user_id] = localuser
        for user in User.query.all():
            # remove from deactivate list; update active status
            if user.id in alllocal:
                localuser = alllocal.pop(user.id)
                localuser.active = user.active
            # needs to be added
            else:
                newlocal = self.localusermodel(user_id=user.id, active=user.active)
                self.db.session.add(newlocal)
        # all remaining in alllocal need to be deactivated
        for user_id in alllocal:
            localuser = self.localusermodel.query.filter_by(user_id=user_id).one()
            localuser.active = False

    def _updateinterest(self):
        # don't try to update before table exists
        if not db.engine.has_table(self.localinteresttable): return

        # alllocal will be used to determine what localinterest model rows need to be deleted
        # this detects deletions in Interest table
        alllocal = {}
        for localinterest in self.localinterestmodel.query.all():
            alllocal[localinterest.interest_id] = localinterest
        for interest in Interest.query.all():
            # if this interest isn't for this application, ignore
            if self.application not in interest.applications: continue

            # remove from delete list; update active status
            if interest.id in alllocal:
                discard = alllocal.pop(interest.id)
            # needs to be added
            else:
                newlocal = self.localinterestmodel(interest_id=interest.id)
                self.db.session.add(newlocal)
        # all remaining in alllocal need to be deleted
        for interest_id in alllocal:
            localinterest = self.localinterestmodel.query.filter_by(interest_id=interest_id).one()
            self.db.session.delete(localinterest)

    def update(self):
        '''
        keep localuser and localinterest tables consistent with external db User table
        '''
        self._updateuser()
        self._updateinterest()
        self.db.session.commit()