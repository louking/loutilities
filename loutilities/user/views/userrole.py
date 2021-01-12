###########################################################################################
# userrole - manage application users and roles
#
#       Date            Author          Reason
#       ----            ------          ------
#       12/08/19        Lou King        Create
#
#   Copyright 2019 Lou King
#
###########################################################################################
'''
userrole - manage application users and roles
====================================================
'''

# standard

# pypi
from validators.slug import slug
from validators.email import email
from flask import g, request
from flask_security.recoverable import send_reset_password_instructions

# homegrown
from . import bp
from loutilities.user.model import db, User, Role, Interest, Application
from loutilities.tables import DbCrudApiRolePermissions, get_request_action, SEPARATOR
from loutilities.timeu import asctime

ymdtime = asctime('%Y-%m-%d %H:%M:%S')

##########################################################################################
# users endpoint
###########################################################################################

user_dbattrs = 'id,email,name,given_name,roles,interests,last_login_at,current_login_at,last_login_ip,current_login_ip,login_count,active'.split(',')
user_formfields = 'rowid,email,name,given_name,roles,interests,last_login_at,current_login_at,last_login_ip,current_login_ip,login_count,active'.split(',')
user_dbmapping = dict(zip(user_dbattrs, user_formfields))
user_formmapping = dict(zip(user_formfields, user_dbattrs))

user_formmapping['last_login_at'] = lambda dbrow: ymdtime.dt2asc(dbrow.last_login_at) if dbrow.last_login_at else ''
user_formmapping['current_login_at'] = lambda dbrow: ymdtime.dt2asc(dbrow.current_login_at) if dbrow.current_login_at else ''

def user_validate(action, formdata):
    results = []

    if formdata['email'] and not email(formdata['email']):
        results.append({ 'name' : 'email', 'status' : 'invalid email: correct format is like john.doe@example.com' })

    # check apps which user will have access to
    apps = set()
    if formdata['roles'] and 'id' in formdata['roles'] and formdata['roles']['id'] != '':
        roleidsstring = formdata['roles']['id']
        roleids = roleidsstring.split(SEPARATOR)
        for roleid in roleids:
            thisrole = Role.query.filter_by(id=roleid).one()
            apps |= set(thisrole.applications)

    # this app must be one of user's roles
    if g.loutility not in apps:
        # need to use name='roles.id' because this field is _treatment:{relationship}
        results.append({'name': 'roles.id', 'status': 'give user at least one role which works for this application'})

    return results

class UserCrudApi(DbCrudApiRolePermissions):

    def createrow(self, formdata):
        '''
        createrow is used by create form, may need to also send password reset request to user.
        comes from tables-assets/static/user/admin/beforedatatables.js user_create_send_notification_button()

        :param formdata: data from form
        :return:
        '''
        # return the row
        row = super().createrow(formdata)

        # admin may have requested password reset email be sent to the user
        if 'resetpw' in request.form:
            user = User.query.filter_by(id=self.created_id).one()
            send_reset_password_instructions(user)

        return row

    def updaterow(self, thisid, formdata):
        '''
        updaterow is used by edit form, may need to also send password reset request to user.
        comes from tables-assets/static/user/admin/beforedatatables.js reset_password_button()

        :param thisid: id of user
        :param formdata: edit form
        :return: row data
        '''
        if 'resetpw' in request.form:
            user = User.query.filter_by(id=thisid).one()
            send_reset_password_instructions(user)
        return super().updaterow(thisid, formdata)

class UserView(UserCrudApi):
    def __init__(self, **kwargs):
        '''
        application MUST instantiate UserView

        application should override editor_method_postcommit(self, form) to call
        loutilities.model.ManageLocalUser(db, appname, localusermodel, localinterestmodel).update()
        '''
        self.kwargs = kwargs
        args = dict(
            app=bp,  # use blueprint instead of app
            db=db,
            model=User,
            version_id_col='version_id',  # optimistic concurrency control
            roles_accepted='super-admin',
            template='datatables.jinja2',
            pagename='users',
            endpoint='userrole.users',
            rule='/users',
            dbmapping=user_dbmapping,
            formmapping=user_formmapping,
            clientcolumns=[
                {'data': 'email', 'name': 'email', 'label': 'Email', '_unique': True,
                 'className': 'field_req',
                 },
                {'data': 'given_name', 'name': 'given_name', 'label': 'First Name',
                 'className': 'field_req',
                 },
                {'data': 'name', 'name': 'name', 'label': 'Full Name',
                 'className': 'field_req',
                 },
                {'data': 'roles', 'name': 'roles', 'label': 'Roles',
                 '_treatment': {'relationship': {'fieldmodel': Role, 'labelfield': 'name', 'formfield': 'roles',
                                                 'dbfield': 'roles', 'uselist': True}}
                 },
                {'data': 'interests', 'name': 'interests', 'label': 'Interests',
                 '_treatment': {'relationship': {'fieldmodel': Interest, 'labelfield': 'description',
                                                 'formfield': 'interests', 'dbfield': 'interests',
                                                 'uselist': True}}
                 },
                {'data': 'active', 'name': 'active', 'label': 'Active',
                 '_treatment': {'boolean': {'formfield': 'active', 'dbfield': 'active'}},
                 'ed': {'def': 'yes'},
                 },
                {'data': 'last_login_at', 'name': 'last_login_at', 'label': 'Last Login At',
                 'className': 'dt-body-nowrap',
                 'type': 'readonly'
                 },
                {'data': 'current_login_at', 'name': 'current_login_at', 'label': 'Current Login At',
                 'className': 'dt-body-nowrap',
                 'type': 'readonly',
                 },
                {'data': 'last_login_ip', 'name': 'last_login_ip', 'label': 'Last Login IP', 'type': 'readonly'},
                {'data': 'current_login_ip', 'name': 'current_login_ip', 'label': 'Current Login IP',
                 'type': 'readonly'
                 },
                {'data': 'login_count', 'name': 'login_count', 'label': 'Login Count', 'type': 'readonly'},
            ],
            validate=user_validate,
            servercolumns=None,  # not server side
            idSrc='rowid',
            buttons=[{
                         'extend': 'create',
                         'editor': {'eval': 'editor'},
                         'formButtons': [
                             {'text': 'Create and Send', 'action': {'eval': 'user_create_send_notification_button'}},
                             {'text': 'Create', 'action': {'eval': 'submit_button'}},
                         ]
                     },
                     {
                         'extend': 'editRefresh',
                         'text': 'Edit',
                         'editor': {'eval': 'editor'},
                         'formButtons': [
                             {'text': 'Reset Password', 'action': {'eval': 'reset_password_button'}},
                             {'text': 'Update', 'action': {'eval': 'submit_button'}},
                         ]
                     },
            ],
            dtoptions={
                'scrollCollapse': True,
                'scrollX': True,
                'scrollXInner': "100%",
                'scrollY': True,
            },
        )
        args.update(kwargs)
        super().__init__(**args)


##########################################################################################
# roles endpoint
###########################################################################################

role_dbattrs = 'id,name,description,applications'.split(',')
role_formfields = 'rowid,name,description,applications'.split(',')
role_dbmapping = dict(zip(role_dbattrs, role_formfields))
role_formmapping = dict(zip(role_formfields, role_dbattrs))

class RoleView(DbCrudApiRolePermissions):
    def __init__(self, **kwargs):
        '''
        application MUST instantiate RoleView

        application should override editor_method_postcommit(self, form) to call
        loutilities.model.ManageLocalUser(db, appname, localusermodel, localinterestmodel).update()
        '''
        self.kwargs = kwargs
        args = dict(
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Role, 
                    version_id_col = 'version_id',  # optimistic concurrency control
                    roles_accepted = 'super-admin',
                    template = 'datatables.jinja2',
                    pagename = 'roles', 
                    endpoint = 'userrole.roles',
                    rule = '/roles',
                    dbmapping = role_dbmapping, 
                    formmapping = role_formmapping, 
                    clientcolumns = [
                        { 'data': 'name', 'name': 'name', 'label': 'Name',
                          'className': 'field_req',
                          },
                        { 'data': 'description', 'name': 'description', 'label': 'Description' },
                        {'data': 'applications', 'name': 'applications', 'label': 'Applications',
                         '_treatment': {'relationship': {'fieldmodel': Application, 'labelfield': 'application',
                                                         'formfield': 'applications', 'dbfield': 'applications',
                                                         'uselist': True}}
                         },
                    ],
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['create', 'editRefresh', 'remove'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
        args.update(kwargs)
        super().__init__(**args)

##########################################################################################
# interests endpoint
###########################################################################################

interest_dbattrs = 'id,interest,description,users,public,applications'.split(',')
interest_formfields = 'rowid,interest,description,users,public,applications'.split(',')
interest_dbmapping = dict(zip(interest_dbattrs, interest_formfields))
interest_formmapping = dict(zip(interest_formfields, interest_dbattrs))

def interest_validate(action, formdata):
    results = []

    for field in ['interest']:
        if formdata[field] and not slug(formdata[field]):
            results.append({ 'name' : field, 'status' : 'invalid slug: must be only alpha, numeral, hyphen' })

    return results

class InterestView(DbCrudApiRolePermissions):
    def __init__(self, **kwargs):
        '''
        application MUST instantiate InterestView

        application should override editor_method_postcommit(self, form) to call
        loutilities.model.ManageLocalUser(db, appname, localusermodel, localinterestmodel).update()
        '''
        self.kwargs = kwargs
        args = dict(
            app=bp,  # use blueprint instead of app
            db=db,
            model=Interest,
            version_id_col='version_id',  # optimistic concurrency control
            interests_accepted='super-admin',
            template='datatables.jinja2',
            pagename='interests',
            endpoint='userrole.interests',
            rule='/interests',
            dbmapping=interest_dbmapping,
            formmapping=interest_formmapping,
            clientcolumns=[
                {'data': 'description', 'name': 'description', 'label': 'Description', '_unique': True,
                 'className': 'field_req',
                 },
                {'data': 'interest', 'name': 'interest', 'label': 'Slug', '_unique': True,
                 'className': 'field_req',
                 },
                {'data': 'public', 'name': 'public', 'label': 'Public',
                 '_treatment': {'boolean': {'formfield': 'public', 'dbfield': 'public'}},
                 'ed': {'def': 'yes'},
                 },
                {'data': 'applications', 'name': 'applications', 'label': 'Applications',
                 '_treatment': {'relationship': {'fieldmodel': Application, 'labelfield': 'application',
                                                 'formfield': 'applications', 'dbfield': 'applications',
                                                 'uselist': True}}
                 },
                {'data': 'users', 'name': 'users', 'label': 'Users',
                 '_treatment': {'relationship': {'fieldmodel': User, 'labelfield': 'email',
                                                 'formfield': 'users', 'dbfield': 'users',
                                                 'uselist': True}}
                 },
            ],
            validate=interest_validate,
            servercolumns=None,  # not server side
            idSrc='rowid',
            buttons=['create', 'editRefresh', 'remove'],
            dtoptions={
                'scrollCollapse': True,
                'scrollX': True,
                'scrollXInner': "100%",
                'scrollY': True,
            },
        )
        args.update(kwargs)
        super().__init__(**args)

##########################################################################################
# applications endpoint
###########################################################################################

application_dbattrs = 'id,application'.split(',')
application_formfields = 'rowid,application'.split(',')
application_dbmapping = dict(zip(application_dbattrs, application_formfields))
application_formmapping = dict(zip(application_formfields, application_dbattrs))

def application_validate(action, formdata):
    results = []

    for field in ['application']:
        if formdata[field] and not slug(formdata[field]):
            results.append({ 'name' : field, 'status' : 'invalid slug: must be only alpha, numeral, hyphen' })

    return results

application = DbCrudApiRolePermissions(
                    app = bp,   # use blueprint instead of app
                    db = db,
                    model = Application,
                    version_id_col = 'version_id',  # optimistic concurrency control
                    applications_accepted = 'super-admin',
                    template = 'datatables.jinja2',
                    pagename = 'applications', 
                    endpoint = 'userrole.applications',
                    rule = '/applications',
                    dbmapping = application_dbmapping, 
                    formmapping = application_formmapping, 
                    clientcolumns = [
                        { 'data': 'application', 'name': 'application', 'label': 'Application', '_unique': True,
                          'className': 'field_req',
                          },
                    ],
                    validate = application_validate,
                    servercolumns = None,  # not server side
                    idSrc = 'rowid', 
                    buttons = ['create', 'editRefresh', 'remove'],
                    dtoptions = {
                                        'scrollCollapse': True,
                                        'scrollX': True,
                                        'scrollXInner': "100%",
                                        'scrollY': True,
                                  },
                    )
application.register()

