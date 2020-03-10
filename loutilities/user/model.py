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

# common roles
ROLE_SUPER_ADMIN = 'super-admin'

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
