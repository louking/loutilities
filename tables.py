###########################################################################################
# datatables_utils
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
from flask import make_response, request, jsonify, url_for
from flask.views import MethodView

# homegrown

class ParameterError(Exception): pass;

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
        if formkey == 'action': continue
        datapart,idpart,fieldpart = formkey.split('[')
        if datapart != 'data': raise ParameterError, "invalid input in request: {}".format(formkey)

        idvalue = int(idpart[0:-1])
        fieldname = fieldpart[0:-1]

        data[idvalue][fieldname] = form[formkey]

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
    '''

    #----------------------------------------------------------------------
    def __init__(self, dbmapping, formmapping):
    #----------------------------------------------------------------------
        self.dbmapping = dbmapping
        self.formmapping = formmapping

    #----------------------------------------------------------------------
    def get_response_data(self, dbentry):
    #----------------------------------------------------------------------
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
                data[key] = getattr(dbentry, dbattr)

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
    '''

    #----------------------------------------------------------------------
    # these methods must be replaced
    #----------------------------------------------------------------------

    def open(self):
        '''
        must be overridden

        open source of "csv" data
        '''
        pass

    def nexttablerow(self):
        '''
        must be overridden

        return next record, similar to csv.DictReader - raises StopIteration
        :rtype: dict with row data for table
        '''
        pass

    def close(self):
        '''
        must be overridden

        close source of "csv" data
        '''
        pass

    def permission(self):
        '''
        must be overridden

        check for readpermission on data
        :rtype: boolean
        '''
        return False

    def renderpage(self, tabledata):
        '''
        must be overridden

        renders flask template with appropriate parameters
        :param tabledata: list of data rows for rendering
        :rtype: flask.render_template()
        '''
        pass

    #----------------------------------------------------------------------
    # these methods may be replaced
    #----------------------------------------------------------------------

    def rollback(self):
        '''
        may be overridden

        any processing which must be done on page abort or exception
        '''
        pass

    def beforeget(self):
        '''
        may be overridden

        any processing which needs to be done at the beginning of the get
        '''
        pass

    def abort(self):
        '''
        may be overridden

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
                    # dtoptions = {},
                    # readpermission = lambda: False, 
                    # columns = None, 
                    # buttons = ['csv'],
                    )
        args.update(kwargs)        
        for key in args:
            setattr(self, key, args[key])

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # create supported endpoints
        my_view = self.as_view(self.endpoint, **self.kwargs)
        self.app.add_url_rule('/{}'.format(self.endpoint),view_func=my_view,methods=['GET',])

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

                if debug: print 'checkaction = {}'.format(checkaction)
                # checkaction needs to be list
                if checkaction:
                    actioncheck = checkaction.split(',')

                # if checkaction and action != checkaction:
                if checkaction and action not in actioncheck:
                    self.rollback()
                    cause = 'unknown action "{}"'.format(action)
                    self.app.logger.warning(cause)
                    return dt_editor_response(error=cause)

                # set up parameters to query
                self.beforequery()

                # execute core of method
                f(self,*args, **kwargs)

                # commit database updates and close transaction
                self.commit()
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
                    self.app.logger.error(traceback.format_exc())
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

    :param app: flask app
    :param pagename: name to be displayed at top of html page
    :param endpoint: endpoint parameter used by flask.url_for()
    :param eduploadoption: editor upload option (optional) see https://editor.datatables.net/reference/option/ajax
    :param clientcolumns: list of dicts for input to dataTables and Editor
    :param servercolumns: list of ColumnDT for input to sqlalchemy-datatables.DataTables
    :param idSrc: idSrc for use by Editor
    :param buttons: list of buttons for DataTable, from ['create', 'remove', 'edit', 'csv']
    '''

    #----------------------------------------------------------------------
    # the following methods must be replaced in subclass
    #----------------------------------------------------------------------
    
    #----------------------------------------------------------------------
    def open(self):
    #----------------------------------------------------------------------
        '''
        must be overridden

        open source of "csv" data
        '''
        pass

    #----------------------------------------------------------------------
    def nexttablerow(self):
    #----------------------------------------------------------------------
        '''
        must be overridden

        return next record, similar to csv.DictReader - raises StopIteration
        :rtype: dict with row data for table
        '''
        pass

    #----------------------------------------------------------------------
    def close(self):
    #----------------------------------------------------------------------
        '''
        must be overridden

        close source of "csv" data
        '''
        pass

    #----------------------------------------------------------------------
    def permission(self):
    #----------------------------------------------------------------------
        return False

    #----------------------------------------------------------------------
    def createrow(self, formdata):
    #----------------------------------------------------------------------
        '''
        must be overridden

        creates row in database
        
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        pass

    #----------------------------------------------------------------------
    def updaterow(self, thisid, formdata):
    #----------------------------------------------------------------------
        '''
        must be overridden

        updates row in database
        
        :param thisid: id of row to be updated
        :param formdata: data from create form
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        pass

    #----------------------------------------------------------------------
    def deleterow(self, thisid):
    #----------------------------------------------------------------------
        '''
        must be overridden

        deletes row in database
        
        :param thisid: id of row to be updated
        :rtype: returned row for rendering, e.g., from DataTablesEditor.get_response_data()
        '''
        pass

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
        return flask.render_template('datatables.html', **kwargs)

    #----------------------------------------------------------------------
    # END of overrridden methods
    #----------------------------------------------------------------------


    #----------------------------------------------------------------------
    def __init__(self, **kwargs):
    #----------------------------------------------------------------------
        # the args dict has all the defined parameters to 
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        self.kwargs = kwargs
        args = dict(app = None,
                    pagename = None, 
                    endpoint = None, 
                    eduploadoption = None,
                    clientcolumns = None, 
                    servercolumns = None, 
                    idSrc = 'DT_RowId', 
                    buttons = ['create', 'edit', 'remove', 'csv'])
        args.update(kwargs)        
        for key in args:
            setattr(self, key, args[key])

        # set up mapping between database and editor form
        # self.dte = DataTablesEditor(self.dbmapping, self.formmapping)

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # create supported endpoints
        my_view = self.as_view(self.endpoint, **self.kwargs)
        self.app.add_url_rule('/{}'.format(self.endpoint),view_func=my_view,methods=['GET',])
        self.app.add_url_rule('/{}/rest'.format(self.endpoint),view_func=my_view,methods=['GET', 'POST'])
        self.app.add_url_rule('/{}/rest/<int:thisid>'.format(self.endpoint),view_func=my_view,methods=['PUT', 'DELETE'])

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

            # DataTables options string, data: and buttons: are passed separately
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
                dtcolumn = column.copy()
                # pop to remove from dtcolumn
                dtonly = dtcolumn.pop('dt', {})
                dtcolumn.pop('ed',{})
                dtcolumn.update(dtonly)
                dt_options['columns'].append(dtcolumn)

            # build table data
            if self.servercolumns == None:
                dt_options['serverSide'] = False
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
                dt_options['serverSide'] = True
                tabledata = '{}/rest'.format(url_for(self.endpoint))

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
            fieldkeys = ['className', 'data', 'def', 'entityDecode', 'fieldInfo', 'id', 'label', 'labelInfo', 'name', 'type', 'options', 'opts', 'ed']
            for column in self.clientcolumns:
                # pick keys which matter
                edcolumn = { key: column[key] for key in fieldkeys if key in column}
                # edcolumn = column.copy()
                # pop to remove from edcolumn
                edonly = edcolumn.pop('ed', {})
                edcolumn.update(edonly)
                ed_options['fields'].append(edcolumn)

            # add upload, if desired
            if self.eduploadoption:
                ed_options['ajax']['upload'] = self.eduploadoption

            # commit database updates and close transaction
            self.commit()

            # render page
            return self.render_template( pagename = self.pagename,
                                         tabledata = tabledata, 
                                         tablebuttons = self.buttons,
                                         options = {'dtopts': dt_options, 'editoropts': ed_options, 'updateopts': update_options},
                                         writeallowed = self.permission())
        
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
            # TODO: verify this works with actual database, see rrwebapp/crudapi.py
            self.open()
            tabledata = []
            try:
                while(True):
                    thisentry = self.nexttablerow()
                    tabledata.append(thisentry)
            except StopIteration:
                pass
            self.close()
            output_result = tabledata

            # back to client
            return jsonify(output_result)

        except:
            # roll back database updates and close transaction
            self.rollback()
            raise

    #----------------------------------------------------------------------
    def get(self):
    #----------------------------------------------------------------------
        if request.path[-4:] != 'rest':
            return self._renderpage()
        else:
            return self._retrieverows()

    #----------------------------------------------------------------------
    @_editormethod(checkaction='create,upload', formrequest=True)
    def post(self):
    #----------------------------------------------------------------------
        # retrieve data from request
        thisdata = self._data[0]
        
        action = get_request_action(request.form)
        if action == 'create':
            thisrow = self.createrow(thisdata)
        else:
            stophere
            thisrow = self.upload(thisdata)

        self._responsedata = [thisrow]


    #----------------------------------------------------------------------
    @_editormethod(checkaction='edit', formrequest=True)
    def put(self, thisid):
    #----------------------------------------------------------------------
        # retrieve data from request
        self._responsedata = []
        thisdata = self._data[thisid]
        
        thisrow = self.editrow(thisid, thisdata)

        self._responsedata = [thisrow]


    #----------------------------------------------------------------------
    @_editormethod(checkaction='remove', formrequest=False)
    def delete(self, thisid):
    #----------------------------------------------------------------------
        self.deleterow(thisid)

        # prepare response
        self._responsedata = []

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


