'''
tables - support tables for user package under loutilities
==============================================================
'''
# standard
from urllib.parse import urlencode
from traceback import format_exception_only, format_exc

# pypi
from flask import g, current_app, url_for, jsonify
from flask.views import MethodView
from flask_security import auth_required
from flask_security import current_user
from sqlalchemy import Enum

# homegrown
from loutilities.tables import DbCrudApiRolePermissions, DteDbOptionsPickerBase
from loutilities.tables import SEPARATOR
from loutilities.user.model import Interest, db

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

    def saformurl(self, **kwargs):
        '''
        standalone form url
        '''
        # NOTE: keyword arguments need to match request.args access in self.get()
        args = urlencode(kwargs)
        # self.__name__ is endpoint -- see https://github.com/pallets/flask/blob/master/flask/views.py View.as_view method
        url = '{}/saformjs?{}'.format(url_for('.' + self.my_view.__name__, interest=g.interest), args)
        return url

    def saformpostjs(self, saeditor):
        '''
        this gives subclass ability to add additional javascript code to saformjs handler
        (see self.get elif request.path[-9:] == '/saformjs':)

        this code is added after standalone form created, as saeditor

        :param saeditor: name of variable which holds standalone form
        :return: list of additional javascript strings
        '''
        js = super().saformpostjs(saeditor)

        js += [
            # note groups_groupname and groups_groupselectselector will now match that which was
            # used for register_group_for_editor
            '  // add event handlers for this standalone editor (see groups.js)',
            '  {}.groups_groupname = editor.groups_groupname;'.format(saeditor),
            '  {}.groups_groupselectselector = editor.groups_groupselectselector;'.format(saeditor),
            '  set_editor_event_handlers({});'.format(saeditor),
        ]

        return js

class AssociationSelect(DteDbOptionsPickerBase):
    '''
    AssociationSelect builds on DteDbOptionsPickerBase, allowing use of
    https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html#association-object to
    add an Enum type selector for the relationship

    Additional parameters

    :param associationmodel: model class which contains [association object](https://docs.sqlalchemy.org/en/13/orm/basic_relationships.html#association-object)
    :param associationfields: list of fields in associationmodel used to update the record, must be Enum or subrecord
    :param selectattrs: list of attributes used to build select grouping. list order must match associationfields
            items must be Enum attribute (Enum) (uses Enum values) or table attribute (uses table values)

    Use of associationattr:

        # TODO: we'd like the select tree to look like this, but currently Editor does not support select2 with optgroup tag
        # select tree looks like
        #
        #     associationattr 1
        #         fieldmodel.id 1
        #         fieldmodel.id 2
        #             :
        #     associationattr 2
        #         fieldmodel.id 1
        #         fieldmodel.id 2
        #             :

        # associate task / taskfield tables adding association attribute "need"
        class TaskTaskField(Base):
            __tablename__ = 'task_taskfield'
            task_id             = Column(Integer, ForeignKey('task.id'), primary_key=True)
            taskfield_id        = Column(Integer, ForeignKey('taskfield.id'), primary_key=True)
            need                = Column(Enum('required', 'oneof', 'optional'))
            task                = relationship('Task', backref='fields')
            taskfield           = relationship('TaskField', backref='tasks')

        class Task(Base):
            __tablename__ = 'task'
            id                  = Column(Integer(), primary_key=True)
            interest_id         = Column(Integer, ForeignKey('localinterest.id'))
            interest            = relationship('LocalInterest', backref=backref('tasks'))
            task                = Column(String(TASK_LEN))

        class TaskField(Base):
            __tablename__ = 'taskfield'
            id                  = Column(Integer(), primary_key=True)
            interest_id         = Column(Integer, ForeignKey('localinterest.id'))
            interest            = relationship('LocalInterest', backref=backref('taskfields'))
            taskfield           = Column(String(TASKFIELD_LEN))
            fieldname           = Column(String(TASKFIELDNAME_LEN))

        taskfields = AssociationSelect(tablemodel=Task, fieldmodel=User, labelfield='name', formfield='users', dbfield='users', associationattr=TaskTaskField.need )
                        OR
        in configuration for DbCrudApiInterestsRolePermissions
            {'data': 'fields', 'name': 'fields', 'label': 'Fields',
             '_treatment': {
                 'relationship': {
                     'optionspicker':
                         AssociationSelect(
                             tablemodel=Task,
                             associationmodel=TaskTaskField,
                             associationtablemodelfield='task',
                             associationfields=['need', 'taskfield'],
                             selectattrs=[TaskTaskField.need, TaskField.taskfield],
                             labelfield='fields',
                             formfield='fields',
                             dbfield='fields', uselist=True,
                             queryparams=localinterest_query_params,
                         )
                 }}
             },


    '''
    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
            associationmodel=None,
            associationtablemodelfield=None,
            associationfields=[],
            selectattrs=[],
        )
        args.update(kwargs)

        # associationmodel = TaskTaskField,
        # associationfields = ['need', 'taskfield'],
        # selectattrs = [TaskTaskField.need, TaskField.taskfield],

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # some of the args are required
        reqdfields = ['associationmodel', 'associationtablemodelfield', 'associationfields', 'selectattrs', 'dbfield']
        for field in reqdfields:
            if not getattr(self, field, None):
                raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))
        if len(self.associationfields) != len(self.selectattrs):
            raise ParameterError('length of associationfields and selectattrs must be the same')

        # pick up options for the tree levels
        self.optionlevels = []
        for associationfield, selectattr in zip(self.associationfields, self.selectattrs):
            thislevel = {'associationfield':associationfield, 'selectattr': selectattr}
            if type(selectattr.type) == Enum:
                thislevel['options'] = selectattr.type.enums
                thislevel['ids'] = range(len(selectattr.type.enums))
            else:
                thislevel['model'] = selectattr.class_
                thislevel['key'] = selectattr.key

            self.optionlevels.append(thislevel)

    # def _setid(self, tablemodelitem, id):
    #     theassociation = self.associationmodel(**{self.associationtablemodelfield:tablemodelitem})
    def _setid(self, id):
        if not id: return None

        theassociation = self.associationmodel()
        db.session.add(theassociation)

        idparts = id.split('.')
        for optionlevel,idpart in zip(self.optionlevels,idparts):
            # have to look up the target if this level is a model
            if 'model' in optionlevel:
                thetarget = optionlevel['model'].query.filter_by(id=idpart).one()
            else:
                thetarget = optionlevel['options'][int(idpart)]
            setattr(theassociation, optionlevel['associationfield'], thetarget)
        return theassociation

    def set(self, formrow):
        if self.uselist:
            # accumulate list of database model instances
            items = []

            # return empty list if no items, rather than list with empty item
            # this allows for multiple keys in formrow[self.formfield], but seems like there'd only be one
            itemvalues = []
            for key in formrow[self.formfield]:
                vallist = formrow[self.formfield][key].split(SEPARATOR)
                # empty list is actually null list with one entry
                if len(vallist) == 1 and not vallist[0]: continue
                # loop through nonempty entries -- will we ever see null entry? hope not else exception on .one() call below
                for ndx in range(len(vallist)):
                    if len(itemvalues) < ndx + 1:
                        itemvalues.append(vallist[ndx])
                    else:
                        itemvalues[ndx].update(vallist[ndx])
            if debug: current_app.logger.debug('itemvalues={}'.format(itemvalues))
            for itemvalue in itemvalues:
                thisitem = self._setid(itemvalue)
                items.append(thisitem)
            return items
        else:
            itemvalue = formrow[self.formfield] if formrow[self.formfield] else None
            thisitem = self._setid(itemvalue)
            return thisitem

    def _getlabelvalue(self, theitem):
        thislabel = ''
        thisvalue = ''
        for optionlevel in self.optionlevels:
            # startup case, don't append separators
            if thislabel != '':
                thislabel += '/'
                thisvalue += '.'

            # check if retrieving from the database, otherwise use existing options
            if 'model' in optionlevel:
                # targetid = getattr(theitem, optionlevel['associationfield'])
                # thetarget = optionlevel['model'].query.filter_by(id=targetid).one()
                thetarget = getattr(theitem, optionlevel['associationfield'])
                thislabel += getattr(thetarget, optionlevel['key'])
                thisvalue += str(getattr(thetarget, 'id'))
            else:
                theoptions = optionlevel['options']
                thislabel += getattr(theitem, optionlevel['associationfield'])
                thisvalue += str(theoptions.index(thislabel))

        return thislabel, thisvalue

    def get(self, dbrow_or_id):
        if type(dbrow_or_id) in [int, str]:
            dbrow = self.tablemodel.query().filter_by(id=dbrow_or_id).one()

        else:
            dbrow = dbrow_or_id

        # get from database to form
        if self.uselist:
            items = {}
            labelitems = []
            valueitems = []
            for item in getattr(dbrow, self.dbfield):
                thislabel,thisvalue = self._getlabelvalue(item)

                labelitems.append(thislabel)
                valueitems.append(thisvalue)

            items = {self.labelfield: SEPARATOR.join(labelitems), self.valuefield: SEPARATOR.join(valueitems)}
            return items
        else:
            # get the attribute if specified
            theitem = getattr(dbrow, self.dbfield)
            if theitem:
                thislabel, thisvalue = self._getlabelvalue(theitem)
                item = {self.labelfield: thislabel, self.valuefield: thisvalue}
                return item

            # otherwise return None
            else:
                return {self.labelfield: None, self.valuefield: None}

    def options(self):
        '''
        return sorted list of items in the model, may be overridden for more complex models

        :return: options as expected by optionpicker type,
            e.g., for select2 list of {'label': label, 'value': value} (see https://select2.org/options)
        '''
        queryparams = self.queryparams() if callable(self.queryparams) else self.queryparams
        items = [{'label':'', 'value':''}]

        for optionlevel in self.optionlevels:
            # overwrite options if retrieving from the database, otherwise use existing options
            if 'model' in optionlevel:
                optionsids = [(getattr(r,optionlevel['key']),getattr(r,'id'))
                              for r in optionlevel['model'].query
                                  .filter_by(**queryparams)
                                  .order_by(optionlevel['selectattr'])
                                  .all()]
                optionlevel['options'] = [oi[0] for oi in optionsids]
                optionlevel['ids'] = [oi[1] for oi in optionsids]

            # distribute these options across existing items
            theseitems = []
            for item in items:
                thislabel = item['label']
                thisvalue = item['value']
                # startup case, don't append separators
                if thislabel != '':
                    thislabel += '/'
                    thisvalue += '.'
                for option,id_ in zip(optionlevel['options'],optionlevel['ids']):
                    theseitems.append({'label':thislabel+option, 'value':thisvalue+str(id_)})
            items = theseitems

        if self.nullable:
            items =[{'label': '<none>', 'value': None}] + items

        return items

    def new_plus_options(self):
        '''
        return sorted list of items in the model, with first option being <new>

        :return:
        '''
        items = [{'label': '<new>', 'value': 0}] + self.options()
        return items

    def col_options(self):
        '''
        return additional column options required by the caller

        :return:
        '''
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
                       'multiple': self.uselist,
                       'placeholder': None if self.uselist else '(select)'}
        if self.uselist:
            col['separator'] = SEPARATOR
        return col

class AssociationCrudApi(DbCrudApiInterestsRolePermissions):
    '''
    AssociationCrudApi MUST be used with AssociationSelect. This allows DbCrudApi... to update
    the association with the self.model instance, which isn't visible to AssociationSelect

    Additional parameters

    :param assnmodelfield: field in Association definition which points to the self.model dbrow being edited
    :param assnlistfield: field in self.model which has association record list or association record
    '''
    def __init__(self, **kwargs):

        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(
            assnlistfield=None,
            assnmodelfield=None,
        )
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super().__init__(**args)

        # Caller should use roles_accepted OR roles_required but not both
        reqdfields = ['assnlistfield', 'assnmodelfield']
        for field in reqdfields:
            if not getattr(self, field, None):
                raise ParameterError('{} are all required'.format(reqdfields))

    def updaterow(self, thisid, formdata):
        '''
        update assnlistfield in self.model, and assnmodelfield in AssociationSelect.associationmodel
        '''
        dbrow = self.model.query.filter_by(id=thisid).one()

        # get handy access to the association list field
        assnfield = getattr(dbrow, self.assnlistfield)

        # first delete all the items in assnlistfield
        for i in range(len(assnfield)):
            assnrow = assnfield.pop(0)
            db.session.delete(assnrow)

        # this adds the current fields list
        notused = super().updaterow(thisid, formdata)

        # now need to add this task to the tasktaskfield associations
        for assnrow in assnfield:
            setattr(assnrow, self.assnmodelfield, dbrow)

        return self.dte.get_response_data(dbrow)


class DbPermissionsMethodViewApi(MethodView):
    """
    method view which checks permissions, for apis

    :param app: app or blueprint this view belongs to
    :param db: database object a la sqlalchemy
    :param roles_accepted: list of roles accepted for this view
    :param endpoint: endpoint parameter used by flask.url_for()
    :param rule: rule parameter used by flask.add_url_rule()
    :param methods: sequence of HTTP methods the url rule applies to
    """
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        args = dict(
            app=None,
            db=None,
            roles_accepted=None,
            endpoint=None,
            rule=None,
            methods=None,
        )
        args.update(kwargs)

        # make arguments into attributes
        for key in args:
            setattr(self, key, args[key])

    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        allowed = False

        # g.interest initialized in <project>.create_app.pull_interest
        # g.interest contains slug, pull in interest db entry. If not found, no permission granted
        interest = Interest.query.filter_by(interest=g.interest).one_or_none()

        # need to be logged in, and allowed to use this interest
        if current_user.is_authenticated and interest and interest in current_user.interests:
            # check permissions allowed/permitted
            for role in self.roles_accepted:
                if current_user.has_role(role):
                    allowed = True
                    break

        return allowed

    def get(self):
        try:
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            response = self.do_get()
            db.session.commit()
            return response

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def do_get(self):
        raise NotImplementedError

    def post(self):
        try:
            if not self.permission():
                db.session.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            response = self.do_post()
            db.session.commit()
            return response

        except Exception as e:
            exc = ''.join(format_exception_only(type(e), e))
            output_result = {'status': 'fail', 'error': 'exception occurred:<br>{}'.format(exc)}
            # roll back database updates and close transaction
            db.session.rollback()
            current_app.logger.error(format_exc())
            return jsonify(output_result)

    def do_post(self):
        raise NotImplementedError

    def register(self):
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        self.my_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule(self.rule, view_func=self.my_view, methods=self.methods)

