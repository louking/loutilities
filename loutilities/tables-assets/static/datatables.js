/**
 * generic datatables / Editor handling
 */

var editor, _dt_table;
var opttree = {};

function checkeval(obj) {
    // loop thru arrays
    if (_.isArray(obj)) {
        $.each(obj, function(i,val) {
            obj[i] = checkeval(val);
        })
        return obj
    
    // loop thru objects (this can probably be combined with above)
    } else if (_.isObject(obj)) {
        if (obj.hasOwnProperty('eval')) {
            return eval(obj['eval']);
        } else {
            $.each(obj, function(key,val) {
                obj[key] = checkeval(val)
            })
            return obj
        }
    
    // not array or object, so just return the item
    } else {
        return obj
    }
}

// handle any updates of dependent fields.
// opttree is set in datatables() if (options.updateopts !== undefined).
// opttree has a key for each field with dependency, and for each possible value
// of that field has object like that described in https://editor.datatables.net/reference/api/dependent()
// under Return options / JSON
function dependent_option( val, data ) {
    options = {}
    for (var field in opttree) {
        if (opttree.hasOwnProperty(field)) {
            $.extend(true, options, opttree[field][data.values[field]]);
        }
    }

    return options;
}


// y scroll management adapted from https://datatables.net/forums/discussion/comment/104797/#Comment_104797

function firstDataTableScrollAdjust() {
    // first render of data table
    jsDataTableScrollAdjust();
    
    window.onresize = function() {
        // adjust the hight of the data table on a browser resize event
        jsDataTableScrollAdjust();
    };
}

function jsDataTableScrollAdjust() {
    return;
    // if(_dt_table) {
    //     var height = jsGetDataTableHeightPx() + "px";
    //     $('.dataTables_scrollBody:has(#datatable)').css('max-height', height);
    //     $('.DTFC_LeftBodyLiner').css('max-height', height);
    //     _dt_table.draw();
    // }
}

/**
 * Gets the data table height based upon the browser page
 * height and the data table vertical position.
 * 
 * @return  Data table height, in pixels.
 */
function jsGetDataTableHeightPx() {
     // set default return height
    var retHeightPx = 350;

    // no nada if there is no dataTable (container) element
    var dataTable = document.getElementById("datatable");
    if(!dataTable) {
        return retHeightPx;
    }

    // do nada if we can't determine the browser height
    var pageHeight = $(window).height();
    if(pageHeight < 0) {
        return retHeightPx;
    }

    // determine the data table height based upon the browser page height
    var dataTableHeight = pageHeight - 320; //default height
    var dataTablePos = $("#datatable").offset();
    var dataTableInfoHeight = $('#datatable_info').height();
    var fudge = 15; // for some reason need this to avoid window scroll bar
    if(dataTablePos != null && dataTablePos.top > 0) {
        // the data table height is the page height minus the top of the data table,
        // minus the info at the bottom
        dataTableHeight = pageHeight - dataTablePos.top - dataTableInfoHeight - fudge;

        // clip height to min. value
        retHeightPx = Math.max(100, dataTableHeight);
    }
    return retHeightPx;
}

// hold for 90 seconds max -- maybe this can be reduced in real system
// requires mutex-promise.js
let rtd_mutex = new MutexPromise('datatables-refresh_table_data', {timeout: 90000})

/**
 * refresh table data without full reload of page
 *
 * Note: this is only for client based table data (serverside = False)
 *
 * @param table - table to redraw
 * @param resturl - url to use to retrieve updated data for table
 * @param paging - see https://datatables.net/reference/api/draw() (default 'full-reset')
 */
function refresh_table_data(table, resturl, paging) {
    // manage rows in the table
    let currrows = {};

    // grab lock
    // console.log('acquiring lock');
    return rtd_mutex.promise()
        .then(function(mutex) {
            mutex.lock();
            // (dataTables default) ordering and search will be recalculated and the rows redrawn in their new positions.
            // The paging will be reset back to the first page.
            if (paging === undefined) {
                paging = 'full-reset';
            }

            // save {rowid: row, } for all current data
            // console.log('copying table')
            let rowndxs = table.rows()[0];
            for (let i=0; i<rowndxs.length; i++) {
                let rowndx = rowndxs[i];
                currrows[table.row(rowndx).id()] = table.row(rowndx);
            }

            return $.get(resturl)
        })
        .then(function( respdata ) {
            let rowId = table.settings()[0].rowId;

            for (let i=0; i<respdata.length; i++) {
                let resprow = respdata[i];
                // replace row if it exists
                if (currrows[resprow[rowId]] !== undefined) {
                    table.row('#' + resprow[rowId]).data(resprow);
                    delete currrows[resprow[rowId]];
                // add row if it is new
                } else {
                    table.row.add(resprow);
                }
            }

            // any remaining rows in currrows need to be deleted
            $.each(currrows, function(k, v){
                table.row('#' + k).remove();
            });

            // redraw
            // console.log('drawing table');
            table.draw(paging);
            // console.log('releasing lock');
            rtd_mutex.unlock();
        })
        .catch(function(e){
            // console.log('releasing lock due to exception');
            rtd_mutex.unlock();
            throw e;
        });
}

/**
 * return a grip for rowReorder function
 *
 * @returns {string}
 */
function render_grip(data, type, row) {
    // see https://datatables.net/forums/discussion/comment/187037/#Comment_187037
    if ( type === 'display' ) {
        return '<i class="fa fa-grip-horizontal" aria-hidden="true"></i>';
    }
    return data;
};

/**
 * return function which renders display data as select tags
 * @param {} separator 
 */
function render_select_as_tags () {
    return function(data, type, row) {
        if ( type === 'display' ) {
            var items = data;
            var displayitems = [];
            for (var i=0; i<items.length; i++) {
                var item = items[i];
                displayitems.push(`<span class=tag-display>${item}</span>`)
            }
            return displayitems.join('');
        }
        return data;
    }
};

/**
 * get the button options, correctly annotated with indicated editor
 *
 * @param buttons - list of editor actions 'create', 'edit', 'editRefresh', 'editChildRowRefresh', 'remove'
 *          or other button configuration.
 *          See https://datatables.net/reference/option/buttons and https://datatables.net/reference/option/buttons.buttons
 * @param editor - editor to annotate action with
 * @returns {[{extend:button, editor: editor}, {buttons.buttons fields}, ...]}
 */
function get_button_options(buttons, editor) {
    var button_options = [];
    for (i=0; i<buttons.length; i++) {
        button = buttons[i];
        if ($.inArray(button, ['create', 'edit', 'editRefresh', 'editChildRowRefresh', 'remove']) >= 0) {
            button_options.push({extend:button, editor:editor});
        } else {
            // convert button actions to javascript, // kludge for conversion from python
            if (button.hasOwnProperty('action')) {
                button.action = eval(button.action)
            }

            button_options.push(button);
        }
    }

    return button_options;
}

/**
 * render a fontawesome icon
 *
 * column declaration for CrudApi must be similar to
 *
 *      {'data': '',  # needs to be '' else get exception converting options from meetings render_template
 *       # TypeError: '<' not supported between instances of 'str' and 'NoneType'
 *       'name': 'edit-control',
 *       'className': 'edit-control shrink-to-fit',
 *       'orderable': False,
 *       'defaultContent': '',
 *       'label': '',
 *       'type': 'hidden',  # only affects editor modal
 *       # this heading title or some other title like "Edit"
 *       'title': '<i class="fas fa-edit" aria-hidden="true"></i>',
 *       'render': {'eval': 'render_icon("fas fa-edit", ["displayicon"])'},
 *       },
 *
 * @param {string} iconclass - classes of icon, e.g., "fas fa-edit"
 * @param {string} [hideattr] - attr of row which, if true means the icon should be hidden
 * @returns {function(data, type, row): string} - string is text to be rendered
 */
function render_icon(iconclass, hideattr) {
    var fn = function(data, type, row) {
        if (!row[hideattr]) {
            return '<i class="' + iconclass + '" aria-hidden="true"></i>';
        } else {
            return ''
        }
    }
    return fn;
}

/**
 * use in yadcf options as custom_func parameter, along with filter_type = 'date_custom_func'
 * @param fromdateattr
 * @param todateattr
 * @returns {function(filterVal, columnVal, rowValues, stateVal): boolean}
 */
function yadcf_between_dates(fromdateattr, todateattr) {
    function yadcf_between_dates_fn(filterVal, columnVal, rowValues, stateVal) {
        // console.log('filterVal='+filterVal);
        // console.log('columnVal='+columnVal);
        // console.log('rowValues='+rowValues);
        // console.log('stateVal='+stateVal);

        // no filter means return all records
        if (filterVal === '') {
          return true;
        }

        // blank fromdate is from the beginning of time, blank todate is to the end of time
        if (    (stateVal[fromdateattr] === '' || filterVal >= stateVal[fromdateattr])
             && (stateVal[todateattr] === ''   || filterVal <= stateVal[todateattr])) {
            return true;

        } else {
          return false;
        }
    }
    return yadcf_between_dates_fn;
}

/**
 * create click event handler for indicated datatable, cell
 * when cell clicked, row is selected and button_name'd button is triggered (pressed)
 *
 * @param dt - datatable
 * @param cell_select - e.g., 'td.colclass'
 * @param button_name - name attached to datatable button to "press"
 */
function onclick_trigger(dt, cell_select, button_name) {
    dt.on('click', cell_select, function (e) {
        var tr = $(this).closest('tr');
        var row = dt.row(tr);
        row.select();
        dt.buttons(button_name + ':name').trigger();
        e.stopPropagation();
    });
}

/**
 * configure dataTables for table with id=datatable
 *
 * @param data - list of objects for rendering or url for ajax retrieval of similar object
 * @param buttons - is a JSON parsable string, as it references editor which hasn't been instantiated yet
 * @param options - object with the following keys
 *     dtopts:       options to be passed to DataTables instance,
 *                   except for data: and buttons: options, passed in data, buttons
 *     editoropts:   options to be passed to Editor instance,
 *                   if not present, Editor will not be configured
 *     updateopts:   options to configure Editor select fields with
 *                   see tables.py for more details
 *     yadcfopts:    (optional) yadcf options to be passed to yadcf
 *                   if not present, yadcf will not be configured
 *     childrow:     (optional) options to configure ChildRow display (see datatables-childrow.js)
 *                   if not present, childrow will not be configured
 * @param files - (optional) passed to Editor instance
 */
function datatables(data, buttons, options, files) {

    // convert render to javascript -- backwards compatibility
    if (options.dtopts.hasOwnProperty('columns')) {
        for (i=0; i<options.dtopts.columns.length; i++) {
            if (options.dtopts.columns[i].hasOwnProperty('render')) {
                options.dtopts.columns[i].render = eval(options.dtopts.columns[i].render)
            }
        }        
    }
    // convert display and render to javascript - backwards compatibility
    if (options.editoropts !== undefined) {
        if (options.editoropts.hasOwnProperty('fields')) {
            for (i=0; i<options.editoropts.fields.length; i++) {
                if (options.editoropts.fields[i].hasOwnProperty('render')) {
                    options.editoropts.fields[i].render = eval(options.editoropts.fields[i].render)
                }
                if (options.editoropts.fields[i].hasOwnProperty('display')) {
                    options.editoropts.fields[i].display = eval(options.editoropts.fields[i].display)
                }
            }        
        }
    }

    // drill down any options with {eval : string} key, and evaluate the string
    options = checkeval(options);

    // configure editor if requested
    if (options.editoropts !== undefined) {
        // disable autocomplete / autofill by default
        $.extend( true, $.fn.dataTable.Editor.Field.defaults, {
          attr: {
            autocomplete: 'off'
          }
        } );

        // configure childrow options for editor if so configured
        if ( ! $.isEmptyObject( options.childrow ) ) {
            if (options.childrow.showeditor) {
                $.extend(options.editoropts,{display:onPageDisplay('#childrow-editform-top')})
            }
        }

        // create editor instance
        $.extend(options.editoropts,{table:'#datatable'})
        editor = new $.fn.dataTable.Editor ( options.editoropts );

        // adapted from https://editor.datatables.net/examples/api/confirmClose
        // requires Editor 1.9.5 (or patch to editor.jqueryui.js (editor.jqueryui.patch-discussion-63653.js)
        var openVals;
        editor
            .on( 'open', function () {
                // Store the values of the fields on open
                openVals = JSON.stringify( editor.get() );

                editor.on( 'preClose', function ( e ) {
                    // On close, check if the values have changed and ask for closing confirmation if they have
                    if ( openVals !== JSON.stringify( editor.get() ) ) {
                        return confirm( 'You have unsaved changes. Are you sure you want to exit?' );
                    }
                } );
            } )
            .on( 'postCreate postEdit close', function () {
                editor.off( 'preClose' );
            } );

        // if createfieldvals requested, add a handler which initializes fields when create form displayed
        if (options.createfieldvals !== undefined) {
            // save for initCreate function
            editor.createfieldvals = options.createfieldvals;
            editor.on('initCreate.dt', function(e) {
                var that = this;
                $.each(this.createfieldvals, function(field, val) {
                    that.field(field).val(val);
                });
            });
        }

        // set up to update select options
        if (options.updateopts !== undefined) {
            for (i=0; i<options.updateopts.length; i++) {
                updateopt = options.updateopts[i]
                // handle option trees
                if (updateopt.options != undefined) {
                    opttree[updateopt.name] = updateopt.options;
                    editor.dependent( updateopt.name, dependent_option );
                    
                // handle ajax update options
                } else {
                    if (updateopt.on == 'open') {
                        editor.dependent( updateopt.name, updateopt.url, {event:'focus'} )
                    } else if (options.updateopts[i].on == 'change') {
                        editor.dependent( updateopt.name, updateopt.url, {event:'change'} )
                    }
                }
            }
        }

        // set Editor files if supplied
        if (files) {
            $.fn.dataTable.Editor.files = files
        }
    }

    // evaluate buttons
    buttons = checkeval(buttons);

    // set up buttons, special care for editor buttons
    var button_options = get_button_options(buttons, editor);
    $.extend(options.dtopts, {buttons:button_options});

    // handle rowReorder if requested; if no editor, disable rowReorder
    // assume an object was configured
    if (options.dtopts.rowReorder) {
        if (options.editoropts) {
            options.dtopts.rowReorder.editor = editor;
            options.dtopts.rowReorder.update = false;
            // 'row-reorder' event added later
        } else {
            options.dtopts.rowReorder = false;
        }
    }

    // assume data is url if serverSide is truthy
    if (options.dtopts.serverSide) {
        var url = data;
        // translate_datatable_group returns function which does the ajax data query, if doesn't exist, use url directly
        $.extend(options.dtopts, { ajax: (typeof translate_datatable_group === "function" && translate_datatable_group(url)) || url });

    // otherwise assume it is object containing the data to render
    } else {
        $.extend(options.dtopts, { data: data });
    }

    // define the table
    _dt_table = $('#datatable').DataTable ( options.dtopts );

    // configure childrow if so configured
    if ( ! $.isEmptyObject( options.childrow ) ) {
        // sets up child row event handling, and initializes child elements as needed
        var childrow = new ChildRow(_dt_table, options.childrow, editor, childrow_childbase, 'top');
    }

    // any column filtering required? if so, define the filters
    if ( ! $.isEmptyObject( options.yadcfopts ) ) {
        // general options supplied
        if (options.yadcfopts.hasOwnProperty('general')) {
            // assume also has columns key
            yadcf.init(_dt_table, options.yadcfopts.columns, options.yadcfopts.general);

        // only columns options supplied
        } else if (options.yadcfopts.hasOwnProperty('columns')) {
            yadcf.init(_dt_table, options.yadcfopts.columns);

        // legacy / backwards compatibility (just columns options
        } else {
            yadcf.init(_dt_table, options.yadcfopts);
        }
    }

    // handle rowReorder if requested; if no editor, disable rowReorder
    // https://datatables.net/reference/event/row-reorder
    if (options.dtopts.rowReorder) {
        if (options.editoropts) {
            // 'row-reorder' event added
            _dt_table.on( 'row-reorder', function ( e, details, changes ) {
                editor
                    .edit( changes.nodes, false, {
                        submit: 'allIfChanged'
                    } )
                    .multiSet( changes.dataSrc, changes.values )
                    .submit();
            });
        }
    }
    // take care of any initialization which needs to be done after datatables is initialized
    if (typeof afterdatatables !== "undefined") {
        afterdatatables();
    }

    // adjust scrolling to fit window
    firstDataTableScrollAdjust();        
}

// editor button dialog feature
function EditorButtonDialog(options) {
    // defaults
    this.options = {
        content: '',
        accordian: true,
    }
    Object.assign(this.options, options);

    this.popup = $('<div>').append(this.options.content);

    // accordian desired
    if (this.options.accordian) {
        this.content = this.popup.accordion({
            heightStyle: "content",
            animate: 30,
        });
        this.buttondialog = $('<div>').append(this.popup);

    // just plain dialog
    } else {
        this.content = this.popup;
        this.buttondialog = this.popup;
    }

    this.buttondialog.dialog({
        dialogClass: "no-titlebar",
        draggable: false,
        //resizeable: false,
        open: this.content,
        autoOpen: false,
        height: "auto",
        width: 450,
    });

    this.status = 0;

    this.click = function() {
        if (this.status == 0) {
            this.open()
        } else {
            this.close()
        }
    };

    this.open = function() {
        this.buttondialog.dialog("open");
        this.content.show();
        this.status = 1;
    };

    this.close = function() {
        this.buttondialog.dialog("close");
        this.content.hide();
        this.status = 0;
    };

    this.position = function(position) {
        this.buttondialog.dialog({
            position: position,
        });
    }
}


// from https://github.com/select2/select2/issues/1246#issuecomment-17428249
// $.ui.dialog.prototype._allowInteraction = function(e) {
//     return !!$(e.target).closest('.ui-dialog, .ui-datepicker, .select2-drop').length;
// };

// patch for select2 search. see https://stackoverflow.com/questions/19787982/select2-plugin-and-jquery-ui-modal-dialogs
// TODO: this causes "maximum call stack size exceeded" see #21
if ($.ui && $.ui.dialog && $.ui.dialog.prototype._allowInteraction) {
    var ui_dialog_interaction = $.ui.dialog.prototype._allowInteraction;
    $.ui.dialog.prototype._allowInteraction = function(e) {
        if ($(e.target).closest('.select2-dropdown').length) return true;
        return ui_dialog_interaction.apply(this, arguments);
    };
}

// patch to allow ckeditor subforms to collect input when issued from jquery ui dialog
// see https://stackoverflow.com/a/20555671/799921 and https://stackoverflow.com/a/64434126/799921
$.widget( "ui.dialog", $.ui.dialog, {
 /*! jQuery UI - v1.10.2 - 2013-12-12
  *  http://bugs.jqueryui.com/ticket/9087#comment:27 - bugfix
  *  http://bugs.jqueryui.com/ticket/4727#comment:23 - bugfix
  *  allowInteraction fix to accommodate windowed editors
  */
  _allowInteraction: function( event ) {
    if ( this._super( event ) ) {
      return true;
    }

    // address interaction issues with general iframes with the dialog
    if ( event.target.ownerDocument != this.document[ 0 ] ) {
      return true;
    }

    // address interaction issues with dialog window
    if ( $( event.target ).closest( ".cke_dialog" ).length ) {
      return true;
    }

    // address interaction issues with iframe based drop downs in IE
    if ( $( event.target ).closest( ".cke" ).length ) {
      return true;
    }

    // address interaction issues with ck input
    if ( $( event.target ).closest( ".ck-input" ).length ) {
      return true;
    }

  },
 /*! jQuery UI - v1.10.2 - 2013-10-28
  *  http://dev.ckeditor.com/ticket/10269 - bugfix
  *  moveToTop fix to accommodate windowed editors
  */
  _moveToTop: function ( event, silent ) {
    if ( !event || !this.options.modal ) {
      this._super( event, silent );
    }
  }
});


