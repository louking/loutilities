###########################################################################################
#
#       Date            Author          Reason
#       ----            ------          ------
#       02/08/16        Lou King        Create
#
#   Copyright 2016 Lou King.  All rights reserved
###########################################################################################

# standard
from collections import defaultdict
import traceback
from copy import deepcopy, copy
from json import dumps
from urllib.parse import urlencode
from threading import RLock
import sys
import json
from traceback import format_exception_only, format_exc

# pypi
import flask
from flask import request, jsonify, url_for, current_app, make_response
from flask.views import MethodView
from sqlalchemy import func, types, cast
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm.attributes import InstrumentedAttribute
from datatables import DataTables as BaseDataTables, ColumnDT
from jinja2 import Template
from formencode.validators import TimeConverter
from formencode import Invalid

# homegrown
from loutilities.nesteddict import NestedDict

class ParameterError(Exception): pass
class NotImplementedError(Exception): pass
class staleData(Exception): pass

debug = False

# separator for select2 tag list
SEPARATOR = ', '

# child row management
CHILDROW_TYPE_TABLE = '_table'

#####################################################
# for use in validation functions
#####################################################

# https://www.regextester.com/93652 - modified to allow upper case
REGEX_URL = r"^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-zA-Z0-9]+([\-\.]{1}[a-zA-Z0-9]+)*\.[a-zA-Z]{2,5}(:[0-9]{1,5})?(\/.*)?$"

# https://www.regular-expressions.info/email.html
REGEX_EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$"

# https://stackoverflow.com/questions/17564088/how-to-form-a-regex-to-recognize-correct-declaration-of-variable-names
REGEX_VBL = r"^[a-zA-Z_$][a-zA-Z_$0-9]*$"

# https://regexr.com/37l5c
REGEX_ISODATE = r"(19|20)\d\d-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"

#####################################################
# for use in ColumnDT declarations
#####################################################
class RenderBoolean(TypeDecorator):
    impl = types.Boolean

    def __init__(self, *args, **kwargs):
        # set arguments as class attributes
        # ignore all but truedisplay, falsedisplay
        self.truedisplay = kwargs.pop('truedisplay')
        self.falsedisplay = kwargs.pop('falsedisplay')
        super(RenderBoolean, self).__init__(*args, **kwargs)

    def process_result_value(self, value, engine):
        # value should be '0' or '1'
        return self.truedisplay if int(value) else self.falsedisplay

    def process_bind_param(self, value, dialect):
        return value == self.truedisplay

def renderboolean(expr, *args, **kwargs):
    return cast(expr, RenderBoolean(*args, **kwargs))


def is_jsonable(x):
    '''
    returns true if json serializable

    :param x: object to check
    :return: True if json serializable
    '''
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError) as e:
        return False


def copyopts(opts):
    '''
    deep copy of dictionary options, json serializable
    if an option wasn't serializable it gets turned into a string

    :param opts: dict or scalar
    :return: json serializable dict or scalar
    '''
    if isinstance(opts, list):
        newopts = []
        for i in opts:
            newopts.append(copyopts(i))
    elif isinstance(opts, dict):
        newopts = {}
        for f in opts:
            newopts[f] = copyopts(opts[f])
    else:
        if is_jsonable(opts):
            newopts = opts
        else:
            # what should we do here?
            newopts = str(opts)

    return newopts


def get_dbattr(basemodel, attrstring):
    '''
    get a database attribute for a string which may have multiple levels

    :param basemodel: top level model under which attrstring should be found
    :param attrstring: dotted notation attribute; dots allow traversal of multiple levels
    :return: bottom level attribute value
    '''

    attrs = attrstring.split('.')
    thismodel = basemodel

    while len(attrs) > 1:
        thisattr = attrs.pop(0)
        thismodel = type(getattr(thismodel, thisattr))

    attr = attrs.pop(0)
    return getattr(thismodel, attr)

def dt_editor_response(**respargs):
    '''
    build response for datatables editor
    
    :param respargs: arguments for response
    :rtype: json response
    '''

    return flask.jsonify(**respargs)


def get_request_action(form):
    # TODO: modify get_request_action and get_request_data to allow either request object or form object,
    # and remove if/else for formrequest, e.g., action = get_request_action(request)
    # (allowing form object deprecated for legacy code)
    '''
    return dict list with data from request.form

    :param form: MultiDict from `request.form`
    :rtype: action - 'create', 'edit', or 'remove'
    '''
    if 'action' in form:
        return form['action']
    else:
        return None

def get_request_data(form):
    # TODO: modify get_request_action and get_request_data to allow either request object or form object,
    # and remove if/else for formrequest, e.g., action = get_request_action(request)
    # (allowing form object deprecated for legacy code)
    '''
    return dict list with data from request.form

    :param form: MultiDict from `request.form`
    :rtype: {id1: {field1:val1, ...}, ...} [fieldn and valn are strings]
    '''

    # request.form comes in multidict [('data[id][field]',value), ...]
    
    # fill in id field automatically
    data = defaultdict(lambda: {})

    # fill in data[id][field] = value
    for formkey in list(form.keys()):
        # if formkey == 'action': continue
        if formkey[0:5] != 'data[': continue

        formlineitems = formkey.split('[')
        datapart,idpart = formlineitems[0:2]
        # if datapart != 'data': raise ParameterError, "invalid input in request: {}".format(formkey)

        # try to coerce to int, but accept as string
        # this allows complex ids to be used, but is backwards compatible for integer ids
        try:
            idvalue = int(idpart[0:-1])
        except ValueError:
            idvalue = idpart[0:-1]

        # the rest of it is the field structure, may have been [a], [a][b], etc before splitting at '['
        fieldparts = [part[0:-1] for part in formlineitems[2:]]

        # use NestedDict to handle arbitrary data field tree structure
        fieldkey = '.'.join(fieldparts)
        fieldlevels = NestedDict()
        fieldlevels[fieldkey] = form[formkey]
        data[idvalue].update(fieldlevels.to_dict())

        if debug:
            from pprint import PrettyPrinter
            pp = PrettyPrinter()
            current_app.logger.debug('get_request_data(): formkey={} data={}'.format(formkey, pp.pformat(data)))

    # return decoded result
    return data

def rest_url_for(endpoint, urlargs={}, **kwargs):
    """
    get the REST url for an endpoint, with optional arguments

    :param endpoint:  endpoint to be supplied to url_for
    :param urlargs: dict with arguments to be added to url
    :param kwargs: url_for keyword arguments
    :return:
    """
    url = url_for(endpoint, **kwargs)
    # for some reason, url_for sometimes give /rest url and sometimes doesn't
    while url[-5:] == '/rest':
        url = url[0:-5]
    url += '/rest'
    if urlargs:
        url += '?' + urlencode(urlargs)
    return url

def page_url_for(endpoint, urlargs={}, _external=False, **kwargs):
    """
    get the page url for an endpoint, with optional arguments

    :param endpoint:  endpoint to be supplied to url_for
    :param urlargs: dict with arguments to be added to url
    :param kwargs: url_for keyword arguments
    :return:
    """
    url = url_for(endpoint, _external=_external, **kwargs)
    # for some reason, url_for sometimes give /rest url and sometimes doesn't
    while url[-5:] == '/rest':
        url = url[0:-5]
    if urlargs:
        url += '?' + urlencode(urlargs)
    return url

# monkey patch yadcf_range_number search method
def alt_yadcf_range_number(expr, value):
    v_from, v_to = value.split('-yadcf_delim-')
    v_from = float(v_from) if v_from != '' else -sys.maxsize+1 # was float('-inf')
    v_to = float(v_to) if v_to != '' else sys.maxsize # was float('inf')
    # logger.debug('yadcf_range_number: between %f and %f', v_from, v_to)
    return expr.between(v_from, v_to)
from datatables.search_methods import SEARCH_METHODS
SEARCH_METHODS['yadcf_range_number'] = alt_yadcf_range_number

# object multiple inheritance because BaseDataTables is old style class
# see https://stackoverflow.com/a/18392639/799921
class DataTables(BaseDataTables, object):

    def __init__(self, *args, **kwargs):
        '''
        adds optional set_yadcf_data kwarg, called instead of standard _set_yadcf_data

        :param args: see datatables.DataTables
        :param kwargs: see datatables.Datatables, plus set_yadcf_data
            set_yadcf_data(): function which sets yadcf_data_x in editor query response; see
            https://github.com/vedmack/yadcf/blob/master/src/jquery.dataTables.yadcf.js Server-side
            processing API
        '''
        self.set_yadcf_data = kwargs.pop('set_yadcf_data', None)
        super(DataTables, self).__init__(*args, **kwargs)

    def _set_yadcf_data(self, query):
        '''
        set self.yadcf_params to list of ('yadcf_data_<col>', values) tuples
        if set_yadcf_data callback specified when class initiated, that is used;
        else standard _set_yadcf_data function is used

        :param query: see datatables.DataTables
        :return: none
        '''

        if self.set_yadcf_data:
            self.yadcf_params = self.set_yadcf_data()

        else:
            super(DataTables, self)._set_yadcf_data(query)


def getattrdeep(obj, attr):
    '''
    get an attribute which might be keyed with dotted notation

    :param obj: possibly multilevel object
    :param attr: key attribute, possible dotted notation
    :return: value
    '''
    attrbranches = attr.split('.')
    # we're at the end of the branches, just return the value
    if len(attrbranches) == 1:
        return getattr(obj, attr)
    # drill down further
    else:
        return getattrdeep(getattr(obj, attrbranches[0]), '.'.join(attrbranches[1:]))

def setattrdeep(obj, attr, val):
    '''
    set an attribute which might be keyed with dotted notation

    :param obj: possibly multilevel object
    :param attr: key attribute, possible dotted notation
    :param val: value to set
    '''
    attrbranches = attr.split('.')
    # we're at the end of the branches, just set the value
    if len(attrbranches) == 1:
        setattr(obj, attr, val)
    # drill down further
    else:
        setattrdeep(getattr(obj, attrbranches[0]), '.'.join(attrbranches[1:]), val)

class DataTablesEditor():
    '''
    handle CRUD request from dataTables Editor

    dbmapping is dict like {'dbattr_n':'formfield_n', 'dbattr_m':f(form), ...}
    formmapping is dict like {'formfield_n':'dbattr_n', 'formfield_m':f(dbrow), ...}
    if order of operation is importand use OrderedDict

    If dbattr key == '__skip__', then don't try to update the db with this field

    :param dbmapping: mapping dict with key for each db field, value is key in form or function(dbentry)
    :param formmapping: mapping dict with key for each form row, value is key in db row or function(form)
    :param null2emptystring: if True translate '' from form to None for db and visa versa
    '''

    def __init__(self, dbmapping, formmapping, null2emptystring=False):
        self.dbmapping = dbmapping
        self.formmapping = formmapping
        self.null2emptystring = null2emptystring

        # can update this via self.set_response_hook(function(responserow))
        self.response_hook = lambda responserow: None

    def get_response_data(self, dbentry):
        '''
        set form values based on database model object

        :param dbentry: database entry (model object)
        '''

        data = {}

        # create data fields based on formmapping
        for key in self.formmapping:
            # call the function to fill data[key]
            if hasattr(self.formmapping[key], '__call__'):
                callback = self.formmapping[key]
                data[key] = callback(dbentry)
            
            # simple map from dbentry field
            else:
                dbattr = self.formmapping[key]

                # skip if indicated
                if dbattr == '__skip__': continue

                data[key] = getattrdeep(dbentry, dbattr)
                if self.null2emptystring and data[key]==None:
                    data[key] = ''

        self.response_hook(data)
        return data

    def set_dbrow(self, inrow, dbrow):
        '''
        update database entry from form entry

        :param inrow: input row
        :param dbrow: database entry (model object)
        '''

        for dbattr in self.dbmapping:
            # detect special value for type: readonly
            if self.dbmapping[dbattr] == '__readonly__':
                continue

            # call the function to fill dbrow.<dbattr>
            if hasattr(self.dbmapping[dbattr], '__call__'):
                callback = self.dbmapping[dbattr]
                try:
                    setattrdeep(dbrow, dbattr, callback(inrow))
                # maybe inrow attribute wasn't found, e.g., inline edit mode
                except KeyError:
                    pass

            # simple map from inrow field
            else:
                key = self.dbmapping[dbattr]
                if key in inrow:
                    setattrdeep(dbrow, dbattr, inrow[key])
                    if self.null2emptystring and getattrdeep(dbrow, dbattr) == '':
                        setattrdeep(dbrow, dbattr, None)
                else:
                    # ignore -- leave dbrow unchanged for this dbattr
                    pass


    def set_response_hook(self, response_hook):
        """
        set function which updates response data just before get_response_data returns

        ..note::
            only works for serverside=False

        :param response_hook: function(responserow)
        :return: None
        """
        self.response_hook = response_hook

class TablesCsv(MethodView):
    '''
    provides flask render for csv.DictReader-like datasource as table

    usage:
        class yourDatatablesCsv(TablesCsv):
            # overridden methods
        instancename = yourDatatablesCsv([arguments]):
        instancename.register()

    see below for methods which must be overridden when subclassing

    **columns** should be like the following. See https://datatables.net/reference/option/columns and 
    https://editor.datatables.net/reference/option/fields for more information

        [
            { 'data': 'name', 'name': 'name', 'label': 'Service Name' },
            { 'data': 'key', 'name': 'key', 'label': 'Key' }, 
            { 'data': 'secret', 'name': 'secret', 'label': 'Secret', 'render':'$.fn.dataTable.render.text()' },
        ]

        * name - describes the column and is used within javascript
        * data - used on server-client interface 
        * label - used for the DataTable table column. CSV file headers must match this
        * optional render key is eval'd into javascript
    
    :param app: flask app this is running under
    :param endpoint: endpoint parameter used by flask.url_for()
    :param rule: rule parameter used by flask.add_url_rule() [defaults to '/' + endpoint]
    '''

    #----------------------------------------------------------------------
    # these methods must be replaced
    #----------------------------------------------------------------------

    def open(self):
        '''
        open source of "csv" data
        '''
        raise NotImplementedError

    def nexttablerow(self):
        '''
        return next record, similar to csv.DictReader - raises StopIteration
        :rtype: dict with row data for table
        '''
        raise NotImplementedError

    def close(self):
        '''
        close source of "csv" data
        '''
        raise NotImplementedError

    def permission(self):
        '''
        check for readpermission on data
        :rtype: boolean
        '''
        raise NotImplementedError
        return False

    def renderpage(self, tabledata):
        '''
        renders flask template with appropriate parameters
        :param tabledata: list of data rows for rendering
        :rtype: flask.render_template()
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    # these methods may be replaced
    #----------------------------------------------------------------------

    def rollback(self):
        '''
        any processing which must be done on page abort or exception
        '''
        raise NotImplementedError

    def beforeget(self):
        '''
        any processing which needs to be done at the beginning of the get
        '''
        pass

    def abort(self):
        '''
        any processing which needs to be done to abort when forbidden (e.g., redirect)
        '''
        flask.abort(403)

    def __init__(self, **kwargs):
        # the args dict has all the defined parameters to
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        self.kwargs = kwargs
        args = dict(app = None,
                    # pagename = None, 
                    endpoint = None, 
                    rule = None, 
                    # dtoptions = {},
                    # readpermission = lambda: False, 
                    # columns = None, 
                    # buttons = ['csv'],
                    )
        args.update(kwargs)

        # rule defaults to '/' + endpoint if not supplied
        args['rule'] = args['rule'] or ('/' + args['endpoint'])

        # make arguments into attributes
        for key in args:
            setattr(self, key, args[key])

    def register(self):
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        # create supported endpoints
        my_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.rule),view_func=my_view,methods=['GET',])

    def get(self):
        try:
            # do any processing, e.g., check credentials
            redirect = self.beforeget()
            if redirect:
                return redirect

            # verify user can read the data, otherwise abort
            if not self.permission():
                self.rollback()
                self.abort()
            
            # build table data
            self.open()
            tabledata = []
            try:
                while (True):
                    datarow = self.nexttablerow()
                    tabledata.append(datarow)
            
            except StopIteration:
                self.close()
            
            # render page
            return self.renderpage(tabledata)
        
        except:
            # handle exception as subclass wants
            self.rollback()
            raise

class CrudChildElement():
    '''
    represents an element within a datatable child row

    :param name: name of the element
    :param type: type of the element, CHILDROW_TYPE_TABLE or datatables field type
    :param args: arguments specific to the element type
        CHILDROW_TYPE_TABLE
            name - name of table
            table - CrudApi table instance
            type - CHILDROW_TYPE_TABLE
            postcreatehook - (optional) string name of js function(datatables, editor) to be executed after create of table, editor
            tableidtemplate - template for table id
            args -
                buttons - list of editor actions 'create', 'edit', 'editRefresh', 'editChildRowRefresh', 'remove'
                    or other button configuration. May be function which returns this list.
                    See https://datatables.net/reference/option/buttons and
                    https://datatables.net/reference/option/buttons.buttons
                columns (optional)
                    datatable - { col.data : {attributes to merge}, ... }
                    editor    - { col.name : {attributes to merge}, ... }
                        ( col.data and col.name identify the column to merge attributes for )
                inline (optional)
                    // col.data is used because className is updated for datatables options
                    { col.data : {editor.inline() options}, ... }
                createfieldvals (optional)
                    // col.name is used because Editor fields are being updated
                    { col.field : initial_value, ... }
                updatedtopts (optional)
                    // general options for datatables, which override the defaults
                    // See https://datatables.net/reference/option/ search on DataTables - Features
                    // these are update on top of dtopts from self.table
                    { option: value, ... }
    '''
    def __init__(self, name=None, type=None, args=None, tableidtemplate=None, table=None, postcreatehook=None):
        if args is None:
            args = {}
        self.name = name
        self.type = type
        self.args = args
        self.tableidtemplate = tableidtemplate
        self.table = table
        self.postcreatehook = postcreatehook

        if type == CHILDROW_TYPE_TABLE and not table:
            raise ParameterError('CrudChildElement: element "{}" missing table argument'.format(name))

    def get_options(self):
        if self.type == CHILDROW_TYPE_TABLE:
            # need to make copy because args['buttons'] may get overwritten if function
            args = deepcopy(self.args)
            args['dtopts'] = self.table.getdtoptions()
            args['edopts'] = self.table.getedoptions()
            args['cropts'] = self.table.getchildrowoptions()
            # don't override caller buttons, else pick up from the table default
            if 'buttons' not in args:
                args['buttons'] = self.table.buttons
            args['buttons'] = args['buttons'] if not callable(args['buttons']) else args['buttons']()

            # remove server based column control as this has been configured by the base table
            # and we don't want to try to pass that to the client
            # add data2col lookup
            columns = []
            data2col = {}
            for thiscol in self.table.clientcolumns:
                copycol = copyopts(thiscol)
                copycol.pop('_ColumnDT_args', None)
                copycol.pop('onclause', None)
                copycol.pop('aliased', None)
                columns.append(copycol)
                data2col[copycol['data']] = copycol
            args['clientcolumns'] = columns
            args['data2col'] = data2col

            # may be postcreatehook, None if wasn't specified
            args['postcreatehook'] = self.postcreatehook

        else:
            args = self.args

        return {
            'name': self.name,
            'type': self.type,
            'tableidtemplate': self.tableidtemplate,
            'args': args
        }

def _editormethod(checkaction='', formrequest=True):
    '''
    decorator for CrudApi methods used by Editor

    :param methodcore: function() containing core of method to execute
    :param checkaction: Editor name of action which is used by the decorated method, one of 'create', 'edit', 'remove' or '' if no check required (can be list)
    :param formrequest: True if request action, data is in form (False for 'remove' action)
    '''
    # see http://python-3-patterns-idioms-test.readthedocs.io/en/latest/PythonDecorators.html
    if debug: print('_editormethod(checkaction={}, formrequest={})'.format(checkaction, formrequest))
    def wrap(f):
        def wrapped_f(self, *args, **kwargs):
            redirect = self.init()
            if redirect:
                return redirect

            # prepare for possible errors
            # see https://editor.datatables.net/manual/server-legacy#Server-to-client for format of self._fielderrors
            self._error = ''
            self._fielderrors = []

            try:
                # verify user can write the data, otherwise abort
                if not self.permission():
                    self.rollback()
                    cause = 'operation not permitted for user'
                    return dt_editor_response(error=cause)

                # get action
                # TODO: modify get_request_action and get_request_data to allow either request object or form object, 
                # and remove if/else for formrequest, e.g., action = get_request_action(request)
                # (allowing form object deprecated for legacy code)
                if formrequest:
                    action = get_request_action(request.form)
                    self._data = get_request_data(request.form)
                else:
                    action = request.args['action']
                self.action = action

                # perform any processing required before method is executed
                self.editor_method_prehook(request.form)

                if debug: print('checkaction = {}'.format(checkaction))
                # checkaction needs to be list
                if checkaction:
                    actioncheck = checkaction.split(',')

                # if checkaction and action != checkaction:
                if checkaction and action not in actioncheck:
                    self.rollback()
                    cause = 'unknown action "{}"'.format(action)
                    current_app.logger.warning(cause)
                    return dt_editor_response(error=cause)

                # set up parameters to query (set self.queryparams, self.queryfilters)
                self.beforequery()

                # execute core of method
                f(self,*args, **kwargs)

                # perform any processing required after method is executed
                self.editor_method_posthook(request.form)

                # commit database updates and close transaction
                self.commit()

                # perform any processing required after method is executed, after commit
                self.editor_method_postcommit(request.form)

                # response to client
                return dt_editor_response(data=self._responsedata, **self.responsekeys)
            
            except:
                # roll back database updates and close transaction
                self.rollback()
                if self._fielderrors:
                    cause = 'please check indicated fields'
                elif self._error:
                    cause = self._error
                else:
                    cause = traceback.format_exc()
                    current_app.logger.error(traceback.format_exc())
                return dt_editor_response(data=[], error=cause, fieldErrors=self._fielderrors)
        return wrapped_f
    return wrap


class CrudApi(MethodView):
    '''
    provides initial render and RESTful CRUD api

    usage:
        instancename = CrudApi([arguments]):
        instancename.register()

    **dbmapping** is dict like {'dbattr_n':'formfield_n', 'dbattr_m':f(form), ...}
    **formmapping** is dict like {'formfield_n':'dbattr_n', 'formfield_m':f(dbrow), ...}
    if order of operation is important for either of these use OrderedDict

    **clientcolumns** should be like the following. See https://datatables.net/reference/option/columns and 
    https://editor.datatables.net/reference/option/fields for more information

        [
            { 'data': 'name', 'name': 'name', 'label': 'Service Name' },
            { 'data': 'key', 'name': 'key', 'label': 'Key', 'render':'$.fn.dataTable.render.text()' }, 
            { 'data': 'secret', 'name': 'secret', 'label': 'Secret', 'render':'$.fn.dataTable.render.text()' },
            { 'data': 'service', 'name': 'service_id', 
              'label': 'Service Name',
              'type': 'selectize', 
              'options': [{'label':'yes', 'value':1}, {'label':'no', 'value':0}],
              'opts': { 
                'searchField': 'label',
                'openOnFocus': False
               },
               'dt': { options for DataTables only }
               'ed': { options for Editor only }
              '_update': [see below]
            },
        ]

        * name - describes the column and is used within javascript
        * data - used on server-client interface and should be used in the formmapping key and dbmapping value
        * label - used for the DataTable table column and the Editor form label 
        * render - (optional) is eval'd into javascript
        * id - is specified by idSrc, and should be in the mapping function but not columns
        * see https://datatables.net/reference/option/ (Columns) and https://editor.datatables.net/reference/option/ (Field) for more options

        NOTE: for options which are supported by both DataTables and Editor, options may be configured only within
        'dt' or 'ed' respectively to force being used for only that package, e.g., 'ed': {'render' ...} would render 
        just for the Editor, but be ignored for DataTables.

        additionally the update option can be used to _update the options for any type = 'select', 'select2', selectize'

        * _update - dict with following keys
            * endpoint - url endpoint to retrieve new options 
            * on - event which triggers update. supported events are
                * 'open' - triggered when form opens (actually when field is focused)
                * 'change' - triggered when field changes - use wrapper to indicate what field(s) are updated
            * wrapper - dict which is wrapped around query response. value '_response_' indicates where query response should be placed
    
                        OR

        * _update - dict with the following keys
                'options' : function() to retrieve option tree:
                        {'val1':<val1 Return options / JSON>,
                         'val2':<val2 Return options / JSON>,
                         ...}
                    when this field changes to 'val1', val1 Return options / JSON fetched and handled by Editor
                    see https://editor.datatables.net/reference/api/dependent(), Return options / JSON
              }

    **serverside** - if true table will be displayed through ajax get calls

    **scriptfilter** - can be used to filter list of scripts into full pathname, version argument, etc

    :param app: flask app or blueprint
    :param pagename: name to be displayed at top of html page
    :param endpoint: endpoint parameter used by flask.url_for()
    :param endpoint_values: values dict for endpoint, default {}, substitution as _value_, e.g., {'value':'_value_'}
        this can be used for permission grouping in url, e.g., /admin/_value_/endpoint
    :param rule: rule parameter used by flask.add_url_rule() [defaults to '/' + endpoint]
    :param eduploadoption: editor upload option (optional) see https://editor.datatables.net/reference/option/ajax
    :param clientcolumns: list of dicts for input to dataTables and Editor
    :param filtercoloptions: list of clientcolumns options which are to be filtered out
    :param serverside: set to true to use ajax to get table data
    :param idSrc: idSrc for use by Editor
    :param buttons: list of buttons for DataTable, from ['create', 'remove', 'editRefresh', 'edit', 'csv'], or
            function which returns such a list
    :param pretablehtml: string any html which needs to go before the table

    :param scriptfilter: function to filter pagejsfiles and pagecssfiles lists into full path / version lists
    :param dtoptions: dict of datatables options to apply at end of options calculation
    :param edoptions: dict of datatables editor options to apply at end of options calculation
    :param yadcfoptions: dict of yadcf options to apply at end of options calculation
    :param pagejsfiles: list of javascript file paths to be included
    :param pagecssfiles: list of css file paths to be included
    :param templateargs: dict of arguments to pass to template - if callable arg function is called before being passed
            to template (no parameters)
    :param validate: editor validation function (action, formdata), result is set to self._fielderrors
    :param formencode_validator: instance of formencode validator, used for editor validation function as described in validate
    :param multiselect: if True, allow selection of multiple rows, default False
    :param responsekeys: dict of items to add to editor response, can update in any of the hooks.
    :param tableidcontext: (optional) function which returns context for tableidtemplate rendering
    :param tableidtemplate: (optional) jinja2 template string used to identify this table, merged via
            self.tableid(**context)

    :param createfieldvals: (optional) dict of fields with values for create form {name: val, ...}, or function
            which returns such a dict
    :param childrowoptions: (optional) the following dict or function which returns this dict
        {
          'template': nunjuck template for display of child row,
          'showeditor': True if editor should be shown in childrow, template must have element with id
                childrow-editform-<id>
          'group' (optional) if group is used to partition database, this is the name of the group
          'groupselector' (optional, but required if 'group' is set) this is the selector id which the user uses to
                choose their group
          'childelementargs': array of arg dicts for instantiations of CrudChildElement instances
        }
    '''

    def __init__(self, **kwargs):
        # the args dict has all the defined parameters to
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        self.kwargs = kwargs
        args = dict(app = None,
                    template = 'datatables.html',
                    pagename = None, 
                    endpoint = None,
                    endpointvalues = {},
                    rule = None, 
                    eduploadoption = None,
                    clientcolumns = None, 
                    filtercoloptions = [],
                    serverside = False, 
                    files = None,
                    idSrc = 'DT_RowId', 
                    buttons = ['create', 'edit', 'remove', 'csv'],
                    pretablehtml = '',
                    posttablehtml = '',
                    scriptfilter = lambda filelist: filelist,
                    dtoptions = {},
                    edoptions = {},
                    yadcfoptions = {},
                    pagejsfiles = [],
                    pagecssfiles = [],
                    templateargs = {},
                    validate = lambda action,formdata: [],
                    formencode_validator = None,
                    multiselect = False,
                    addltemplateargs = {},
                    responsekeys = {},
                    tableidcontext = lambda: {},
                    tableidtemplate = '',
                    createfieldvals = {},
                    childrowoptions = {},
                    )
        args.update(kwargs)

        # rule defaults to '/' + endpoint if not supplied
        args['rule'] = args['rule'] or ('/' + args['endpoint'])

        # make arguments into attributes
        for key in args:
            setattr(self, key, args[key])

        # update self.validate if formencode_validator supplied
        if self.formencode_validator:
            self.validate = self._validate_formencode

        # set up child element instances
        self.childelements = []
        self.childtables = {}
        if self.childrowoptions:
            childrowoptions = self.childrowoptions() if callable(self.childrowoptions) else self.childrowoptions
            childelementargs = childrowoptions.get('childelementargs', [])
            for ceargs in childelementargs:
                self.childelements.append(CrudChildElement(**ceargs))
                self.childtables[ceargs['name']] = ceargs

    def register(self):
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        # create supported endpoints
        self.my_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.rule),view_func=self.my_view,methods=['GET',])
        self.app.add_url_rule('{}/rest'.format(self.rule),view_func=self.my_view,methods=['GET', 'POST'])
        self.app.add_url_rule('{}/rest/<thisid>'.format(self.rule),view_func=self.my_view,methods=['PUT', 'DELETE'])

        if self.files:
            self.files.register()
            if debug: print('self.files.register()')

    def _renderpage(self):
        try:
            redirect = self.init()
            if redirect:
                return redirect
            
            # verify user can write the data, otherwise abort
            if not self.permission():
                self.rollback()
                self.abort()

            # set up parameters to query (set self.queryparams, self.queryfilters)
            self.beforequery()

            # peel off any _update options
            update_options = []
            for column in self.clientcolumns:
                if '_update' in column:
                    update = column['_update']  # convenience alias
                    if 'url' in update:
                        update['url'] = url_for(update['endpoint']) + '?' + urlencode({'_wrapper':dumps(update['wrapper'])})
                        update['name'] = column['name']
                        update_options.append(update)
                    
                    # options should be callable
                    elif 'options' in update:
                        # don't change column['_update']
                        thisupdate = {}

                        # pick up name from editor parameters, if present
                        if 'ed' in column and 'name' in column['ed']:
                            thisupdate['name'] = column['ed']['name']
                        else:
                            thisupdate['name'] = column['name']
                        thisupdate['options'] = update['options']()
                        update_options.append(thisupdate)

                    else:
                        raise ParameterError('invalid _update format: {}'.format(update))

            # build table data
            if not self.serverside:
                self.open()
                tabledata = []
                try:
                    while(True):
                        thisentry = self.nexttablerow()
                        tabledata.append(thisentry)
                except StopIteration:
                    pass
                self.close()
            else:
                tabledata = '{}/rest'.format(url_for(self.endpoint, **self.endpointvalues))

            # get files if indicated
            if self.files:
                tablefiles = self.files.list()
                if debug: print(tablefiles)
            else:
                tablefiles = None

            # commit database updates and close transaction
            self.commit()

            # calculate buttons
            buttons = self.buttons
            if callable(buttons):
                buttons = buttons()

            # render page
            return self.render_template(
                pagename = self.pagename if not callable(self.pagename) else self.pagename(),
                pagejsfiles = self.scriptfilter(self.pagejsfiles),
                pagecssfiles = self.scriptfilter(self.pagecssfiles),
                tabledata = tabledata,
                tablefiles = tablefiles,
                tablebuttons = buttons,
                pretablehtml = self.pretablehtml if not callable(self.pretablehtml) else self.pretablehtml(),
                posttablehtml = self.posttablehtml if not callable(self.posttablehtml) else self.posttablehtml(),
                options = {
                    'dtopts': self.getdtoptions(),
                    'editoropts': self.getedoptions(),
                    'yadcfopts' : self.getyadcfoptions(),
                    'childrow' : self.getchildrowoptions(),
                    'updateopts': update_options,
                    'createfieldvals': self.getcreatefieldvals(),
                },
                writeallowed = self.permission(),
                **self.addltemplateargs
            )
        
        except:
            # roll back database updates and close transaction
            self.rollback()
            raise

    def _retrieverows(self):
        try:
            redirect = self.init()
            if redirect:
                return redirect
            
            # verify user can write the data, otherwise abort
            if not self.permission():
                self.rollback()
                self.abort()
                
            # set up parameters to query (set self.queryparams, self.queryfilters)
            self.beforequery()

            # get data from database
            # ### open, nexttablerow and close may create and manipulate self.output_result
            # ### the tabledata list manipulation here is available for backwards compatibility
            # ### at time of this writing, 
            # TODO: handle case when files are indicated
            self.open()
            tabledata = []
            try:
                while(True):
                    thisentry = self.nexttablerow()
                    tabledata.append(thisentry)
            except StopIteration:
                pass
            self.close()

            # back to client
            if hasattr(self, 'output_result'):
                self.output_result.update(self.responsekeys)
                return jsonify(self.output_result)
            else:
                output_result = tabledata
                # for this case (non-serverside) output_result is list so this doesn't work
                # output_result.update(self.responsekeys)
                return jsonify(output_result)

        except:
            # roll back database updates and close transaction
            self.rollback()
            raise

    def _validate_formencode(self, action, formdata):
        val = DteFormValidate(self.formencode_validator)
        results = val.validate(formdata)
        self.formdata = results['python']
        return results['results']

    def getdtoptions(self):

        # DataTables options string, data: and buttons: are passed separately
        # self.dtoptions can update what we come up with
        dt_options = {
            'dom': '<"H"lBpfr>t<"F"i>',
            'columns': [
            ],
            'rowId': self.idSrc,
            'select': 'single' if not self.multiselect else 'os',
            'ordering': True,
        }

        # track col name to col index, for 'order' option preprocessing
        name2index = {}

        # get column options
        for column in self.clientcolumns:
            # skip rows that are editor only
            if 'edonly' in column: continue

            # if callable, call when making a copy
            # this allows views to refresh, e.g., 'options' for select-like columns
            # remove any column options indicated when this class called (filtercoloptions)
            dtcolumn = { key: column[key] if not callable(column[key]) else column[key]()
                        for key in column if key not in self.filtercoloptions + ['dtonly']}

            # add title option if not there
            dtcolumn.setdefault('title', dtcolumn.get('label', ''))

            # pop to remove certain keys from dtcolumn
            dtspecific = dtcolumn.pop('dt', {})
            dtcolumn.pop('ed', {})
            dtcolumn.pop('_update', {})
            dtcolumn.update(dtspecific)
            dt_options['columns'].append(dtcolumn)

            # track col name to col index, for 'order' option preprocessing
            if 'name' in dtcolumn:
                name2index[dtcolumn['name']] = len(dt_options['columns']) - 1

        dt_options['serverSide'] = self.serverside

        # maybe user had their own ideas on what options are needed for table
        dt_options.update(self.dtoptions)

        # preprocess 'order' option, if present, converting {string}:name to index
        if 'order' in dt_options:
            for ordcol in dt_options['order']:
                if isinstance(ordcol[0], str):
                    try:
                        colname,seltype = ordcol[0].split(':')
                        if seltype != 'name':
                            raise ValueError
                    except ValueError:
                        raise ParameterError('order option "index" must be int or of form "colname:name": {}'.format(ordcol[0]))

                    if colname in name2index:
                        ordcol[0] = name2index[colname]
                    else:
                        raise ParameterError('order option name not found: {}'.format(colname))

        # deep copy, taking care not to include non-jsonable values
        dt_options = copyopts(dt_options)

        return dt_options

    def getedoptions(self):
        ed_options = {
            'idSrc': self.idSrc,
            'ajax': {
                'create': {
                    'type': 'POST',
                    'url':  '{}/rest'.format(url_for(self.endpoint, **self.endpointvalues)),
                },
                'edit': {
                    'type': 'PUT',
                    'url':  '{}/rest/{}'.format(url_for(self.endpoint, **self.endpointvalues),'_id_'),
                },
                'editRefresh': {
                    'type': 'PUT',
                    'url':  '{}/rest'.format(url_for(self.endpoint, **self.endpointvalues)),
                },
                'editChildRowRefresh': {
                    'type': 'PUT',
                    'url':  '{}/rest'.format(url_for(self.endpoint, **self.endpointvalues)),
                },
                'remove': {
                    'type': 'DELETE',
                    'url':  '{}/rest/{}'.format(url_for(self.endpoint, **self.endpointvalues),'_id_'),
                },
            },
            
            'fields': [
            ],

            # no focus on field error, fixes #50
            'onFieldError': 'none',
        }
        # TODO: these are known editor field options as of Editor 1.8.1 -- do we really need to get rid of non-Editor options?
        fieldkeys = ['className', 'data', 'def', 'entityDecode', 'fieldInfo', 'id', 'label', 'labelInfo', 'name',
                     'type', 'options', 'opts', 'ed', 'separator', 'dateFormat', 'onFocus']
        for column in self.clientcolumns:
            # skip rows that are datatable only
            if 'dtonly' in column: continue

            # current_app.logger.debug('getedoptions(): column = {}'.format(column))

            # pick keys which matter
            # if callable, call when making a copy
            # this allows views to refresh, e.g., 'options' for select-like columns
            # remove any column options indicated when this class called (filtercoloptions)
            edcolumn = { key: column[key] if not callable(column[key]) else column[key]()
                        for key in fieldkeys if key in column and key not in self.filtercoloptions + ['edonly']}

            # pop to remove from edcolumn
            edspecific = edcolumn.pop('ed', {})
            edcolumn.update(edspecific)
            # current_app.logger.debug('getedoptions(): edcolumn={}'.format(edcolumn))
            ed_options['fields'].append(edcolumn)

        # add upload, if desired
        if self.eduploadoption:
            ed_options['ajax']['upload'] = self.eduploadoption

        # maybe user had their own ideas on what options are needed for editor
        ed_options.update(self.edoptions)
        if debug: current_app.logger.debug('getedoptions(): ed_options={}'.format(ed_options))

        # deep copy, taking care not to include non-jsonable values
        ed_options = copyopts(ed_options)

        return ed_options

    def getyadcfoptions(self):
        return self.yadcfoptions

    def getchildrowoptions(self):
        # deep copy, taking care not to include non-jsonable values
        val = copyopts(self.childrowoptions) if not callable(self.childrowoptions) else self.childrowoptions()

        # the original childelementargs config has been converted to self.childelements
        val.pop('childelementargs', None)

        # add elements to options
        # NOTE: the order from the original childelementargs has been preserved
        for el in self.childelements:
            val.setdefault('childelements',{})
            options = el.get_options()
            val['childelements'][options['name']] = options

        return val

    def getcreatefieldvals(self):
        if callable(self.createfieldvals):
            return self.createfieldvals()
        else:
            return self.createfieldvals

    def tableid(self, **context):
        '''
        return string from context, suitable for use within table form

        :param context: keyword parameters rendered against template supplied at instantiation via
            childidtemplate parameter
        :return: string
        '''
        template = Template(self.tableidtemplate)
        return template.render(**context)

    def get(self):
        if debug: print('request.path = {}'.format(request.path))
        if request.path[-5:] != '/rest':
            return self._renderpage()
        else:
            return self._retrieverows()

    @_editormethod(checkaction='create,refresh', formrequest=True)
    def post(self):
        self.do_post()

    def do_post(self):
        # retrieve data from request
        thisdata = self._data[0]

        action = get_request_action(request.form)
        self._fielderrors = self.validate(action, thisdata)
        if self._fielderrors: raise ParameterError

        if action == 'create':
            thisrow = self.createrow(thisdata)
            self._responsedata = [thisrow]
        elif action == 'refresh':
            form = request.form
            if 'refresh' in form and 'ids' in form:
                self._responsedata = self.refreshrows(form['ids'])
            else:
                cause = 'post(): edit action without refresh parameters'
                current_app.logger.error(cause)
                self._error = cause
                raise ParameterError(cause)
        else:
            thisrow = self.upload(thisdata)

    @_editormethod(checkaction='edit', formrequest=True)
    def put(self, thisid):
        # allow multirow editing, e.g., for rowReorder
        theseids = thisid.split(',')
        self._responsedata = []
        for id in theseids:
            # try to coerce to int, but ok if not
            try:
                id = int(id)
            except ValueError:
                pass

            # retrieve data from request
            thisdata = self._data[id]

            self._fielderrors = self.validate('edit', thisdata)
            if self._fielderrors: raise ParameterError

            thisrow = self.updaterow(id, thisdata)

            self._responsedata += [thisrow]


    @_editormethod(checkaction='remove', formrequest=False)
    def delete(self, thisid):
        # try to coerce to int, but ok if not
        try:
            thisid = int(thisid)
        except ValueError:
            pass

        self.deleterow(thisid)

        # prepare response
        self._responsedata = []


    #----------------------------------------------------------------------
    # the following methods must be replaced in subclass
    #----------------------------------------------------------------------
    
    def open(self):
        '''
        open source of "csv" data
        '''
        raise NotImplementedError

    def nexttablerow(self):
        '''
        return next record, similar to csv.DictReader - raises StopIteration
        :rtype: dict with row data for table
        '''
        raise NotImplementedError

    def close(self):
        '''
        close source of "csv" data
        '''
        raise NotImplementedError

    def permission(self):
        '''
        check for readpermission on data
        :rtype: boolean
        '''
        raise NotImplementedError
        return False

    def createrow(self, formdata):
        '''
        creates row in database
        
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        raise NotImplementedError

    def refreshrows(self, ids):
        '''
        refreshes rows from database
        
        :param ids: comma separated ids for which refresh is required
        :rtype: returned rows for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        current_app.logger.debug('tables.refreshrows("{}"): reached'.format(ids))
        raise NotImplementedError

    def updaterow(self, thisid, formdata):
        '''
        updates row in database
        
        :param thisid: id of row to be updated
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        raise NotImplementedError

    def deleterow(self, thisid):
        '''
        deletes row in database
        
        :param thisid: id of row to be updated
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    # the following methods may be replaced in subclass
    #----------------------------------------------------------------------
    
    def init(self):
        '''
        optional return redirect URL
        :return: redirect url or None if no redirect
        '''
        pass

    def beforequery(self):
        '''
        update self.queryparams, self.queryfilters if necessary
        '''
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def abort(self):
        flask.abort(403)

    def render_template(self, **kwargs):
        '''
        NOTE: it is recommended that rather than replacing this method, templateargs and template class
        parameters be used instead
        '''

        # when class was instantiated, templateargs dict passed in, keys of which to be added to flask render_template
        # some of these keys cannot be determined when the class was instantiated, e.g., if url_for() is needed
        # because blueprint hadn't been instantiated yet. So these are pass as lambda: url_for(), and therefore callable

        theseargs = {}
        current_app.logger.debug('rendertemplate(): self.templateargs = {}'.format(self.templateargs))
        for arg in self.templateargs:
            current_app.logger.debug('rendertemplate(): adding {} to template args'.format(arg))
            # maybe the template argument needs to be determined at runtime
            if callable(self.templateargs[arg]):
                theseargs[arg] = self.templateargs[arg]()
            else:
                theseargs[arg] = self.templateargs[arg]
        kwargs.update(theseargs)

        # current_app.logger.debug('flask.render_template({}, {})'.format(self.template, theseargs))
        return flask.render_template(self.template, **kwargs)

    def editor_method_prehook(self, form):
        '''
        This method is called within post() [create], put() [edit], delete() [edit] after permissions are checked

        Replace this if any preprocessing is required based on the form. The form itself cannot be changed

        NOTE: any updates to form validation should be done in self.validation()

        self.action has action

        parameters:
        * form - request.form object (immutable)
        '''
        return

    def editor_method_posthook(self, form):
        '''
        This method is called within post() [create], put() [edit], delete() [edit] db commit() just before database
        commit and response to client

        Use get_request_action(form) to determine which method is in progress
        self._responsedata has data about to be returned to client
        self.action has action

        parameters:
        * form - request.form object (immutable)
        '''
        return

    def editor_method_postcommit(self, form):
        '''
        This method is called within post() [create], put() [edit], delete() [edit] db commit() just after database
        commit and before response to client

        Use get_request_action(form) to determine which method is in progress
        self._responsedata has data about to be returned to client
        self.action has action

        parameters:
        * form - request.form object (immutable)
        '''
        return


def _uploadmethod():
    '''
    decorator for CrudFiles methods used by Editor

    :param methodcore: function() containing core of method to execute
    '''

    # see http://python-3-patterns-idioms-test.readthedocs.io/en/latest/PythonDecorators.html
    def wrap(f):
        def wrapped_f(self, *args, **kwargs):
            try:
                # execute core of method and send response
                f(self,*args, **kwargs)

                return dt_editor_response(**self._responsedata)
            
            except Exception as e:
                cause = 'Unexpected Error: {}\n{}'.format(e,traceback.format_exc())
                current_app.logger.error(cause)
                return dt_editor_response(error=cause)

        return wrapped_f
    return wrap

class DteDbOptionsPickerBase():
    '''
    base class defines options picker for datatables editor db - form interface

    for relationships defined like
    class model()
        dbfield            = relationship( 'mappingmodel', backref=tablemodel, lazy=True )

    * tablemodel - name of model for the table
    * fieldmodel - name of model which comprises list in dbfield
    * labelfield - field in fieldmodel which is used to be displayed to the user
    * valuefield - field in fieldmodel which is used as value for select and to retrieve record, passed on Editor interface,
    *    default 'id' - needs to be a key for model record
    * formfield - field as used on the form
    * dbfield - field as used in the database table (not the model -- this is field in tablemodel which has list of
         fieldmodel items)
    * uselist - set to True if using tags, otherwise field expects single entry, default True
    * searchbox - set to True if searchbox desired, default False
    * nullable - set to True if item can give null (unselected) return, default False (only applies for usellist=False)
    * queryparams - dict containing parameters for query to determine options, or callable which returns such a dict
    '''

    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(tablemodel=None,
                    fieldmodel=None,
                    labelfield=None,
                    valuefield='id',
                    formfield=None,
                    dbfield=None,
                    uselist=True,
                    searchbox=False,
                    nullable=False,
                    queryparams= {}
                    )
        args.update(kwargs)

        # # some of the args are required
        # reqdfields = ['fieldmodel', 'labelfield', 'formfield', 'dbfield']
        # for field in reqdfields:
        #     if not args[field]:
        #         raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))

        # set arguments as class attributes
        for key in args:
            setattr(self, key, args[key])

    def get_dbrow(self, dbrow_or_id):
        '''
        return dbrow for possible dbrow or id

        :param dbrow_or_id: dbrow or id for table row
        :return: dbrow
        '''
        # check if id supplied, if so retrieve dbrow
        if type(dbrow_or_id) in [int, str]:
            # normal operation is not through via attr
            dbrow = self.tablemodel.query().filter_by(id=dbrow_or_id).one()

        else:
            dbrow = dbrow_or_id

        return dbrow

    def set(self, formrow):
        '''
        set formfield into database based on formrow

        :param formrow: dict row received from datatables editor client with a key for each form field
        :return: updated database item or item list
        '''
        raise NotImplementedError

    def get(self, dbrow_or_id):
        '''
        get database item for display in option picker at datatables editor client

        :param dbrow_or_id: id or database row, assumes id if int or str
        :return: {self.labelfield : labelvalue, self.valuefield : valuevalue} (or list of these)
        '''
        # check if id supplied, if so retrieve dbrow
        raise NotImplementedError

    def options(self):
        '''
        return sorted list of items in the model, may be overridden for more complex models

        :return: options as expected by optionpicker type,
            e.g., for select2 list of {'label': label, 'value': value} (see https://select2.org/options)
        '''
        raise NotImplementedError
        # e.g., like the below
        # queryparams = self.queryparams() if callable(self.queryparams) else self.queryparams
        # items = []
        # if self.nullable:
        #     items += [{'label': '<none>', 'value': None}]
        # items += [{'label': getattr(item, self.labelfield), 'value': item.id}
        #           for item in self.fieldmodel.query.filter_by(**queryparams).all()]
        # items.sort(key=lambda k: k['label'].lower())
        # return items

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
        raise NotImplementedError

        # e.g., like below
        # col = {}
        # col['type'] = 'select2'
        # col['onFocus'] = 'focus'
        # col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
        #                'multiple': self.uselist,
        #                'placeholder': None if self.uselist else '(select)'}
        # if self.uselist:
        #     col['separator'] = SEPARATOR
        # return col

class DteDbRelationship():
    '''
    define relationship for datatables editor db - form interface

    for relationships defined like
    class model()
        dbfield            = relationship( 'mappingmodel', backref=tablemodel, lazy=True )

    * tablemodel - name of model for the table
    * fieldmodel - name of model which comprises list in dbfield
    * labelfield - field in fieldmodel which is used to be displayed to the user
    * valuefield - field in fieldmodel which is used as value for select and to retrieve record, passed on Editor interface,
    *    default 'id' - needs to be a key for model record
    * formfield - field as used on the form
    * dbfield - field as used in the database table (not the model -- this is field in tablemodel which has list of
         fieldmodel items)

    * viasubfield - (optional) field which has record which contains options, in this case, dbfield is attr of the subrecord

    * viadbattr - (optional) if fieldmodel is in a separate database, the select options of fieldmodel.valuefield
         can be mapped via a local table. Specify the "via" mapping attribute here, e.g., LocalUser.user_id
    * viafilter - (optional) if viadbattr is set, this can be additional filters to add to the local table lookup.
         This can be specific dict or function() which returns specific dict

    * sqlaexpr - override sqla expression with this

    * uselist - set to True if using tags, otherwise field expects single entry, default True
    * searchbox - set to True if searchbox desired, default False
    * nullable - set to True if item can give null (unselected) return, default False (only applies for usellist=False)
    * queryparams - dict containing parameters for query to determine options, or callable which returns such a dict
    * queryfilters - list containing filter sql expressions, for query to determine options, or callable which returns such a list
    * sortkey - function(dbrow) for sorting options list, default sorts by self.labelfield.lower()

    * onclause - sqlalchemy expression: if there is ambiguous relationship between records, this is used as part of
        outerjoin() to clarify the relationship. E.g., Motion.seconder_id == LocalUser.id

    Basic Use:

        class Parent(Base):
            __tablename__ = 'parent'
            id = Column(Integer, primary_key=True)
            child_id = Column(Integer, ForeignKey('child.id'))
            child = relationship("Child", backref="parents")

        class Child(Base):
            __tablename__ = 'child'
            name = Column(String)
            id = Column(Integer, primary_key=True)

        TODO: add more detail here -- this is confusing

        children = DteDbRelationship(tablemodel=Parent, fieldmodel=Child, labelfield='name', formfield='children', dbfield='children')

    Use of viadbattr:

        # local db
        usertaskgroup_table = Table('user_taskgroup', Base.metadata,
                           Column('user_id', Integer, ForeignKey('localuser.id')),
                           Column('taskgroup_id', Integer, ForeignKey('taskgroup.id')),
                           )

        class LocalUser(Base):
            __tablename__ = 'localuser'
            id                  = Column(Integer(), primary_key=True)
            user_id             = Column(Integer)

        class TaskGroup(Base):
            __tablename__ = 'taskgroup'
            id                  = Column(Integer(), primary_key=True)
            taskgroup           = Column(String(TASKGROUP_LEN))
            users               = relationship('LocalUser',
                                               secondary=usertaskgroup_table,
                                               backref=backref('taskgroups'))

        # separate db (using SQLALCHEMY_BINDS)
        class User(Base, UserMixin):
            __tablename__ = 'user'
            __bind_key__ = 'users'
            id                  = Column(Integer, primary_key=True)
            email               = Column( String(EMAIL_LEN), unique=True )  # = username
            password            = Column( String(PASSWORD_LEN) )
            name                = Column( String(NAME_LEN) )
            given_name          = Column( String(NAME_LEN) )

        taskgroups = DteDbRelationship(tablemodel=TaskGroup, fieldmodel=User, viadbattr=LocalUser.user_id, labelfield='name', formfield='users', dbfield='users')

    '''

    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(tablemodel=None,
                    fieldmodel=None,
                    labelfield=None,
                    valuefield='id',
                    formfield=None,
                    dbfield=None,
                    viasubrecord=None,
                    viadbattr=None,
                    viafilter={},
                    sqlaexpr=None,
                    uselist=True,
                    searchbox=False,
                    nullable=False,
                    queryparams= {},
                    queryfilters= [],
                    onclause=None,
                    sortkey=None,
                    )
        args.update(kwargs)

        # some of the args are required
        reqdfields = ['fieldmodel', 'labelfield', 'formfield', 'dbfield']
        for field in reqdfields:
            if not args[field]:
                raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))

        # set arguments as class attributes
        for key in args:
            setattr(self, key, args[key])

        # pick up viadbattr class, key
        if self.viadbattr:
            self.viamodel = self.viadbattr.class_
            self.viafield = self.viadbattr.key

    def set(self, formrow):
        # set database from form
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
                        itemvalues.append({key: vallist[ndx]})
                    else:
                        itemvalues[ndx].update({key: vallist[ndx]})
            if debug: current_app.logger.debug('itemvalues={}'.format(itemvalues))
            for itemvalue in itemvalues:
                # normal operation is not through via attr
                if not self.viadbattr:
                    queryfilter = itemvalue
                    # queryfilter = {self.valuefield : itemvalue}
                    thisitem = self.fieldmodel.query.filter_by(**queryfilter).one()
                # operation through "via" model to access bind table
                else:
                    # note self.viafilter must be or return dict
                    queryfilter = self.viafilter() if callable(self.viafilter) else self.viafilter
                    queryfilter[self.viafield] = itemvalue[self.valuefield]
                    thisitem = self.viamodel.query.filter_by(**queryfilter).one()
                items.append(thisitem)
            return items
        else:
            itemvalue = formrow[self.formfield] if formrow[self.formfield] else None
            if not self.viadbattr:
                queryfilter = itemvalue
                # queryfilter = {self.valuefield : itemvalue}
                thisitem = self.fieldmodel.query.filter_by(**queryfilter).one_or_none()
            else:
                queryfilter = self.viafilter() if callable(self.viafilter) else self.viafilter
                queryfilter[self.viafield] = itemvalue[self.valuefield]
                thisitem = self.viamodel.query.filter_by(**queryfilter).one()
            return thisitem

    def get(self, dbrow_or_id):
        # check if id supplied, if so retrieve dbrow
        if type(dbrow_or_id) in [int, str]:
            # normal operation is not through via attr
            dbrow = self.tablemodel.query().filter_by(id=dbrow_or_id).one()

        else:
            dbrow = dbrow_or_id

        # use subrecord if requested
        if self.viasubrecord:
            dbrow = getattr(dbrow, self.viasubrecord)

        # get from database to form
        if self.uselist:
            items = {}
            labelitems = []
            valueitems = []
            for item in getattr(dbrow, self.dbfield):
                if not self.viadbattr:
                    theitem = item
                # operation through "via" model to access bind table
                # item points at viamodel entry, need to convert to fieldmodel entry
                else:
                    itemparams = {self.valuefield: getattr(item, self.viafield)}
                    theitem = self.fieldmodel.query.filter_by(**itemparams).one()

                labelitems.append(str(getattr(theitem, self.labelfield)))
                valueitems.append(str(getattr(theitem, self.valuefield)))
            items = {self.labelfield: SEPARATOR.join(labelitems), self.valuefield: SEPARATOR.join(valueitems)}
            return items
        else:
            # get the attribute if specified
            if getattr(dbrow, self.dbfield):
                if not self.viadbattr:
                    item = {self.labelfield: getattr(getattr(dbrow, self.dbfield), self.labelfield),
                            self.valuefield: getattr(getattr(dbrow, self.dbfield), self.valuefield)}
                # operation through "via" model to access bind table
                # item points at viamodel entry, need to convert to fieldmodel entry
                else:
                    recparams = {self.valuefield: getattr(getattr(dbrow, self.dbfield), self.viafield)}
                    rec = self.fieldmodel.query.filter_by(**recparams).one()
                    item = {self.labelfield: getattr(rec, self.labelfield), self.valuefield: getattr(rec, self.valuefield)}
                
                return item
            # otherwise return None
            else:
                return {self.labelfield: None, self.valuefield: None}

    def sqla_expr(self):
        '''
        get from database when using serverside = True, for use with ColumnDT

        :return: sqlalchemy expression
        '''
        if type(self.sqlaexpr) != type(None):
            return self.sqlaexpr

        if not self.viadbattr:
            return get_dbattr(self.fieldmodel, self.labelfield)
            # return get_dbattr(self.tablemodel, self.dbfield)

        else:
            return self.viadbattr

    def options(self):
        # return sorted list of items in the model
        queryparams = self.queryparams() if callable(self.queryparams) else self.queryparams
        queryfilters = self.queryfilters() if callable(self.queryfilters) else self.queryfilters
        items = []
        if self.nullable:
            items += [{'label': '<none>', 'value': None}]
        alldbitems = self.fieldmodel.query.filter_by(**queryparams).filter(*queryfilters).all()
        if self.sortkey:
            alldbitems.sort(key=self.sortkey)
        items += [{'label': getattr(item, self.labelfield), 'value': item.id} for item in alldbitems]
        if not self.sortkey:
            items.sort(key=lambda k: k['label'].lower())
        return items

    def new_plus_options(self):
        # return sorted list of items in the model
        items = [{'label': '<new>', 'value': 0}] + self.options()
        return items

    def col_options(self):
        col = {}
        col['type'] = 'select2'
        col['onFocus'] = 'focus'
        col['opts'] = {'minimumResultsForSearch': 0 if self.searchbox else 'Infinity',
                       'multiple': self.uselist,
                       'placeholder': None if self.uselist else '(select)'}
        if self.uselist:
            col['separator'] = SEPARATOR
        return col

    def col_dt_list(self, **coldt_args):
        '''
        return a two item list of ColumnDT instances, for id and labelfield
        louking/members#152 (search for this to find required matching code)
        TODO: test to work with viadbattr (guaranteed not to work right now)

        :param coldt_args: caller supplied ColumnDT arguments
        :return: [ColumnDT( for 'id' ), ColumnDT( for labelfield )
        '''
        coldts = []
        for f in ['id', self.labelfield]:
            args = {}
            args.update(**coldt_args)
            # these take precedence
            args.update({'sqla_expr': get_dbattr(self.fieldmodel, f), 'mData': '{}.{}'.format(self.formfield, f)})
            coldts.append(ColumnDT(**args))
        return coldts

class DteDbSubrec():
    '''
    define subfield relationship for datatables editor db - form interface

    for relationships defined like
    class model()
        field            = relationship( 'mappingmodel', backref=tablemodel, lazy=True )

    * model - model comprises the subrec
    * dbfield - field in model which is used to be displayed to the user
    * formfield - field name on form associated with this db field
    * onclause - sqlalchemy expression: if there is ambiguous relationship between records, this is used as part of
        outerjoin() to clarify the relationship. E.g., Motion.seconder_id == LocalUser.id

    e.g.,
        class Parent(Base):
            __tablename__ = 'parent'
            id = Column(Integer, primary_key=True)
            child_id = Column(Integer, ForeignKey('child.id'))
            child = relationship("Child", backref="parents")

        class Child(Base):
            __tablename__ = 'child'
            name = Column(String)
            id = Column(Integer, primary_key=True)

        TODO: add more detail here -- this is confusing

        reln = DteDbSubrec(model=Child, dbfield='name', formfield='name')
    '''

    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(model=None,
                    field=None,
                    subfield=None,
                    formfield=None,
                    onclause=None,
                    )
        args.update(kwargs)

        # some of the args are required
        reqdfields = ['model', 'field', 'subfield', 'formfield']
        for field in reqdfields:
            if not args[field]:
                raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))

        # set arguments as class attributes
        for key in args:
            setattr(self, key, args[key])

    def set(self, formrow):
        # set database from form
        itemvalue = formrow[self.formfield] if formrow[self.formfield] else None
        queryfilter = itemvalue
        thisitem = self.model.query.filter_by(**queryfilter).one_or_none()
        return thisitem

    def get(self, dbrow_or_id):
        # check if id supplied, if so retrieve dbrow
        if type(dbrow_or_id) in [int, str]:
            dbrow = self.model.query().filter_by(id=dbrow_or_id).one()
        else:
            dbrow = dbrow_or_id

        # get from database to form
        # get the attribute if specified
        if getattr(dbrow, self.field):
            item = getattr(getattr(dbrow, self.field), self.subfield)
            return item
        # otherwise return None
        else:
            return None


class DteDbBool():
    '''
    define helpers for boolean fields

    * formfield - field as used on the form
    * dbfield - field as used in the database
    * truedisplay - how to display True to user (default 'yes')
    * falsedisplay - hot to display False to user (default 'no')
    '''

    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(tablemodel=None,
                    formfield=None,
                    dbfield=None,
                    truedisplay='yes',
                    falsedisplay='no',
                    )
        args.update(kwargs)

        # some of the args are required
        reqdfields = ['formfield', 'dbfield']
        for field in reqdfields:
            if not args[field]:
                raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))

        # set arguments as class attributes
        for key in args:
            setattr(self, key, args[key])

    def get(self, dbrow_or_id):
        """get from database for form"""
        # check if id supplied, if so retrieve dbrow
        if type(dbrow_or_id) in [int, str]:
            dbrow = self.tablemodel.query().filter_by(id=dbrow_or_id).one()
        else:
            dbrow = dbrow_or_id

        return self.truedisplay if getattr(dbrow, self.dbfield) else self.falsedisplay

    def sqla_expr(self):
        '''
        get from database when using serverside = True, for use with ColumnDT

        :return: sqlalchemy expression
        '''
        return renderboolean(
            get_dbattr(self.tablemodel, self.dbfield),
            truedisplay=self.truedisplay, falsedisplay=self.falsedisplay
        )

    def set(self, formrow):
        """set to database from form"""
        return formrow[self.formfield] == self.truedisplay

    def options(self):
        return [{'label': self.truedisplay, 'value': self.truedisplay},
                {'label': self.falsedisplay, 'value': self.falsedisplay}]


class DteDbDependent():
    '''
    define dependent options between fields

    * model - which when changed uses options from dependent model
    * modelfield - field within model to drive changes in dependent model - default 'id'
    * depmodel - dependent model
    * depmodelref - field which refers back to model
    * depmodelfield - field in dependent model which are displayed to user
    * depvaluefield - field in dependent model which is used as value for select and to retrieve record, passed on Editor interface
        default 'id' - needs to be a key for model record

    e.g.,
        class Parent(Base):
            __tablename__ = 'parent'
            id = Column(Integer, primary_key=True)
            child_id = Column(Integer, ForeignKey('child.id'))
            child = relationship("Child", backref="parent")

        class Child(Base):
            __tablename__ = 'child'
            name = Column(String)
            id = Column(Integer, primary_key=True)
            parent_id = Column( Integer, ForeignKey('parent.id') )
            parent    = relationship( 'Parent', backref='children', lazy=True )

        TODO: add more detail here -- this is confusing

        children = DteDbDependent(model=Parent,
                                  modelfield='id',
                                  depmodel=Child,
                                  depmodelref='parent',
                                  depmodelfield='name',
                                  depformfield='formfieldname',
                                  depvaluefield='id',
                                 )

        children is callable function which returns tree suitable for tables.CrudApi _update.options
    '''

    def __init__(self, **kwargs):
        # the args dict has default values for arguments added by this class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(model=None,
                    modelfield='id',
                    depmodel=None,
                    defmodelref=None,
                    depmodelfield=None,
                    depformfield=None,
                    depvaluefield='id',
                    )
        args.update(kwargs)

        # some of the args are required
        reqdfields = ['model', 'modelfield', 'depmodel', 'depmodelfield', 'depvaluefield']
        for field in reqdfields:
            if not args[field]:
                raise ParameterError('{} parameters are all required'.format(', '.join(reqdfields)))

        # set arguments as class attributes
        for key in args:
            setattr(self, key, args[key])

    def __call__(self):

        dbvals = self.model.query.all()
        vals = [getattr(v, self.modelfield) for v in dbvals]

        retoptions = {}
        for val in vals:
            retoptions[val] = {'options': {}}
            # make convenient handle
            formoptions = retoptions[val]['options'][self.depformfield] = []

            # retrieve all dependent rows which refer to val
            query = {self.depmodelref: val}
            dbopts = self.depmodel.query.filter_by(**query).all()

            # add these to the options
            for dbopt in dbopts:
                formoptions.append({'label': getattr(dbopt, self.depmodelfield),
                                    'value': getattr(dbopt, self.depvaluefield)})

        return retoptions


class DbCrudApi(CrudApi):
    '''
    This class extends CrudApi. This extension uses sqlalchemy to read / write to a database

    Additional parameters for this class:

        db: database object a la sqlalchemy
        model: sqlalchemy model for the table to read/write from
        dbmapping: mapping dict with key for each db field, value is key in form or function(dbentry)
            NOTE: this cannot be changed after __init__ because a copy is made
        formmapping: mapping dict with key for each form row, value is key in db row or function(form)
            NOTE: this cannot be changed after __init__ because a copy is made
        queryparams: dict of query parameters relevant to this table to retrieve table or rows (using filter_by())
        queryfilters: list of query criteria relevant to this table to retrieve table or rows (using filter())
        dtoptions: datatables options to override / add
        version_id_col: name of column which contains version id
        checkrequired: True causes checks of columns with className: 'field_req'

        **dbmapping** is dict like {'dbattr_n':'formfield_n', 'dbattr_m':f(form), ...}
        **formmapping** is dict like {'formfield_n':'dbattr_n', 'formfield_m':f(dbrow), ...}
        if order of operation is important for either of these use OrderedDict

        **clientcolumns** should be like the following. See https://datatables.net/reference/option/columns and
        https://editor.datatables.net/reference/option/fields for more information
            [
                { 'data': 'service', 'name': 'service', 'label': 'Service Name' },
                { 'data': 'key', 'name': 'key', 'label': 'Key', 'render':'$.fn.dataTable.render.text()' },
                { 'data': 'secret', 'name': 'secret', 'label': 'Secret', 'render':'$.fn.dataTable.render.text()' },
                { 'data': 'service', 'name': 'service_id',
                  'label': 'Service Name',
                  'type': 'selectize',
                  'options': [{'label':'yes', 'value':1}, {'label':'no', 'value':0}],
                  'opts': {
                    'searchField': 'label',
                    'openOnFocus': False
                   },
                  '_update' {
                    'endpoint' : <url endpoint to retrieve options from>,
                    'on' : <event>
                    'wrapper' : <wrapper for query response>
                  }
                {'data': 'name', 'name': 'name', 'label': 'Name',
                 'type': 'readonly',
                 '_ColumnDT_args' :
                     {'sqla_expr': localuser_invites_alias1.name},
                 'aliased': localuser_invites_alias1,
                 'onclause': localuser_invites_alias1.id == Invite.user_id,
                 },
                },
            ]
            * name - describes the column and is used within javascript
            * data - used on server-client interface and should be used in the formmapping key and dbmapping value
            * label - used for the DataTable table column and the Editor form label
            * optional render key is eval'd into javascript
            * id - is specified by idSrc, and should be in the mapping function but not columns

            additionally the update option can be used to _update the options for any type = 'select', 'selectize'
            * _update - dict with following keys
                * endpoint - url endpoint to retrieve new options
                * on - event which triggers update. supported events are
                    * 'open' - triggered when form opens (actually when field is focused)
                    * 'change' - triggered when field changes - use wrapper to indicate what field(s) are updated
                * wrapper - dict which is wrapped around query response. value '_response_' indicates where query response should be placed

            * _treatment - dict with (only) one of following keys - note this causes override of dbmapping and formmapping configuration
                * boolean - {DteDbBool keyword parameters}
                * relationship - {'editable' : { 'api':<DbCrudApi()> }}
                                    'editable' is set only if it is desired to bring up a form to edit the
                                    underlying model row

                                  'optionspicker' : <DteDbOptionsPickerBase()> based class instance
                                        OR
                                  DteDbRelationship keyword parameters (backwards compatibility)


            * _ColumnDT_args - dict with keyword arguments passed to ColumnDT for serverside processing
            * aliased - class resulting from sqlalchemy.orm.aliased()
            * onclause - expression used to limit outer join, can go with aliased
                see https://stackoverflow.com/a/46810551/799921

        **serverside** - if present table will be displayed through ajax get calls
        **set_yadcf_data** default None, passed to DataTables() -- see DataTables() above for more details
            function() which sets yadcf_data_x in editor query response; see
            https://github.com/vedmack/yadcf/blob/master/src/jquery.dataTables.yadcf.js Server-side
            processing API

        **version_id_col** - if present edits to this table are protected using optimistic concurrency control
          * https://docs.sqlalchemy.org/en/13/orm/versioning.html
          * see https://en.wikipedia.org/wiki/Optimistic_concurrency_control
          * also https://martinfowler.com/eaaCatalog/optimisticOfflineLock.html
          * this column is automatically added to dbmapping, formmapping and clientcolumns
          * e.g., for version_id_col='version_id', database model for this table should have code like
                ```
                version_id          = Column(Integer, nullable=False)
                __mapper_args__ = {
                    'version_id_col' : version_id
                }
                ```
    '''

    # class specific imports here so users of other classes do not need to install

    def __init__(self, **kwargs):
        if debug: current_app.logger.debug('DbCrudApi.__init__()')

        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(db=None,
                    model=None,
                    dbmapping={},
                    formmapping={},
                    version_id_col=None,
                    serverside=False,  # duplicated here and in CrudApi because test before super() called
                    set_yadcf_data=None,
                    queryparams={},
                    queryfilters=[],
                    dtoptions={},
                    filtercoloptions=[],
                    checkrequired=None,  # TODO: should this be made more general? Maybe a function to check col
                    )
        args.update(kwargs)

        # make sure '_treatment', '_unique' and '_ColumnDT_args' column options are removed before invoking DataTables and Editor
        args['filtercoloptions'] += ['_treatment', '_unique', '_ColumnDT_args']

        # make copy of dbmapping and formmapping
        # Need to do this because we update the mapping with functions.
        # view class gets reinstantiated when page painted, so we'll need to make sure we
        # don't corrupt the original data
        self.formmapping = deepcopy(args['formmapping'])
        self.dbmapping = deepcopy(args['dbmapping'])

        # keep track of columns which must be unique in the database
        self.uniquecols = []

        # update parameters if version_col_id is specified
        version_id_col = args['version_id_col']
        if version_id_col:
            self.occupdate = False
            self.formmapping[version_id_col] = version_id_col
            self.dbmapping[version_id_col] = lambda form: int(form['version_id']) if form['version_id'] else 0
            versioncol = {
                'name': version_id_col,
                'data': version_id_col,
                'ed': {'type': 'hidden'},
                'dt': {'visible': False},
            }
            # this code comes through multiple times so need to prevent from being added twice
            # should consider alternative of deepcopy() like mapping arguments
            if version_id_col not in [c['data'] for c in args['clientcolumns']]:
                args['clientcolumns'].append(versioncol)

        # for serverside processing, self.servercolumns is built up from column data
        if args['serverside']:
            # keep track of needed columns, args, and joins
            # serverargs is used to simulate Editor query args for editRefresh
            self.servercolumns = []
            self.joins = []

        # do some preprocessing on columns
        booleandb = {}
        booleanform = {}
        self.saforms = []
        for col in args['clientcolumns']:
            if debug: current_app.logger.debug('__init__(): col = {}'.format(col))
            # remove readonly fields from dbmapping
            if col.get('type', None) == 'readonly':
                # this assumes db attribute is named the same as form attribute #25
                self.dbmapping.pop(col['name'], None)

            # need to peel off column dt args before checking col['data'] == None
            _columndt_args = col.get('_ColumnDT_args', {})

            # certain use cases require data=None and therefore no dbattr exists,
            # e.g., child row handling
            # if serverside=True put in placeholder ColumnDT column so indeces for
            # datatables(js) and sqlalchemy-datatables(py) line up, but don't do anything else for this column
            if col['data'] == None or col['data'] == '':
                if args['serverside']:
                    columndt_args = {'sqla_expr': getattr(args['model'], 'id'), 'mData': '_placeholder'}
                    columndt_args.update(**_columndt_args)
                    self.servercolumns.append(ColumnDT(**columndt_args))
                continue

            # need formfield and dbattr for a couple of things
            formfield = col['data']
            # this assumes db attribute is named the same as form attribute (may be function) #25
            dbattr = self.formmapping.get(formfield, None)
            
            # if dbattr not found in form mapping, can skip this field. There may be special handling, e.g., in self.nexttablerow()
            if not dbattr:
                continue

            # maybe this column needs to be unique
            if col.get('_unique', False):
                self.uniquecols.append(dbattr)

            # check for special treatment for column
            treatment = col.get('_treatment', None)
            if debug: current_app.logger.debug('__init__(): treatment = {}'.format(treatment))

            # no special treatment is the norm
            if not treatment:
                # make sure mapping doesn't get executed if readonly
                if col.get('type', None) == 'readonly':
                    # special value detected in set_dbrow before setattr attempted
                    self.dbmapping[dbattr] = '__readonly__'

                # some special processing to check for subrecords, unless there's a function
                if not callable(dbattr):
                    branches = dbattr.split('.')
                    if len(branches) == 1:
                        # server side tables adds ColumnDT for page paint
                        if args['serverside']:
                            columndt_args = {'sqla_expr': getattr(args['model'], dbattr, None), 'mData':formfield}
                            columndt_args.update(**_columndt_args)
                            # need to check for type(None) because Boolean value of an sqla expression is not defined
                            if type(columndt_args['sqla_expr']) == type(None):
                                raise ParameterError('formmapping[dbattr] or _ColumnDT_args[\'sqla_expr\'] must be specified')
                            self.servercolumns.append(ColumnDT(**columndt_args))

                    # special processing if db attribute implies subrecord
                    # only know how to handle two levels now
                    elif len(branches) == 2:
                        # submodel is one level down
                        submodelname = branches[0]
                        submodel = getattr(args['model'], submodelname).prop.entity.class_
                        if 'aliased' in col:
                            submodel = col['aliased']
                        subfield = branches[1]
                        onclause = None
                        if 'onclause' in col:
                            onclause = col['onclause']
                        thisreln = DteDbSubrec(
                            model=submodel,
                            field=submodelname,
                            subfield=subfield,
                            formfield=formfield,
                            onclause=onclause,
                        )
                        self.formmapping[formfield] = thisreln.get

                        # server side tables adds ColumnDT for page paint
                        if args['serverside']:
                            columndt_args = {'sqla_expr': getattr(submodel, subfield), 'mData':formfield}
                            columndt_args.update(**_columndt_args)
                            self.servercolumns.append(ColumnDT(**columndt_args))
                            if submodel not in self.joins:
                                # if debug: print('DbCrudApi: self {} joining {}'.format(args['model'], submodel))
                                thisjoin = submodel
                                if type(thisreln.onclause) != type(None):
                                    thisjoin = {'model': submodel, 'onclause': thisreln.onclause}
                                addjoin = True
                                if thisjoin in self.joins:
                                    addjoin = False
                                # don't add duplicate submodel join
                                if isinstance(thisjoin, dict):
                                    if ((thisjoin['model'], thisjoin['onclause']) in
                                            [(j['model'], j['onclause']) for j in self.joins if isinstance(j, dict)]):
                                        addjoin = False
                                if addjoin:
                                    # if debug: print('DbCrudApi: self {} joining {}'.format(args['model'], subsubmodel))
                                    self.joins.append(thisjoin)

                            # db processing section
                            ## save handler, set data to db using handler set function
                            ## for now, make this a noop, and readonly. See loutilities.tables.DataTablesEditor.set_dbrow()
                            # self.dbmapping[dbattr] = thisreln.set        #TODO: doesn't work

                    else:
                        raise ParameterError('can\'t handle more than 2 levels of dbattr yet')

            # special treatment required
            else:
                if not isinstance(treatment, dict) or len(treatment) != 1 or list(treatment.keys())[0] not in ['boolean',
                                                                                                 'relationship']:
                    raise ParameterError('invalid treatment: {}'.format(treatment))

                # handle boolean treatment
                if 'boolean' in treatment:
                    thisbool = DteDbBool(tablemodel=args['model'], **treatment['boolean'])
                    col['type'] = 'select2'
                    col['opts'] = {'minimumResultsForSearch': 'Infinity'}

                    # form processing section
                    ## save handler, get data from database using handler get function, update form to call handler options when options needed
                    booleanform[formfield] = thisbool
                    col['options'] = booleanform[formfield].options

                    # table modifies getter to handle boolean values
                    self.formmapping[formfield] = booleanform[formfield].get

                    # server side tables adds ColumnDT to handle boolean values for page paint
                    if args['serverside']:
                        # yadcf_autocomplete because this forces direct comparison. See sqlalchemy-datatables.search_methods
                        # this is probably a kludge, as here we have no idea what 'yadcf_autocomplete' means
                        columndt_args = {'sqla_expr': thisbool.sqla_expr(), 'mData': formfield,
                                         'search_method': 'yadcf_autocomplete'}
                        columndt_args.update(**_columndt_args)
                        self.servercolumns.append(ColumnDT(**columndt_args))

                        # db processing section
                    ## save handler, set data to db using handler set function
                    booleandb[dbattr] = thisbool
                    self.dbmapping[dbattr] = booleandb[dbattr].set

                # handle relationship treatment
                if 'relationship' in treatment:
                    # now create the relationship
                    if 'optionspicker' in treatment['relationship']:
                        thisreln = treatment['relationship']['optionspicker']
                    else:
                        thisreln = DteDbRelationship(tablemodel=args['model'], **treatment['relationship'])
                    col.update(thisreln.col_options())

                    # get original formfield and dbattr
                    # TODO: should this come from 'name' or 'data'?
                    ## actually name and data should be the same value, name for editor and data for datatable
                    ## see https://editor.datatables.net/examples/simple/join.html

                    # form processing section
                    ## save handler, get data from form using handler get function, update form to call handler options when options needed
                    # relationshipform[formfield] = thisreln

                    # table modifies getter to handle associated values
                    self.formmapping[formfield] = thisreln.get

                    # server side tables adds ColumnDT for page paint
                    if args['serverside']:
                        sqla_expr = thisreln.sqla_expr()
                        # louking / members  #152 (search for this to find required matching code)
                        self.servercolumns += thisreln.col_dt_list(**_columndt_args)

                        # need to add join of this relationship
                        if type(sqla_expr) == InstrumentedAttribute:
                            subsubmodel = sqla_expr.class_
                            thisjoin = subsubmodel
                            if type(thisreln.onclause) != type(None):
                                thisjoin = {'model': subsubmodel, 'onclause': thisreln.onclause}
                            if thisjoin not in self.joins:
                                # print('DbCrudApi: self {} joining {}'.format(args['model'], subsubmodel))
                                self.joins.append(thisjoin)

                    # db processing section
                    ## save handler, set data to db using handler set function
                    self.dbmapping[dbattr] = thisreln.set

                    ## if this field needs form for editing the record it points at, remember information
                    editable = treatment['relationship'].get('editable', {})
                    if debug: current_app.logger.debug(
                        '__init__(): labelfield={} editable={}'.format(treatment['relationship']['labelfield'],
                                                                       editable))
                    valuefield = thisreln.valuefield
                    labelfield = thisreln.labelfield
                    formfield = thisreln.formfield
                    if editable:
                        self.saforms.append({'api': editable['api'],
                                             'args': {'labelfield': labelfield, 'valuefield': valuefield,
                                                      'parentfield': formfield}})
                        # bring in standalone forms from subforms, create parent arg if not already present
                        # parent arg may be present from a deeper subform
                        for saform in editable['api'].saforms:
                            thisform = saform
                            if 'parent' not in saform['args']:
                                thisform = {}
                                thisform['api'] = saform['api']
                                # make copy so we don't corrupt xxx.saforms
                                thisform['args'] = copy(saform['args'])
                                thisform['args']['parent'] = '{}_editor'.format(thisreln.labelfield)
                            self.saforms.append(thisform)
                        # add <new> option
                        col['options'] = thisreln.new_plus_options
                        # this is for #65, abandoned for first release
                        # col['opts'].update({'tags':True, 'createTag': {'eval':'select2_createtag'}})
                        # col['options'] = thisreln.options
                    else:
                        col['options'] = thisreln.options
                        col['options'] = thisreln.options

                    # convert this column for dt and ed configuration
                    # this conversion happens with super(DbCrudApi, self).__init__(**args)
                    # column attributes are updated based on 'dtonly', 'edonly' at very end of initialization
                    if 'data' in col:
                        col.setdefault('dt', {}).update({'data': '{}.{}'.format(col['data'], thisreln.labelfield)})
                        col.setdefault('ed', {}).update({'data': '{}.{}'.format(col['data'], thisreln.valuefield)})
                    if 'name' in col:
                        col.setdefault('dt', {}).update({'name': '{}.{}'.format(col['name'], thisreln.labelfield)})
                        col.setdefault('ed', {}).update({'name': '{}.{}'.format(col['name'], thisreln.valuefield)})

        # from pprint import PrettyPrinter
        # pp = PrettyPrinter()
        # if debug: current_app.logger.debug('args["columns"]={}'.format(pp.pformat(args['clientcolumns'])))

        # for serverside processing, self.servercolumns is built up from column data
        # because of https://github.com/Pegase745/sqlalchemy-datatables/issues/131 we need to make sure that
        # indexes given to sqlalchemy-datatables (python pypi package) line up with those given to DataTables (js)
        if args['serverside']:
            # finish with model.id
            # this is put at the end to make sure the column index inside sqlalchemy-datatables (python pypi package)
            # is the same as what is given to DataTables (javascript)
            self.servercolumns += [ColumnDT(getattr(args['model'], 'id'), mData=self.dbmapping['id'])]

            # kludge to prevent https://github.com/louking/members/issues/156
            # push any field.id ColumnDT instances to end of list; scan from end so earlier indices don't change
            for ndx in range(len(self.servercolumns)-1, 0, -1):
                mdata = getattr(self.servercolumns[ndx], 'mData', None)
                if mdata:
                    splitmdata = mdata.split('.')
                    # if this is an object notation with 'id' field, move to end of list
                    if len(splitmdata) > 1 and splitmdata[-1] == 'id':
                        self.servercolumns.append(self.servercolumns.pop(ndx))


        # set up mapping between database and editor form
        # Note: translate '' to None and visa versa
        self.dte = DataTablesEditor(self.dbmapping, self.formmapping, null2emptystring=True)

        # initialize inherited class, and a couple of attributes
        super(DbCrudApi, self).__init__(**args)

        # if any standalone forms required, add to templateargs
        if self.saforms:
            self.saformjsurls = lambda: [saf['api'].saformurl(**saf['args']) for saf in self.saforms]
            self.templateargs['saformjsurls'] = self.saformjsurls

        # save caller's validation method and update validation to local version
        self.callervalidate = self.validate
        self.validate = self.validatedb
        if debug: current_app.logger.debug('updated validate() to validatedb()')

    def get(self):

        # this returns editor options for this model class
        # this can be used to have a create or edit form accessed from any type of view
        if request.path[-7:] == '/saform':
            edoptions = self.getedoptions()
            return jsonify({'edoptions': edoptions})

        # this allows standalone editor form to be created for this model class from another model class
        # through a select2 control on a datatables view
        # NOTE: request.args need to match keyword args in self.saformurl()
        elif request.path[-9:] == '/saformjs':
            ed_options = self.getedoptions()

            # indent all by 4 and use indent=2 to make debugging easy
            edoptsjson = ['    {}'.format(l) for l in dumps(ed_options, indent=2).split('\n')]

            labelfield = request.args['labelfield']
            parentfield = request.args['parentfield']
            valuefield = request.args['valuefield']
            parent = request.args.get('parent', 'editor')
            js = [
                'var {}_{}_lastval;'.format(parentfield, valuefield),
                'var {}_editor;'.format(labelfield),

                # first one of these initializes stack variable
                'if ( typeof editorstack == "undefined" ) {',
                '    var editorstack = [];',
                '    var curreditor = editor;',
                '    var pushing = false;',
                '    var restoring = false;',
                '    var parentbuttons;',
                '}',
                '',
                '$( function () {',
                # NOTE: this assumes editor has been defined by an earlier $([ready]) function
                '  if ( editorstack.length == 0 ) {',
                '      curreditor = editor;',
                '  }',
                '',
                '  if ( typeof pusheditor == "undefined" ) {',
                '      function pusheditor( neweditor, parentname, buttons, editorname ) {',
                '        var fields = {};',
                '        $.each(curreditor.order(), function(i, field) {',
                '            fields[field] = curreditor.field(field).get();',
                '        });',
                '        pushing = true;',
                '',
                '        var mode = curreditor.mode();',
                '        // true parameter below is includeHash, required to get the right rows ',
                '        var ids = curreditor.ids( true );',
                # TODO: make this generic to accept a variety of button configurations
                '        if (mode == \'create\') {',
                '            parentbuttons = [',
                '                       {',
                '                        label: "Cancel",',
                '                        fn: function () {',
                '                              this.close();',
                '                        },',
                '                       },',
                '                       {',
                '                        label: "Create",',
                '                        fn: function () {',
                '                              this.submit( );',
                '                        },',
                '                       },',
                '            ];',
                '        } else if (mode == \'edit\') {',
                '            parentbuttons = [',
                '                       {',
                '                        label: "Cancel",',
                '                        fn: function () {',
                '                              this.close();',
                '                        },',
                '                       },',
                '                       {',
                '                        label: "Update",',
                '                        fn: function () {',
                '                              this.submit( );',
                '                        },',
                '                       },',
                '            ];',
                '        }',
                '',
                '        curreditor.close()',
                '        pushing = false;',
                # need to map / extend to make a copy of parentbuttons
                '        editorstack.push( { editor:curreditor, newcurrent:editorname, mode:mode, ids:ids, fields:fields, buttons:parentbuttons.map(a => $.extend(true, {}, a)) } );',
                '        parentbuttons = buttons;',
                '        curreditor = neweditor;',
                # 'console.log("pusheditor(): newcurrent=" + editorname + " depth="+editorstack.length);',
                # '$.each(editorstack, function(i,val) { console.log("editorstack["+i+"].fields="+JSON.stringify(val.fields)) });',
                '      }',
                '',
                '      function popeditor( ) {',
                '          editorrec = editorstack.pop();',
                '          curreditor = editorrec.editor;',
                '          buttons = editorrec.buttons;',
                # '        if ( curreditor != editor ) {',
                # handle buttons specially for top level editor
                # requires special handling above
                '          if (editorrec.mode == \'create\') {',
                '              curreditor',
                '                .buttons( buttons )',
                '                .create();',
                '          } else if (editorrec.mode == \'edit\') {',
                '              curreditor',
                '                .buttons( buttons )',
                '                .edit(editorrec.ids);',
                '          }',
                '          restoring = true;',
                '          $.each(editorrec.fields, function(field, val) {',
                '              curreditor.field(field).set( val );',
                '          });',
                '          restoring = false;',
                # '        } else {',
                # '          curreditor.open( );',
                # '        }',
                # 'console.log("popeditor(): depth="+editorstack.length);',
                # '$.each(editorstack, function(i,val) { console.log("editorstack["+i+"].fields="+JSON.stringify(val.fields)) });',
                # 'console.trace();',
                '      }',
                '  }',
                '',
                '  // handle save, then open parent on submit',
                '  var fieldname = "{}.{}"'.format(labelfield, valuefield),
                '  var parentname = "{}.{}"'.format(parentfield, valuefield),
                '  var {label}_buttons = ['.format(label=labelfield),
                '                 {',
                '                  label: "Cancel",',
                '                  fn: function () {',
                '                        this.close();',
                # this is needed here and also on close
                # '                        editor.field( fieldname ).set( {}_{}_lastval );'.format(parentfield, valuefield),
                # '                        popeditor( );',
                '                  },',
                '                 },',
                '                 {',
                '                  label: "Create",',
                '                  fn: function () {',
                '                        this.submit( function(resp) {',
                # resp.data needs to be converted to string in case select2 is uselist=True
                '                              // at this point curreditor is back to parent form',
                '                              var newval = {{label:resp.data[0].{}, value:resp.data[0].{}.toString()}};'.format(
                    labelfield, self.idSrc),
                '                              curreditor.field( parentname ).AddOption( [ newval ] );',
                '                              if ( curreditor.field( parentname ).isMultiSelect() ) {',
                '                                  var sep = curreditor.field( parentname ).separator();',
                '                                  var thevals = [curreditor.field( parentname ).get( ), newval.value].join(sep);',
                '                                  curreditor.field( parentname ).set( thevals );',
                '                              } else {',
                '                                  curreditor.field( parentname ).set( newval.value );',
                '                              } ',
                '                           },',
                '                        )',
                '                  },',
                '                 },',
                '                ];',
                '  $( {}.field( parentname ).input() ).on ("select2:open", function () {{'.format(parent),
                '    {}_{}_lastval = {}.get( parentname );'.format(parentfield, valuefield, parent),
                '  } );',
                '  $( {}.field( parentname ).input() ).on ("change", function (e) {{'.format(parent),
                # '    console.log("{} select2 change fired");'.format(parentfield),
                '    // only fire if <new> entry in field -- check if null first',
                # need to split by SEPARATOR in case select2 is uselist=True
                '    var parentfield = {}.get( parentname );'.format(parent),
                '    if ( parentfield == null ) return;',
                '    var parentitems = parentfield.split(\'{}\');'.format(SEPARATOR),
                '    if ( !parentitems.includes("0") ) return;',
                '    // no fire if restoring',
                '    if ( restoring ) return;',
                # this is for #65, abandoned for first release
                # '    // ignore initialization',
                # '    if ( !e.params ) return;',
                # '    // only fire if new entry',
                # '    if ( !e.params.data.isNew ) return;',
                '',
                '    pusheditor( {label}_editor, parentname, {label}_buttons, "{label}_editor" );'.format(
                    label=labelfield),
                '',
                '    {}_editor'.format(labelfield),
                "      .title('Create new entry')",
                '      .buttons( {label}_buttons )'.format(label=labelfield),
                '      .create();',
                '  } );',
                '',
                '  {}_editor = new $.fn.dataTable.Editor( '.format(labelfield),
            ]

            js += edoptsjson

            js += [
                '  );',
                '  // if form closes, reopen previous editor',
                '  {}_editor'.format(labelfield),
                '    .on("close", function () {',
                # this is needed here and also when cancel button is pressed
                # don't pop if in the middle of pushing
                '      if (!pushing) {',
                '        popeditor( );',
                '        curreditor.field( parentname ).set( {}_{}_lastval );'.format(parentfield, valuefield),
                '      };',
                '  });',
                '',
                # set the width for this form
                # '  {}_editor.__dialouge.dialog( "option", "width", 600 );'.format(labelfield),

            ]

            js += self.saformpostjs('{}_editor'.format(labelfield))

            js += [
                '} );',
            ]
            # see https://stackoverflow.com/questions/11017466/flask-return-image-created-from-database
            response = make_response('\n'.join(js))
            response.headers.set('Content-Type', 'application/javascript')
            return response

        # otherwise handle get from base class
        else:
            return super(DbCrudApi, self).get()

    def saformpostjs(self, saeditor):
        '''
        this may be overridden

        this gives subclass ability to add additional javascript code to saformjs handler
        (see self.get elif request.path[-9:] == '/saformjs':)

        this code is added after standalone form created, as saeditor

        :param saeditor: name of variable which holds standalone form
        :return: list of additional javascript strings
        '''
        return []

    def saformurl(self, **kwargs):
        '''
        standalone form url
        '''
        # NOTE: keyword arguments need to match request.args access in self.get()
        args = urlencode(kwargs)
        # self.__name__ is endpoint -- see https://github.com/pallets/flask/blob/master/flask/views.py View.as_view method
        url = '{}/saformjs?{}'.format(url_for('.' + self.my_view.__name__), args)
        return url

    def register(self):
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        # create the inherited class endpoints, as by product my_view attribute is initialized
        super(DbCrudApi, self).register()
        self.app.add_url_rule('{}/saformjs'.format(self.rule), view_func=self.my_view, methods=['GET', ])
        self.app.add_url_rule('{}/saform'.format(self.rule), view_func=self.my_view, methods=['GET', ])

    def serverquery(self):
        # filter applies to self.model
        query = self.db.session.query().select_from(self.model).filter_by(**self.queryparams).filter(*self.queryfilters)

        # add required joins (determined in __init__)
        for j in self.joins:
            if isinstance(j, dict):
                model = j['model']
                onclause = j['onclause']
            else:
                model = j
                onclause = None
            if type(onclause) != type(None):
                query = query.outerjoin(model, onclause)
            else:
                query = query.outerjoin(model)

        return query

    def open(self):
        '''
        retrieve all the data in the indicated table
        '''
        if debug: current_app.logger.debug('DbCrudApi.open()')
        if debug: current_app.logger.debug('DbCrudApi.open: self.db = {}, self.model = {}'.format(self.db, self.model))

        # not server table, rows will be handled in nexttablerow()
        if not self.serverside:
            query = self.model.query.filter_by(**self.queryparams).filter(*self.queryfilters)
            self.rows = iter(query.all())

        # server table, this is the output to be returned, nexttablerow() is noop
        # note get_response_data transform is not done - name mapping is in self.servercolumns
        else:
            args = request.args.to_dict()
            rowTable = DataTables(args, self.serverquery(), self.servercolumns, set_yadcf_data=self.set_yadcf_data)
            output = rowTable.output_result()

            if 'error' in output:
                self._error = output['error']
                raise ParameterError(self._error)

            self.objectifyrows(output['data'])
            self.output_result = output

    def nexttablerow(self):
        '''
        since open has done all the work, tell the caller we're done
        '''
        if debug: current_app.logger.debug('DbCrudApi.nexttablerow()')

        # not server table, need to do translation
        if not self.serverside:
            dbrecord = next(self.rows)
            return self.dte.get_response_data(dbrecord)

        # server table
        else:
            # nothing to do, all done in open()
            raise StopIteration

    def close(self):
        if debug: current_app.logger.debug('DbCrudApi.close()')
        pass

    def validatedb(self, action, formdata):
        if debug: current_app.logger.debug('DbCrudApi.validatedb({})'.format(action))

        # no validatation done if refresh action
        if action == 'refresh': return []

        # check results of caller's validation
        results = self.callervalidate(action, formdata)

        # check required fields if requested
        # TODO: this should be made more general, and possibly moved lower in the chain to CrudApi
        if self.checkrequired:
            for col in self.clientcolumns:
                field = col['data']
                if 'className' in col and 'field_req' in col['className'].split(' '):
                    if not isinstance(formdata[field], str) and 'id' in formdata[field]:
                        if not formdata[field]['id']:
                            results.append({'name': '{}.id'.format(field), 'status': 'please select'})
                    elif not formdata[field]:
                        results.append({'name': field, 'status': 'please supply'})

        # check if any records conflict with uniqueness requirements
        if action == 'create' and self.uniquecols:
            dbrow = self.model()
            self.dte.set_dbrow(formdata, dbrow)
            for field in self.uniquecols:
                # if debug: current_app.logger.debug('DbCrudApi.validatedb(): checking field "{}":"{}"'.format(field,getattr(dbrow,field)))
                # TODO: it isn't clear that we want to do all this filtering before checking uniqueness
                rows = self.model.query.filter_by(**self.queryparams).filter_by(**{field: getattr(dbrow, field)}).filter(*self.queryfilters).all()
                # if we found a row that matches, flag error

                # looking to see if we found any rows which aren't the row we're currently working on
                # the row we are working on can be found if there's a list of subrecords hanging off of
                # this record thru one to many relationship
                if (len(rows) == 1 and rows[0].id != dbrow.id) or len(rows) >= 2:
                    results.append({'name': field, 'status': 'duplicate found, must be unique'})

            # clear out dbrow from sqlalchemy
            self.db.session.rollback()

        return results

    def createrow(self, formdata):
        '''
        creates row in database

        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        # create item
        dbrow = self.model()

        if debug: current_app.logger.debug('createrow(): self.dbmapping = {}'.format(self.dbmapping))

        self.dte.set_dbrow(formdata, dbrow)
        if debug: current_app.logger.debug('createrow(): creating dbrow={}'.format(dbrow.__dict__))

        self.db.session.add(dbrow)
        if debug: current_app.logger.debug('createrow(): created dbrow={}'.format(dbrow.__dict__))

        self.db.session.flush()
        if debug: current_app.logger.debug('createrow(): flushed dbrow={}'.format(dbrow.__dict__))

        # kludge to allow access to this new db row within editor_method_posthook()
        self.created_id = dbrow.id

        # prepare response
        thisrow = self.dte.get_response_data(dbrow)
        return thisrow

    def updaterow(self, thisid, formdata):
        '''
        updates row in database

        :param thisid: id of row to be updated
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        if debug: current_app.logger.debug('updaterow({},{})'.format(thisid, formdata))

        # critical region
        lock = RLock()
        with lock:
            # edit item
            queryparams = {
                'id': thisid,
            }
            # some edit modes do not supply version id from form (inline editing, e.g.)
            if self.version_id_col and self.version_id_col in formdata:
                queryparams[self.version_id_col] = formdata[self.version_id_col]
            dbrow = self.model.query.filter_by(**queryparams).one_or_none()

            # found correct version
            if dbrow:
                if debug: current_app.logger.debug('editing id={} dbrow={}'.format(thisid, dbrow.__dict__))
                self.dte.set_dbrow(formdata, dbrow)
                if debug: current_app.logger.debug('after edit id={} dbrow={}'.format(thisid, dbrow.__dict__))

                # flush in case of version_id update
                self.db.session.flush()

                # prepare response
                thisrow = self.dte.get_response_data(dbrow)
                return thisrow

            # someone else edited the row
            else:
                self._error = 'Someone updated this record while your edit form was open -- close the form and try your edit again'
                raise staleData

        # couldn't get this to work -- was getting weird error during update about State (or other records)
        # not being boolean
        ## updatefields = self.dte.set_dbrow_update(formdata)
        ## print 'updatefields = {}'.format(updatefields)
        ## self.model.query.filter_by(id=thisid).update(updatefields)
        ## updatedrow = self.model.query.filter_by(id=thisid).one()

    def deleterow(self, thisid):
        '''
        deletes row in database

        :param thisid: id of row to be updated
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        dbrow = self.model.query.filter_by(id=thisid).one()
        if debug: current_app.logger.debug('deleting id={} dbrow={}'.format(thisid, dbrow.__dict__))
        self.db.session.delete(dbrow)

        return []

    def refreshrows(self, ids):
        '''
        refresh row(s) from database

        :param ids: comma separated ids of row to be refreshed
        :rtype: list of returned rows for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        theseids = ids.split(',')
        responsedata = []
        for thisid in theseids:
            if not self.serverside:
                dbrow = self.model.query.filter_by(id=thisid).one()
                responsedata.append(self.dte.get_response_data(dbrow))

            # if serverside, get data from database using same query as page paint, limited by ids
            else:
                # set up generic "request args" for DataTables, will be retrieving only one row at a time for the refresh
                args = {
                    'columns': [],
                    'draw': 1,
                    'start': 0,
                    'length': -1,
                    'search': {'value': '', 'regex': False},
                }
                rowTable = DataTables(args, self.serverquery().filter(self.model.id==thisid), self.servercolumns, set_yadcf_data=self.set_yadcf_data)
                output = rowTable.output_result()

                if 'error' in output:
                    self._error = output['error']
                    raise ParameterError(self._error)

                self.objectifyrows(output['data'])
                responsedata += output['data']

        return responsedata

    def objectifyrows(self, rows):
        '''
        take items in object notation and make into object

        :param rows: rows on which to operate
        :return: None
        '''
        # kludge? to take items in object notation, and make into object
        # louking/members#152 (search for this to find required matching code
        # TODO: only handles one level deep - should we make this recursive?
        for row in rows:
            delfields = []
            addfields = {}
            for field in row:
                splitobj = field.split('.')
                # if there are multiple levels to the fieldname, need to make it into an object
                if len(splitobj) > 1:
                    # this will cause exception if more than two levels; that's ok for now, see todo above
                    parent, child = splitobj
                    addfields.setdefault(parent, {})
                    addfields[parent][child] = row[field]
                    delfields.append(field)
            row.update(addfields)
            for field in delfields:
                del row[field]

    def commit(self):
        self.db.session.commit()

    def rollback(self):
        self.db.session.rollback()


class DbCrudApiRolePermissions(DbCrudApi):
    '''
    This class extends DbCrudApi which, in turn, extends CrudApi. This extension uses flask_security
    to do role checking for the current user.

    Caller should use roles_accepted OR roles_required but not both.

    Additional parameters for this class:

        roles_accepted: None, 'role', ['role1', 'role2', ...] - user must have at least one of the specified roles
        roles_required: None, 'role', ['role1', 'role2', ...] - user must have all of the specified roles
    '''
    from flask_security import current_user

    def __init__(self, **kwargs):
        if debug: current_app.logger.debug('DbCrudApiRolePermissions.__init__()')

        # the args dict has default values for arguments added by this derived class
        # caller supplied keyword args are used to update these
        # all arguments are made into attributes for self by the inherited class
        args = dict(roles_accepted=None, roles_required=None)
        args.update(kwargs)

        # this initialization needs to be done before checking any self.xxx attributes
        super(DbCrudApiRolePermissions, self).__init__(**args)

        # Caller should use roles_accepted OR roles_required but not both
        if self.roles_accepted and self.roles_required:
            raise ParameterError('use roles_accepted OR roles_required but not both')

        # assure None or [ 'role1', ... ]
        if self.roles_accepted and not isinstance(self.roles_accepted, list):
            self.roles_accepted = [self.roles_accepted]
        if self.roles_required and not isinstance(self.roles_required, list):
            self.roles_required = [self.roles_required]

    def permission(self):
        '''
        determine if current user is permitted to use the view
        '''
        if debug: current_app.logger.debug('DbCrudApiRolePermissions.permission()')
        if debug: current_app.logger.debug(
            'permission: roles_accepted = {} roles_required = {}'.format(self.roles_accepted, self.roles_required))

        # if no roles are asked for, permission granted
        if not self.roles_accepted and not self.roles_required:
            allowed = True

        # if user has any of the roles_accepted, permission granted
        elif self.roles_accepted:
            allowed = False
            for role in self.roles_accepted:
                if self.current_user.has_role(role):
                    allowed = True
                    break

        # if user has all of the roles_required, permission granted
        elif self.roles_required:
            allowed = True
            for role in self.roles_required:
                if not self.current_user.has_role(role):
                    allowed = False
                    break

        return allowed


class CrudFiles(MethodView):
    '''
    provides files support for CrudApi

    usage:
        filesinst = CrudFiles([arguments]):
        apiinst - CrudApi(files=filesinst, [other arguments])
        apiinst.register()
    '''

    def __init__(self, **kwargs):
        # the args dict has all the defined parameters to
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        if debug: print('CrudFiles.__init__() **kwargs={}'.format(kwargs))

        self.kwargs = kwargs
        args = dict(app = None,
                    uploadendpoint = None, 
                    uploadrule = None,  # defaults to '/' + uploadendpoint
                    endpointvalues = {},
                    )
        args.update(kwargs)        
        for key in args:
            setattr(self, key, args[key])

        # uploadrule defaults to '/' + uploadendpoint
        self.uploadrule = self.uploadrule or ('/' + self.uploadendpoint)

        self.credentials = None

    def register(self):
        # name for view is last bit of fully named endpoint
        name = self.uploadendpoint.split('.')[-1]

        # # create supported endpoints
        # list_view = self.as_view(self.listendpoint, **self.kwargs)
        # self.app.add_url_rule('/{}'.format(self.listendpoint),view_func=list_view,methods=['GET',])
        if debug: print('CrudFiles.register()')

        upload_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.uploadrule, **self.endpointvalues),view_func=upload_view,methods=['POST',])


    @_uploadmethod()
    def post(self):
        self._responsedata = self.upload()

    #----------------------------------------------------------------------
    # the following methods must be replaced in subclass
    #----------------------------------------------------------------------
    
    def list(self):
        '''
        must be overridden

        return list of files

        return value must be set to the following, as defined in https://editor.datatables.net/manual/server#File-upload

             {
                table1 : {
                            fileid1 : metadata1,
                            fileid2 : metadata2,
                            ...
                         },
                table2 : {
                            etc.
                         }
             }

        where:
            tablename is name for table which will be stored in DataTables and Editor
            fileid is scalar file identifier, e.g., database id
            metadata is dict describing file, e.g., 
                'filename' : filename
                'web_path' : path to file, etc

        
        :rtype: return value as described above
        '''
        pass

    def upload(self):
        '''
        must override, but this must be called

        receive an uploaded file

        returnvalue dict must include at least 
        the following keys, as defined in 
        https://editor.datatables.net/manual/server#File-upload

            {
             'upload' : {'id': fileid },
             'files'  : {
                        table : {
                            fileid : metadata
                        },
             optkey1  : optdata1
            ...
            }


        where:
            fileid is scalar file identifier, e.g., database id
            tablename is name for table which will be stored in DataTables and Editor
            metadata is dict describing file, e.g., 
                'filename' : filename
                'web_path' : path to file, etc
            optkeyn is optional key

        if optional keys are provided will be sent along with the data 

        :rtype: return value as described above
        '''
        pass


def deepupdate(obj, val, newval):
    '''
    recursively searches obj object and replaces any val values with newval
    does not update opj
    returns resultant object
    
    :param obj: object which requires updating
    :param val: val to look for
    :param newval: replacement for val
    '''
    thisobj = deepcopy(obj)

    if isinstance(thisobj, dict):
        for k in thisobj:
            thisobj[k] = deepupdate(thisobj[k], val, newval)

    elif isinstance(thisobj, list):
        for k in range(len(thisobj)):
            thisobj[k] = deepupdate(thisobj[k], val, newval)

    else:
        if thisobj == val:
            thisobj = newval

    return thisobj


# form validation
class TimeOptHoursConverter(TimeConverter):
    use_seconds = True
    use_ampm = False
    use_float_secs = True
    
    def _convert_to_python(self, value, state):
        parts = value.split(':')
        if len(parts) == 2:
            value = f'0:{value}'
        return super()._convert_to_python(value, state)

    # copied from formencode.validators.TimeConverter, updated to allow float seconds
    def _to_python_tuple(self, value, state):
        time = value.strip()
        explicit_ampm = False
        if self.use_ampm:
            last_two = time[-2:].lower()
            if last_two not in ('am', 'pm'):
                if self.use_ampm != 'optional':
                    raise Invalid(self.message('noAMPM', state), value, state)
                offset = 0
            else:
                explicit_ampm = True
                offset = 12 if last_two == 'pm' else 0
                time = time[:-2]
        else:
            offset = 0
        parts = time.split(':', 3)
        if len(parts) > 3:
            raise Invalid(self.message('tooManyColon', state), value, state)
        if len(parts) == 3 and not self.use_seconds:
            raise Invalid(self.message('noSeconds', state), value, state)
        if (len(parts) == 2
                and self.use_seconds and self.use_seconds != 'optional'):
            raise Invalid(self.message('secondsRequired', state), value, state)
        if len(parts) == 1:
            raise Invalid(self.message('minutesRequired', state), value, state)
        try:
            hour = int(parts[0])
        except ValueError:
            raise Invalid(
                self.message('badNumber', state,
                    number=parts[0], part='hour'), value, state)
        if explicit_ampm:
            if not 1 <= hour <= 12:
                raise Invalid(
                    self.message('badHour', state,
                        number=hour, range='1-12'), value, state)
            if hour == 12 and offset == 12:
                # 12pm == 12
                pass
            elif hour == 12 and offset == 0:
                # 12am == 0
                hour = 0
            else:
                hour += offset
        else:
            if not 0 <= hour < 24:
                raise Invalid(
                    self.message('badHour', state,
                        number=hour, range='0-23'), value, state)
        try:
            minute = int(parts[1])
        except ValueError:
            raise Invalid(
                self.message('badNumber', state,
                    number=parts[1], part='minute'), value, state)
        if not 0 <= minute < 60:
            raise Invalid(
                self.message('badMinute', state, number=minute),
                value, state)
        if len(parts) == 3:
            try:
                # allow seconds to be float
                if not self.use_float_secs:
                    second = int(parts[2])
                else:
                    second = float(parts[2])
            except ValueError:
                raise Invalid(
                    self.message('badNumber', state,
                        number=parts[2], part='second'), value, state)
            if not 0 <= second < 60:
                raise Invalid(
                    self.message('badSecond', state, number=second),
                    value, state)
        else:
            second = None
        if second is None:
            return hour, minute
        else:
            return hour, minute, second

    

class DteFormValidate():
    '''
    use formencode validator to validate form and convert to python. See http://www.formencode.org/en/latest/index.html
    
    :param validator: formencode validator instance
    '''
    def __init__(self, validator):
        self.validator = validator
    
    def validate(self, form):
        '''
        validate form and convert to python
        
        :param form: dict or multidict to be validated (e.g., request.form)
        :rtype: {'python': <form in python format>, 'results': <results formatted for response to datatables editor>}
            if no errors, results = [], python included
            if errors, results = [{'name': <field name>, 'status': <error message for field>}, ...]
        '''
        py = None
        error_dict = {}
        results = []
        try:
            py = self.validator.to_python(form)
        except Invalid as e:
            error_dict = e.error_dict
        for field in error_dict:
            results.append({'name': field, 'status': error_dict[field].msg})

        return {'python':py, 'results':results}

def apimethod(f):
    '''
    decorator for api methods

    :param f: function() containing core of method to execute
    '''
    # see http://python-3-patterns-idioms-test.readthedocs.io/en/latest/PythonDecorators.html
    def wrapped_f(self, *args, **kwargs):
        try:
            # verify user can write the data, otherwise abort
            if not self.permission():
                self.rollback()
                cause = 'operation not permitted for user'
                return jsonify(error=cause)

            # execute core of method
            return f(self, *args, **kwargs)
        
        except Exception as e:
            output_result = {'status': 'fail'}
            # abort if errors seen
            if hasattr(self, '_fielderrors') and self._fielderrors:
                cause = 'please check indicated fields'
                output_result.update({'error': cause, 'fieldErrors': self._fielderrors})
            else:
                exc = ''.join(format_exception_only(type(e), e))
                output_result['error'] = 'exception occurred:\n{}'.format(exc)
                current_app.logger.error(format_exc())

            # roll back database updates and close transaction
            self.rollback()
            return jsonify(output_result)
    return wrapped_f

