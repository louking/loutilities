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
from copy import deepcopy
from json import dumps, loads
from urllib import urlencode

# pypi
import flask
from flask import request, jsonify, url_for, current_app
from flask.views import MethodView

# homegrown
from nesteddict import NestedDict

class ParameterError(Exception): pass;
class NotImplementedError(Exception): pass;

debug = False

#----------------------------------------------------------------------
def dt_editor_response(**respargs):
#----------------------------------------------------------------------
    '''
    build response for datatables editor
    
    :param respargs: arguments for response
    :rtype: json response
    '''

    return flask.jsonify(**respargs)


#----------------------------------------------------------------------
def get_request_action(form):
#----------------------------------------------------------------------
    # TODO: modify get_request_action and get_request_data to allow either request object or form object, 
    # and remove if/else for formrequest, e.g., action = get_request_action(request)
    # (allowing form object deprecated for legacy code)
    '''
    return dict list with data from request.form

    :param form: MultiDict from `request.form`
    :rtype: action - 'create', 'edit', or 'remove'
    '''
    return form['action']

#----------------------------------------------------------------------
def get_request_data(form):
#----------------------------------------------------------------------
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
    for formkey in form.keys():
        # if formkey == 'action': continue
        if formkey[0:5] != 'data[': continue

        formlineitems = formkey.split('[')
        datapart,idpart = formlineitems[0:2]
        # if datapart != 'data': raise ParameterError, "invalid input in request: {}".format(formkey)

        idvalue = int(idpart[0:-1])

        # the rest of it is the field structure, may have been [a], [a][b], etc before splitting at '['
        fieldparts = [part[0:-1] for part in formlineitems[2:]]

        # use NestedDict to handle arbitrary data field tree structure
        fieldkey = '.'.join(fieldparts)
        fieldlevels = NestedDict()
        fieldlevels[fieldkey] = form[formkey]
        data[idvalue].update(fieldlevels.to_dict())

        from pprint import PrettyPrinter
        pp = PrettyPrinter()
        current_app.logger.debug('get_request_data(): formkey={} data={}'.format(formkey, pp.pformat(data)))

    # return decoded result
    return data


###########################################################################################
class DataTablesEditor():
###########################################################################################
    '''
    handle CRUD request from dataTables Editor

    dbmapping is dict like {'dbattr_n':'formfield_n', 'dbattr_m':f(form), ...}
    formmapping is dict like {'formfield_n':'dbattr_n', 'formfield_m':f(dbrow), ...}
    if order of operation is importand use OrderedDict

    :param dbmapping: mapping dict with key for each db field, value is key in form or function(dbentry)
    :param formmapping: mapping dict with key for each form row, value is key in db row or function(form)
    :param null2emptystring: if True translate '' from form to None for db and visa versa
    '''

    #----------------------------------------------------------------------
    def __init__(self, dbmapping, formmapping, null2emptystring=False):
    #----------------------------------------------------------------------
        self.dbmapping = dbmapping
        self.formmapping = formmapping
        self.null2emptystring = null2emptystring

    #----------------------------------------------------------------------
    def get_response_data(self, dbentry, nesteddata=False):
    #----------------------------------------------------------------------
        '''
        set form values based on database model object

        :param dbentry: database entry (model object)
        :param nesteddata: set to True if data coming from server is multi leveled e.g., see see https://editor.datatables.net/examples/simple/join.html)
        '''

        # ** use of NestedDict() may be useful for certain situations (e.g., see https://editor.datatables.net/examples/simple/join.html)
        # ** however this has not been fully tested so is disabled by default  
        if nesteddata:
            # data['a.b.c'].to_dict() = data['a']['b']['c']
            data = NestedDict()
        else:
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
                data[key] = getattr(dbentry, dbattr)
                if self.null2emptystring and data[key]==None:
                    data[key] = ''

        if nesteddata:
            return data.to_dict()
        else:
            return data

    #----------------------------------------------------------------------
    def set_dbrow(self, inrow, dbrow):
    #----------------------------------------------------------------------
        '''
        update database entry from form entry

        :param inrow: input row
        :param dbrow: database entry (model object)
        '''

        for dbattr in self.dbmapping:
            # call the function to fill dbrow.<dbattr>
            if hasattr(self.dbmapping[dbattr], '__call__'):
                callback = self.dbmapping[dbattr]
                setattr(dbrow, dbattr, callback(inrow))

            # simple map from inrow field
            else:
                key = self.dbmapping[dbattr]
                if key in inrow:
                    setattr(dbrow, dbattr, inrow[key])
                    if self.null2emptystring and getattr(dbrow, dbattr) == '':
                        setattr(dbrow, dbattr, None)
                else:
                    # ignore -- leave dbrow unchanged for this dbattr
                    pass


#######################################################################
class TablesCsv(MethodView):
#######################################################################
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

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
    #----------------------------------------------------------------------
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
        for key in args:
            setattr(self, key, args[key])

        # rule defaults to '/' + endpoint if not supplied
        self.rule = self.rule or ('/' + self.endpoint)

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        # create supported endpoints
        my_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.rule),view_func=my_view,methods=['GET',])

    #----------------------------------------------------------------------
    def get(self):
    #----------------------------------------------------------------------
        try:
            # do any processing, e.g., check credentials
            redirect = self.beforeget()
            if redirect:
                return redirect

            # verify user can read the data, otherwise abort
            if not self.permission():
                self.rollback()
                self.abort()
            
            # # DataTables options string, data: and buttons: are passed separately
            # dt_options = {
            #     'dom': '<"H"lBpfr>t<"F"i>',
            #     'columns': [],
            #     'ordering': True,
            #     'serverSide': False,
            # }
            # dt_options.update(self.dtoptions)

            # # set up columns
            # if hasattr(self.columns, '__call__'):
            #     columns = self.columns()
            # else:
            #     columns = self.columns
            # for column in columns:
            #     dt_options['columns'].append(column)

            # # set up buttons
            # if hasattr(self.buttons, '__call__'):
            #     buttons = self.buttons()
            # else:
            #     buttons = self.buttons

            # set up column transformation from header items to data items
            # mapping = { c['data']:c['label'] for c in columns }
            # headers2data = Transform(mapping, sourceattr=False, targetattr=False)

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


#######################################################################
#----------------------------------------------------------------------
def _editormethod(checkaction='', formrequest=True):
#----------------------------------------------------------------------
    '''
    decorator for CrudApi methods used by Editor

    :param methodcore: function() containing core of method to execute
    :param checkaction: Editor name of action which is used by the decorated method, one of 'create', 'edit', 'remove' or '' if no check required (can be list)
    :param formrequest: True if request action, data is in form (False for 'remove' action)
    '''
    # see http://python-3-patterns-idioms-test.readthedocs.io/en/latest/PythonDecorators.html
    if debug: print '_editormethod(checkaction={}, formrequest={})'.format(checkaction, formrequest)
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
                
                # perform any processing required before method is executed
                self.editor_method_prehook(request.form)

                # get action
                # TODO: modify get_request_action and get_request_data to allow either request object or form object, 
                # and remove if/else for formrequest, e.g., action = get_request_action(request)
                # (allowing form object deprecated for legacy code)
                if formrequest:
                    action = get_request_action(request.form)
                    self._data = get_request_data(request.form)
                else:
                    action = request.args['action']

                if debug: print 'checkaction = {}'.format(checkaction)
                # checkaction needs to be list
                if checkaction:
                    actioncheck = checkaction.split(',')

                # if checkaction and action != checkaction:
                if checkaction and action not in actioncheck:
                    self.rollback()
                    cause = 'unknown action "{}"'.format(action)
                    current_app.logger.warning(cause)
                    return dt_editor_response(error=cause)

                # set up parameters to query
                self.beforequery()

                # execute core of method
                f(self,*args, **kwargs)

                # perform any processing required after method is executed
                self.editor_method_posthook(request.form)

                # commit database updates and close transaction
                self.commit()

                # response to client                
                return dt_editor_response(data=self._responsedata)
            
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


#######################################################################
class CrudApi(MethodView):
#######################################################################
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
              '_update' {
                'endpoint' : <url endpoint to retrieve options from>,
                'on' : <event>
                'wrapper' : <wrapper for query response>
              }
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

        additionally the update option can be used to _update the options for any type = 'select', 'selectize'

        * _update - dict with following keys
            * endpoint - url endpoint to retrieve new options 
            * on - event which triggers update. supported events are
                * 'open' - triggered when form opens (actually when field is focused)
                * 'change' - triggered when field changes - use wrapper to indicate what field(s) are updated
            * wrapper - dict which is wrapped around query response. value '_response_' indicates where query response should be placed
    
    **servercolumns** - if present table will be displayed through ajax get calls

    **scriptfilter** - can be used to filter list of scripts into full pathname, version argument, etc

    :param app: flask app or blueprint
    :param pagename: name to be displayed at top of html page
    :param endpoint: endpoint parameter used by flask.url_for()
    :param rule: rule parameter used by flask.add_url_rule() [defaults to '/' + endpoint]
    :param eduploadoption: editor upload option (optional) see https://editor.datatables.net/reference/option/ajax
    :param clientcolumns: list of dicts for input to dataTables and Editor
    :param filtercoloptions: list of clientcolumns options which are to be filtered out
    :param servercolumns: list of ColumnDT for input to sqlalchemy-datatables.DataTables
    :param idSrc: idSrc for use by Editor
    :param buttons: list of buttons for DataTable, from ['create', 'remove', 'edit', 'csv']
    :param pretablehtml: string any html which needs to go before the table

    :param scriptfilter: function to filter pagejsfiles and pagecssfiles lists into full path / version lists
    :param dtoptions: dict of datatables options to apply at end of options calculation
    :param edoptions: dict of datatables editor options to apply at end of options calculation
    :param yadcfoptions: dict of yadcf options to apply at end of options calculation
    :param pagejsfiles: list of javascript file paths to be included
    :param pagecssfiles: list of css file paths to be included
    :param templateargs: dict of arguments to pass to template - if callable arg function is called before being passed to template (no parameters)
    :param validate: editor validation function (action, formdata), result is set to self._fielderrors
    '''

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
    #----------------------------------------------------------------------
        # the args dict has all the defined parameters to 
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        self.kwargs = kwargs
        args = dict(app = None,
                    template = 'datatables.html',
                    pagename = None, 
                    endpoint = None, 
                    rule = None, 
                    eduploadoption = None,
                    clientcolumns = None, 
                    filtercoloptions = [],
                    servercolumns = None, 
                    files = None,
                    idSrc = 'DT_RowId', 
                    buttons = ['create', 'edit', 'remove', 'csv'],
                    pretablehtml = '',
                    scriptfilter = lambda filelist: filelist,
                    dtoptions = {},
                    edoptions = {},
                    yadcfoptions = {},
                    pagejsfiles = [],
                    pagecssfiles = [],
                    templateargs = {},
                    validate = lambda action,formdata: []
                    )
        args.update(kwargs)
        for key in args:
            setattr(self, key, args[key])

        # rule defaults to '/' + endpoint if not supplied
        self.rule = self.rule or ('/' + self.endpoint)

        # set up mapping between database and editor form
        # self.dte = DataTablesEditor(self.dbmapping, self.formmapping)

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        # create supported endpoints
        self.my_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.rule),view_func=self.my_view,methods=['GET',])
        self.app.add_url_rule('{}/rest'.format(self.rule),view_func=self.my_view,methods=['GET', 'POST'])
        self.app.add_url_rule('{}/rest/<int:thisid>'.format(self.rule),view_func=self.my_view,methods=['PUT', 'DELETE'])

        if self.files:
            self.files.register()
            if debug: print 'self.files.register()'

    #----------------------------------------------------------------------
    def _renderpage(self):
    #----------------------------------------------------------------------
        try:
            redirect = self.init()
            if redirect:
                return redirect
            
            # verify user can write the data, otherwise abort
            if not self.permission():
                self.rollback()
                self.abort()
            
            # set up parameters to query, based on whether results are limited to club
            self.beforequery()

            # peel off any _update options
            update_options = []
            for column in self.clientcolumns:
                if '_update' in column:
                    update = column['_update']  # convenience alias
                    update['url'] = url_for(update['endpoint']) + '?' + urlencode({'_wrapper':dumps(update['wrapper'])})
                    update['name'] = column['name']
                    update_options.append(update)

            # get datatable, editor and yadcf options
            dt_options = self.getdtoptions()
            ed_options = self.getedoptions()
            yadcf_options = self.getyadcfoptions()

            # build table data
            if self.servercolumns == None:
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
                tabledata = '{}/rest'.format(url_for(self.endpoint))

            # get files if indicated
            if self.files:
                tablefiles = self.files.list()
                if debug: print tablefiles
            else:
                tablefiles = None

            # commit database updates and close transaction
            self.commit()

            # render page
            return self.render_template( pagename = self.pagename,
                                         pagejsfiles = self.scriptfilter(self.pagejsfiles),
                                         pagecssfiles = self.scriptfilter(self.pagecssfiles),
                                         tabledata = tabledata, 
                                         tablefiles = tablefiles,
                                         tablebuttons = self.buttons,
                                         pretablehtml = self.pretablehtml,
                                         options = {'dtopts': dt_options, 
                                                    'editoropts': ed_options, 
                                                    'yadcfopts' : yadcf_options,
                                                    'updateopts': update_options},
                                         writeallowed = self.permission(),
                                         )
        
        except:
            # roll back database updates and close transaction
            self.rollback()
            raise

    #----------------------------------------------------------------------
    def _retrieverows(self):
    #----------------------------------------------------------------------
        try:
            redirect = self.init()
            if redirect:
                return redirect
            
            # verify user can write the data, otherwise abort
            if not self.permission():
                self.rollback()
                self.abort()
                
            # set up parameters to query
            self.beforequery()

            # columns to retrieve from database
            columns = self.servercolumns

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
                return jsonify(self.output_result)
            else:
                output_result = tabledata
                return jsonify(output_result)

        except:
            # roll back database updates and close transaction
            self.rollback()
            raise

    #----------------------------------------------------------------------
    def getdtoptions(self):
    #----------------------------------------------------------------------

        # DataTables options string, data: and buttons: are passed separately
        # self.dtoptions can update what we come up with
        dt_options = {
            'dom': '<"H"lBpfr>t<"F"i>',
            'columns': [
                {
                    'data': None,
                    'defaultContent': '',
                    'className': 'select-checkbox',
                    'orderable': False
                },
            ],
            'select': True,
            'ordering': True,
            'order': [1,'asc']
        }
        for column in self.clientcolumns:
            # skip rows that are editor only
            if 'edonly' in column: continue

            # if callable, call when making a copy
            # this allows views to refresh, e.g., 'options' for select-like columns
            # remove any column options indicated when this class called (filtercoloptions)
            dtcolumn = { key: column[key] if not callable(column[key]) else column[key]()
                        for key in column if key not in self.filtercoloptions + ['dtonly']}
            # pop to remove from dtcolumn
            dtspecific = dtcolumn.pop('dt', {})
            dtcolumn.pop('ed',{})
            dtcolumn.update(dtspecific)
            dt_options['columns'].append(dtcolumn)

        if self.servercolumns == None:
            dt_options['serverSide'] = False
        else:
            dt_options['serverSide'] = True

        # maybe user had their own ideas on what options are needed for table
        dt_options.update(self.dtoptions)

        return dt_options

    #----------------------------------------------------------------------
    def getedoptions(self):
    #----------------------------------------------------------------------
        ed_options = {
            'idSrc': self.idSrc,
            'ajax': {
                'create': {
                    'type': 'POST',
                    'url':  '{}/rest'.format(url_for(self.endpoint)),
                },
                'edit': {
                    'type': 'PUT',
                    'url':  '{}/rest/{}'.format(url_for(self.endpoint),'_id_'),
                },
                'remove': {
                    'type': 'DELETE',
                    'url':  '{}/rest/{}'.format(url_for(self.endpoint),'_id_'),
                },
            },
            
            'fields': [
            ],
        }
        # TODO: these are editor field options as of Editor 1.5.6 -- do we really need to get rid of non-Editor options?
        fieldkeys = ['className', 'data', 'def', 'entityDecode', 'fieldInfo', 'id', 'label', 'labelInfo', 'name', 'type', 'options', 'opts', 'ed', 'separator', 'dateFormat']
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
        # current_app.logger.debug('getedoptions(): self.edoptions={}'.format(self.edoptions))
        ed_options.update(self.edoptions)

        return ed_options

    #----------------------------------------------------------------------
    def getyadcfoptions(self):
    #----------------------------------------------------------------------
        return self.yadcfoptions

    #----------------------------------------------------------------------
    def get(self):
    #----------------------------------------------------------------------
        print 'request.path = {}'.format(request.path)
        if request.path[-5:] != '/rest':
            return self._renderpage()
        else:
            return self._retrieverows()

    #----------------------------------------------------------------------
    @_editormethod(checkaction='create', formrequest=True)
    def post(self):
    #----------------------------------------------------------------------
        # retrieve data from request
        thisdata = self._data[0]
        
        self._fielderrors = self.validate('create', thisdata)
        if self._fielderrors: raise ParameterError

        action = get_request_action(request.form)
        if action == 'create':
            thisrow = self.createrow(thisdata)
        else:
            thisrow = self.upload(thisdata)

        self._responsedata = [thisrow]


    #----------------------------------------------------------------------
    @_editormethod(checkaction='edit', formrequest=True)
    def put(self, thisid):
    #----------------------------------------------------------------------
        # retrieve data from request
        self._responsedata = []
        thisdata = self._data[thisid]
        
        self._fielderrors = self.validate('edit', thisdata)
        if self._fielderrors: raise ParameterError
        
        thisrow = self.updaterow(thisid, thisdata)

        self._responsedata = [thisrow]


    #----------------------------------------------------------------------
    @_editormethod(checkaction='remove', formrequest=False)
    def delete(self, thisid):
    #----------------------------------------------------------------------
        self.deleterow(thisid)

        # prepare response
        self._responsedata = []


    #----------------------------------------------------------------------
    # the following methods must be replaced in subclass
    #----------------------------------------------------------------------
    
    #----------------------------------------------------------------------
    def open(self):
    #----------------------------------------------------------------------
        '''
        open source of "csv" data
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    def nexttablerow(self):
    #----------------------------------------------------------------------
        '''
        return next record, similar to csv.DictReader - raises StopIteration
        :rtype: dict with row data for table
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    def close(self):
    #----------------------------------------------------------------------
        '''
        close source of "csv" data
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    def permission(self):
    #----------------------------------------------------------------------
        '''
        check for readpermission on data
        :rtype: boolean
        '''
        raise NotImplementedError
        return False

    #----------------------------------------------------------------------
    def createrow(self, formdata):
    #----------------------------------------------------------------------
        '''
        creates row in database
        
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    def updaterow(self, thisid, formdata):
    #----------------------------------------------------------------------
        '''
        updates row in database
        
        :param thisid: id of row to be updated
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    def deleterow(self, thisid):
    #----------------------------------------------------------------------
        '''
        deletes row in database
        
        :param thisid: id of row to be updated
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        raise NotImplementedError

    #----------------------------------------------------------------------
    # the following methods may be replaced in subclass
    #----------------------------------------------------------------------
    
    #----------------------------------------------------------------------
    def init(self):
    #----------------------------------------------------------------------
        pass

    #----------------------------------------------------------------------
    def beforequery(self):
    #----------------------------------------------------------------------
        pass

    #----------------------------------------------------------------------
    def commit(self):
    #----------------------------------------------------------------------
        pass

    #----------------------------------------------------------------------
    def rollback(self):
    #----------------------------------------------------------------------
        pass

    #----------------------------------------------------------------------
    def abort(self):
    #----------------------------------------------------------------------
        flask.abort(403)

    #----------------------------------------------------------------------
    def render_template(self, **kwargs):
    #----------------------------------------------------------------------
        # NOTE: it is recommended that rather than replacing this method, templateargs and template class 
        # parameters be used instead

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
        theseargs.update(kwargs)

        # current_app.logger.debug('flask.render_template({}, {})'.format(self.template, theseargs))
        return flask.render_template(self.template, **theseargs)

    #----------------------------------------------------------------------
    def editor_method_prehook(self, form):
    #----------------------------------------------------------------------
        '''
        This method is called within post() [create], put() [edit], delete() [edit] after permissions are checked

        Replace this if any preprocessing is required based on the form. The form itself cannot be changed

        NOTE: any updates to form validation should be done in self.validation()

        parameters:
        * form - request.form object (immutable)
        '''
        return

    #----------------------------------------------------------------------
    def editor_method_posthook(self, form):
    #----------------------------------------------------------------------
        '''
        This method is called within post() [create], put() [edit], delete() [edit] db commit() just before database
        commit and response to client

        Use get_request_action(form) to determine which method is in progress
        self._responsedata has data about to be returned to client

        parameters:
        * form - request.form object (immutable)
        '''
        return


#######################################################################
#----------------------------------------------------------------------
def _uploadmethod():
#----------------------------------------------------------------------
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
            
            except Exception,e:
                cause = 'Unexpected Error: {}\n{}'.format(e,traceback.format_exc())
                current_app.logger.error(cause)
                return dt_editor_response(error=cause)

        return wrapped_f
    return wrap

#######################################################################
class CrudFiles(MethodView):
#######################################################################
    '''
    provides files support for CrudApi

    usage:
        filesinst = CrudFiles([arguments]):
        apiinst - CrudApi(files=filesinst, [other arguments])
        apiinst.register()
    '''

    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
    #----------------------------------------------------------------------
        # the args dict has all the defined parameters to 
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        if debug: print 'CrudFiles.__init__() **kwargs={}'.format(kwargs)

        self.kwargs = kwargs
        args = dict(app = None,
                    uploadendpoint = None, 
                    uploadrule = None,  # defaults to '/' + uploadendpoint
                    )
        args.update(kwargs)        
        for key in args:
            setattr(self, key, args[key])

        # uploadrule defaults to '/' + uploadendpoint
        self.uploadrule = self.uploadrule or ('/' + self.uploadendpoint)

        self.credentials = None

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # name for view is last bit of fully named endpoint
        name = self.uploadendpoint.split('.')[-1]

        # # create supported endpoints
        # list_view = self.as_view(self.listendpoint, **self.kwargs)
        # self.app.add_url_rule('/{}'.format(self.listendpoint),view_func=list_view,methods=['GET',])
        if debug: print 'CrudFiles.register()'

        upload_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.uploadrule),view_func=upload_view,methods=['POST',])


    #----------------------------------------------------------------------
    @_uploadmethod()
    def post(self):
    #----------------------------------------------------------------------
        self._responsedata = self.upload()

    #----------------------------------------------------------------------
    # the following methods must be replaced in subclass
    #----------------------------------------------------------------------
    
    #----------------------------------------------------------------------
    def list(self):
    #----------------------------------------------------------------------
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

    #----------------------------------------------------------------------
    def upload(self):
    #----------------------------------------------------------------------
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


#----------------------------------------------------------------------
def deepupdate(obj, val, newval):
#----------------------------------------------------------------------
    '''
    recursively searches obj object and replaces any val values with newval
    does not update opj
    returns resultant object
    
    :param obj: object which requires updating
    :param val: val to look for
    :param newval: replacement for val
    '''
    thisobj = deepcopy(obj)

    if type(thisobj) == dict:
        for k in thisobj:
            thisobj[k] = deepupdate(thisobj[k], val, newval)

    elif type(thisobj) == list:
        for k in range(len(thisobj)):
            thisobj[k] = deepupdate(thisobj[k], val, newval)

    else:
        if thisobj == val:
            thisobj = newval

    return thisobj



