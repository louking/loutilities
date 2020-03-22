'''
tables - support tables for user package under loutilities
==============================================================
'''
# pypi
from flask import g, current_app
from flask_security import auth_required
from flask_security import current_user

# homegrown
from loutilities.tables import DbCrudApiRolePermissions
from loutilities.user.model import Interest

class ParameterError(Exception): pass

debug = False

class DbCrudApiInterestsRolePermissions(DbCrudApiRolePermissions):
    '''
    This class extends DbCrudApiRolePermissions. This extension uses flask_security
    to do role checking for the current user and managing Interests usage (see
    loutilities.user
    '''

    decorators = [auth_required()]

    def __init__(self, **kwargs):
        if debug: current_app.logger.debug('DbCrudApiInterestsRolePermissions.__init__()')

        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
                    local_interest_model=None,
                    )
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # Caller must use local_interest_model
        if not self.local_interest_model:
            raise ParameterError('local_interest_model required')

    def permission(self):
        '''
        check for permission on data
        :rtype: boolean
        '''
        if debug: print('DbCrudApiInterestsRolePermissions.permission()')

        # need to be logged in
        if not current_user.is_authenticated:
            return False

        # g.interest initialized in <project>.create_app.pull_interest
        # g.interest contains slug, pull in interest db entry. If not found, no permission granted
        self.interest = Interest.query.filter_by(interest=g.interest).one_or_none()
        if not self.interest:
            return False

        # check permissions allowed/permitted
        if not super().permission():
            return False

        # current_user has permissions. Can this user access current interest?
        if self.interest in current_user.interests:
            return True
        else:
            return False

    def beforequery(self):
        '''
        filter on current interest
        :return:
        '''
        # self.interest set in self.permission()
        # need to convert to id of local interest table for query
        self.localinterest = self.local_interest_model.query.filter_by(interest_id=self.interest.id).one()
        self.queryparams['interest_id'] = self.localinterest.id

    def createrow(self, formdata):
        '''
        creates row in database

        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        if debug: print('DbCrudApiInterestsRolePermissions.createrow()')

        # make sure we record the row's local interest id (self.localinterest set in self.beforequery())
        formdata['interest_id'] = self.localinterest.id

        # return the row
        row = super().createrow(formdata)

        return row

