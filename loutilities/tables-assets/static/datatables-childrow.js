/**
 * generic datatables child row handling
 */

/**
 * @typedef {Object<rowid, Object<tablename, ChildRowTableMeta>>} ChildRowMeta
 *
 * @typedef {Object} ChildRowTableMeta
 * @property {DataTable} table DataTable instance
 * @property {string} tableid css id for table
 * @property {Editor} [editor] Editor instance associated with table
 * @property {ChildRowMeta} [childbase] recursive childbase for this table
 *
 * @typedef {(string|number)} rowid DataTables id which identifies the row, e.g., row().id()
 *
 * @typedef {string} tablename name of table as configured in CrudChildElement.get_options()
 *
 */
/*
 * @type {ChildRowMeta} - maintains the data for all child rows
 */
var childrow_childbase = {};

// save datatable childrow post create hooks
var childrow_postcreate_hooks = {};
/**
 * add a hook which is called after child row datatable, editor created for a childrow table
 *
 * @param tablename - {str} name of table
 * @param fn - after table created, function fn is passed datatable and (optional) editor instance, fn(datatable, [editor])
 */
function childrow_add_postcreate_hook(tablename, fn) {
    if (!childrow_postcreate_hooks.hasOwnProperty(tablename)) {
        childrow_postcreate_hooks[tablename] = []
    }
    childrow_postcreate_hooks[tablename].push(fn);
}

/**
 * initial rendering of + in column for expanding child row, for fontawesome child row handling
 *
 * @returns {string} - i tag with classes fa fa-plus-square
 */
function render_plus() {
     // see http://live.datatables.net/bihawepu/1/edit
     // from https://datatables.net/examples/api/row_details.html bindrid comment
    return '<i class="fa fa-plus-square" aria-hidden="true"></i>';
}

function render_grip() {
    return '<i class="fa fa-grip-horizontal" aria-hidden="true"></i>';
}

/**
 * check tables to see if unsaved changes
 *
 * @param base - childrow base from which to work
 * @param row - row
 * @param debug - true if debug required
 * @returns {boolean} - true if ok to remove tables for this row
 */
function checkTables(base, row, debug) {
    if (debug) {console.log(new Date().toISOString() + ' checkTables()');}

    // assume all is ok
    var oktoclose = true;

    // check table(s) and editor(s) if they exist
    var id = row.id();
    if (base[id]) {
        $.each(base[id], function (tablename, rowtablemeta) {
            // drill down if needed
            var tablenames = Object.keys(base[id]);
            for (var i=0; i<tablenames.length; i++) {
                var tablename = tablenames[i];
                var childbase = base[id][tablename].childbase;
                if (childbase) {
                    var rowids = Object.keys(childbase);
                    for (j=0; j<rowids.length; j++) {
                        var rowid = rowids[j];
                        var thisrow = base[id][tablename].table.row('#' + rowid);
                        if ( ! checkTables(childbase, thisrow, debug)) {
                            if (debug) {
                                console.log(new Date().toISOString() + ' checkTables(): cancelling close (from lower level)');
                            }
                            oktoclose = false;
                            return false;
                        }
                    }
                }
            }

            // check this row
            if (rowtablemeta.editor) {
                var editor = rowtablemeta.editor;
                // note at this level savedvalues is kept in editor class
                if (editor.savedvalues) {
                    if (editor.savedvalues !== JSON.stringify(editor.get())) {
                        if (!confirm('You have unsaved changes. Are you sure you want to exit?')) {
                            // abort!
                            if (debug) {
                                console.log(new Date().toISOString() + ' checkTables(): cancelling close');
                            }
                            oktoclose = false;
                        }
                        // break out of jquery $.each regardless of response to confirm
                        return false;
                    }
                }
            }
        });
    }

    return oktoclose;
}

/**
 * Child row management for a table
 *
 * @param {dataTable} table - dataTables instance of the table for which this child row is maintained
 * @param config - list of ChildRowElement configurations
 *          options:    options to be passed to childrow DataTables instance,
 *                      except for data: and buttons: options, passed in childdata, childbuttons
 * @param {Editor} editor - Editor instance to use for create/open form
 * @param {ChildRowMeta} base - ChildRow data is maintained here; this can be recursively used for child rows within child rows
 *          if base isn't supplied,
 * @constructor
 */
function ChildRow(table, config, editor, base) {
    var that = this;
    that.debug = true;

    if (that.debug) {console.log(new Date().toISOString() + ' ChildRow()');}

    // adapted from https://datatables.net/examples/api/row_details.html
    that.table = table;
    that.editor = editor;
    that.template = config.template;
    that.config = config;
    that.base = base;

    // set up table postcreate hook, if requested
    var cekeys = Object.keys(that.config.childelements);
    for (var i=0; i<cekeys.length; i++) {
        // variable names assume it's a table, but if it's not we'll skip processing
        var tablename = cekeys[i];
        var tableconfig = that.config.childelements[tablename];
        if (tableconfig.type === '_table') {
            if (tableconfig.args.postcreatehook) {
                var postcreatefn = eval(tableconfig.args.postcreatehook);
                childrow_add_postcreate_hook(tablename, postcreatefn);
            }
        }
    }

    // clicking +/- in a row displays the row's data
    that.table.on('click', 'td.details-control', function (e) {
        if (that.debug) {console.log(new Date().toISOString() + ' click row details control event');}

        // don't let this bubble to an outer table in the case of recursive child rows
        if ( $(this).closest('table').attr('id') != $(that.table.table().node()).attr('id') ) {
            return;
        }

        var tr = $(this).closest('tr');
        var tdi = tr.find("i.fa");
        var row = that.table.row( tr );

        if ( row.child.isShown() ) {
            // This row is already open - close it, close editor if open, abort if close error
            if ( ! that.closeChild(row) ) {
                return;
            }
            that.hideChild(row);
        }
        else {
            // Open this row
            that.showChild(row);
        }
    } );

    // clicking +/- in the header displays all rows' data
    // see https://datatables.net/forums/discussion/comment/125858/#Comment_125858
    $(that.table.table().header()).on('click', 'th.details-control', function (e) {
        if (that.debug) {console.log(new Date().toISOString() + ' click header details control event');}

        // if all shown or some shown, close all that are open
        var thead = $(that.table.header())
        var thi = thead.find("i.fa");
        if (thead.hasClass('allshown') || thead.hasClass('someshown')) {
            var rows = that.table.rows();
            for (var i=0; i<rows[0].length; i++) {
                var rowndx = rows[0][i];
                if (that.table.row(rowndx).child.isShown()) {
                    var tr = $(that.table.row(rowndx).node());
                    var tdi = tr.find("i.fa");
                    tdi.first().trigger('click');
                }
            }

        // none shown, so show all
        } else {
            var rows = that.table.rows();
            for (var i=0; i<rows[0].length; i++) {
                var rowndx = rows[0][i];
                var tr = $(that.table.row(rowndx).node());
                var tdi = tr.find("i.fa");
                tdi.first().trigger('click');
            }
        }
        that.updateHeaderDetails();
    });

    // sometimes DataTables draws the table which changes the row configuration, so need to
    // update the header details
    that.table.on('draw.dt', function(e, settings) {
        that.updateHeaderDetails();
    });

    // edit button will open the child row if it's not already open
    // if it's already open need to hide the text display and bring up the edit form
    if (that.editor) {
        // bring up edit view after refresh
        that.editor.on('postEditChildRowRefresh', function (e, json, dt, node, config) {
            // // check if triggered by this datatable
            // if (dt.context[0].sTableId !== that.table.context[0].sTableId) return;

            if (that.debug) {
                console.log(new Date().toISOString() + ' postEditChildRowRefresh ');
            }

            // if error, display message and return
            if (json.error) {
                // this is application specific
                // not sure if there's a generic way to find the current editor instance
                that.editor.error('ERROR retrieving row from server:<br>' + json.error);
                return;
            }

            // assumes only one row can be selected
            var row = that.table.row({selected:true});
            var tr = $(row.node());
            var tdi = tr.find("i.fa");

            if (row.child.isShown()) {
                // This row is already open - close it first
                that.hideChild(row);
            }

            that.editChild(row);

            that.updateHeaderDetails();
        });
    }

    // submit closes the edit form and brings up the text display
    if (that.editor) {
        that.editor.on('submitComplete.dt', function (e, json, data, action) {
            if (that.debug) {
                console.log(new Date().toISOString() + ' submitComplete.dt event, action = ' + action);
            }

            // we only care about edit submits
            if (action !== 'edit') {
                return;
            }

            // don't close if error occurred
            if (json.error) {
                return;
            }

            // take no action if this was a row reorder. normal submit should only be single row
            var modifier = that.editor.modifier();
            if (modifier.length > 1) {
                return;
            }

            // not sure this is necessary, as after the submit there's a draw which seems to close the row
            var row = that.table.row(modifier);
            var tr = $(row.node());
            if (row.child.isShown()) {
                // successful save, don't need savedvalues any more
                if (that.debug) {console.log(new Date().toISOString() + ' submitComplete.dt: removing savedvalues');}
                delete that.savedvalues;
                that.closeChild(row);
            }
            that.updateHeaderDetails();
        });
    }

    // prevent user select on details control column
    that.table.on('user-select.dt', function (e, dt, type, cell, originalEvent) {
        if (that.debug) {console.log(new Date().toISOString() + ' user-select.dt event');}
        if ($(cell.node()).hasClass('details-control')) {
            e.preventDefault();
        }
    });
}

/**
 * update the shown class and indicator for the header for this table
 */
ChildRow.prototype.updateHeaderDetails = function() {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' updateHeaderDetails() ');}

    var thead = $(that.table.header())
    var thi = thead.find("i.fa");
    var rows = that.table.rows();
    var shown = $( that.table.table().node()).find('tr.shown');

    thead.removeClass('allshown someshown');
    thi.first().removeClass('fa-plus-square fa-minus-square fa-square');

    if (shown.length == 0) {
        thi.first().addClass('fa-plus-square');
    } else if (shown.length == rows[0].length) {
        thead.addClass('allshown');
        thi.first().addClass('fa-minus-square');
    } else {
        thead.addClass('someshown');
        thi.first().addClass('fa-square');
    }

}

ChildRow.prototype.updateRowDetails = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' updateRowDetails() ');}

    var tr = row.node();
    var tdi = $(tr).find('i.fa').first();

    $(tr).removeClass('shown');
    tdi.removeClass('fa-plus-square fa-minus-square');
    if (row.child.isShown()) {
        tdi.addClass('fa-minus-square');
        $(tr).addClass('shown');
    } else {
        tdi.addClass('fa-plus-square');
    }
    that.updateHeaderDetails();
}

/**
 * get the table id for specified row, tablename
 *
 * @param row - datatables row
 * @param tablename - name of table
 * @returns {string} - hashtagged id for table row
 */
ChildRow.prototype.getTableId = function(row, tablename) {
    var that = this;
    var rowdata = row.data();
    var tablemeta = that.getTableMeta(row, tablename);
    return '#childrow-table-' + tablemeta.tableid;
}

/**
 * get the tablemeta for this table
 *
 * @param row
 * @param tablename
 * @returns {tablemeta}
 */
ChildRow.prototype.getTableMeta = function(row, tablename) {
    var rowdata = row.data();
    var tablemeta = null;
    for (var i=0; rowdata.tables && i<rowdata.tables.length; i++) {
        table = rowdata.tables[i];
        if (table.name == tablename) {
            tablemeta = table;
            break;
        }
    }
    if (tablemeta === null) {
        throw 'could not find table in row: ' + tablename;
    }
    return tablemeta;
}

/**
 * show tables for this row
 *
 * @param row - dataTables row
 * @param showedit - true if editor to be used
 */
ChildRow.prototype.showTables = function(row, showedit) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' showTables()');}

    // if there are tables, render them now
    var id = row.id();
    that.base[id] = that.base[id] || {};
    var rowdata = row.data();
    for (var i=0; rowdata.tables && i<rowdata.tables.length; i++) {
        var tablemeta = rowdata.tables[i];
        var tableconfig = that.config.childelements[tablemeta.name];

        if (tableconfig) {
            // initialize base[id][tablename] if needed
            that.base[id][tablemeta.name] = that.base[id][tablemeta.name] || {};
            var childrowtablemeta = that.base[id][tablemeta.name];

            childrowtablemeta.tableid = childrowtablemeta.tableid || that.getTableId(row, tablemeta.name);

            var buttons = [];
            var dtopts = _.cloneDeep(tableconfig.args.dtopts);
            if (showedit) {
                var edopts = _.cloneDeep(tableconfig.args.edopts);

                // add requested editor field options
                if (tableconfig.args.columns && tableconfig.args.columns.editor) {
                    var edextend = tableconfig.args.columns.editor;
                    $.each(edopts.fields, function(index, field) {
                        if (edextend.hasOwnProperty(field.name)) {
                            $.extend(field, edextend[field.name]);
                        }
                    })
                }

                // if inline editing is requested, annotate the fields with _inline-edit class
                // note need to do this with dtopts as the dtopts.col.className option takes precedence
                if (tableconfig.args.inline) {
                    var inline = tableconfig.args.inline;
                    $.each(dtopts.columns, function(index, col) {
                        if (inline.hasOwnProperty(col.data)) {
                            // not quite sure why I'm using 'class' not 'className'
                            // see https://datatables.net/reference/option/columns.className
                            col.className = (col.className || '') + ' _inline_edit'
                        }
                    });
                }

                $.extend(edopts, {
                    table: childrowtablemeta.tableid
                });

                // configure childrow options for editor if so configured
                if ( ! $.isEmptyObject( tableconfig.args.cropts ) ) {
                    if (tableconfig.args.cropts.showeditor) {
                        $.extend(edopts, {display:onPageDisplay('#childrow-editform-' + tablemeta.tableid)})
                    }
                }

                // create child row editor
                childrowtablemeta.editor = new $.fn.dataTable.Editor(edopts);

                // get confirmation when navigating away from changed edit forms,
                // for editors on tables which don't have child row
                childrowtablemeta.editor
                    .on( 'open', function (e, mode, action) {
                        // this is Editor
                        var childeditor = this;

                        // Store the values of the fields on open (store in editor space)
                        childeditor.savedvalues = JSON.stringify( childeditor.get() );

                        childeditor.on( 'preClose', function ( e ) {
                            // On close, check if the values have changed and ask for closing confirmation if they have
                            if ( childeditor.savedvalues !== JSON.stringify( childeditor.get() ) ) {
                                var confirmed = confirm( 'You have unsaved changes. Are you sure you want to exit?' );
                                return confirmed;
                            }
                        } )
                    } )
                    .on( 'postCreate postEdit close', function () {
                        // this is Editor
                        var childeditor = this;

                        childeditor.off( 'preClose' );
                        delete childeditor.savedvalues;
                    } );

                // set up special event handlers for group management, if requested
                if (register_group_for_editor) {
                    if (that.config.group) {
                        if (!that.config.groupselector) {
                            throw 'groupselected required if group configured'
                        }
                        register_group_for_editor(that.config.group, that.config.groupselector, childrowtablemeta.editor)
                        set_editor_event_handlers(childrowtablemeta.editor)
                    }
                }

                // if inline editing requested, add a handler
                if (tableconfig.args.inline) {
                    $( childrowtablemeta.tableid ).on('click', '._inline_edit', function() {
                        // get inline parameters
                        var colname = childrowtablemeta.editor.fields()[this._DT_CellIndex.column];
                        var inlineopts = tableconfig.args.inline[colname];
                        childrowtablemeta.editor.inline(this, inlineopts);
                    });
                }

                // if createfieldvals requested, add a handler which initializes fields when create form displayed
                if (tablemeta.createfieldvals) {
                    // save for initCreate function
                    childrowtablemeta.editor.createfieldvals = tablemeta.createfieldvals;
                    childrowtablemeta.editor.on('initCreate.dt', function(e) {
                        var that = this;
                        $.each(this.createfieldvals, function(field, val) {
                            that.field(field).val(val);
                        });
                    });
                }

                // annotate buttons as appropriate
                buttons = get_button_options(tableconfig.args.buttons, childrowtablemeta.editor)
            }
            // add requested datatable column options
            if (tableconfig.args.columns && tableconfig.args.columns.datatable) {
                var dtextend = tableconfig.args.columns.datatable;
                $.each(dtopts.columns, function(index, col) {
                    if (dtextend.hasOwnProperty(col.data)) {
                        $.extend(col, dtextend[col.data]);
                    }
                })
            }
            $.extend(dtopts, {
                // TODO: ajax assumes serverside=True
                ajax: {
                    url: tablemeta.url,
                    type: 'get'
                },
                buttons: buttons,
                // need to remove scrollCollapse as we don't want to hide rows
                scrollCollapse: false,
            });
            if (tableconfig.args.updatedtopts) {
                $.extend(dtopts, tableconfig.args.updatedtopts);
            }
            if (!showedit) {
                $.extend(dtopts, {
                    select: false
                });
            };
            var table = $( childrowtablemeta.tableid );
            childrowtablemeta.table = table
                // don't let select / deselect propogate to the parent table
                // from https://datatables.net/forums/discussion/comment/175517/#Comment_175517
                .on('select.dt deselect.dt draw.dt', function (e) {
                    e.stopPropagation();
                })
                .DataTable(dtopts);

            // configure childrow if so configured
            if ( ! $.isEmptyObject( tableconfig.args.cropts ) ) {
                // sets up child row event handling, and initializes child elements as needed
                childrowtablemeta.childbase = {}
                var childsubrow = new ChildRow(childrowtablemeta.table, tableconfig.args.cropts, childrowtablemeta.editor, childrowtablemeta.childbase);
            }

            // fire any childrow_postcreate_hooks hooks
            if (childrow_postcreate_hooks.hasOwnProperty(tablemeta.name)) {
                for (var i=0; i<childrow_postcreate_hooks[tablemeta.name].length; i++) {
                    var fn = childrow_postcreate_hooks[tablemeta.name][i];
                    fn(childrowtablemeta.table, childrowtablemeta.editor);
                }
            }

        } else {
            throw 'table missing from config.childelements: ' + tablemeta.name;
        }
    }
}

/**
 * destroy tables and editors
 *
 * @param row - datatables row
 */
ChildRow.prototype.destroyTables = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' destroyTables()');}

    var id = row.id();

    // kill table(s) and editor(s) if they exist
    if (that.base[id]) {
        $.each(that.base[id], function(tablename, rowtablemeta) {
            var table = $( that.base[id][tablename].tableid );
            table.detach();
            table.DataTable().destroy();
            if (rowtablemeta.editor) {
                var editor = rowtablemeta.editor;
                editor.destroy();
            }
        })
        delete that.base[id];
    }
}

/**
 * show child row
 *
 * @param row - row which gets expanded
 */
ChildRow.prototype.showChild = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' showChild()');}

    // see see https://datatables.net/examples/api/row_details.html, https://datatables.net/blog/2019-01-11
    var env = new nunjucks.Environment();
    var rowdata = row.data();
    rowdata._showedit = false;
    row.child(env.render(that.template, rowdata)).show();
    that.updateRowDetails(row);

    // show tables
    that.showTables(row, rowdata._showedit);
};

/**
 * hide child row
 *
 * @param row - row to hide
 */
ChildRow.prototype.hideChild = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' hideChild()');}

    // remove table(s) and editor(s)
    that.destroyTables(row);

    row.child.hide();
    that.updateRowDetails(row);
};

/**
 * open the editor for this row
 *
 * @param row
 */
ChildRow.prototype.editChild = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' editChild()');}

    // On new edit, check if the values have changed and ask for closing confirmation if they have
    if (that.debug) {console.log(new Date().toISOString() + ' editChild(): checking savedvalues');}
    if ( that.savedvalues  ) {
        // try closing the row being edited, user may abort at this point
        if ( ! that.closeChild(that.editrow) ) {
            // turn off processing (found in loutilities/tables-assets/static/editor.buttons.editchildrowrefresh.js
            that.editor._event( 'preOpen', [])
            return;
        }
    }

    // see see https://datatables.net/examples/api/row_details.html, https://datatables.net/blog/2019-01-11
    var env = new nunjucks.Environment();
    var rowdata = row.data();
    rowdata._showedit = true;
    row.child(env.render(that.template, rowdata)).show();
    that.updateRowDetails(row);

    that.editor
        .title('Edit')
        .buttons([
            {
                "text": "Save",
                "action": function () {
                    that.editor.submit();
                }
            },
            {
                "text": "Cancel",
                "action": function() {
                    that.closeChild(row);
                }
            }
        ])
        .edit(row); // in https://datatables.net/forums/discussion/62880

    // save current values so we can verify change on close
    // requires Editor 1.9.5 (or patch to editor.jqueryui.js (editor.jqueryui.patch-discussion-63653.js)
    if (that.debug) {console.log(new Date().toISOString() + ' editChild(): saving savedvalues');}
    that.savedvalues = JSON.stringify(that.editor.get());
    that.editrow = row;


    // show tables
    that.showTables(row, rowdata._showedit);
}

/**
 * close child row
 *
 * @param row - row to hide
 */
ChildRow.prototype.closeChild = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' closeChild()');}

    // check tables to see if there are any changed rows. This returns false if we need to abort
    if ( ! checkTables(that.base, row, that.debug) ) {
        return false;
    }

    // On close, check if the values have changed and ask for closing confirmation if they have
    if (that.debug) {console.log(new Date().toISOString() + ' closeChild(): checking savedvalues');}
    if ( that.savedvalues && that.savedvalues !== JSON.stringify(that.editor.get()) ) {
        if ( ! confirm( 'You have unsaved changes. Are you sure you want to exit?' ) ) {
            // abort!
            if (that.debug) {
                console.log(new Date().toISOString() + ' closeChild(): cancelling close');
            }
            return false;
        }
    }

    // closing so we need to remove savedvalues
    if ( that.savedvalues ) {
        if (that.debug) {console.log(new Date().toISOString() + ' closeChild(): removing savedvalues');}
        delete that.savedvalues;
    }

    // remove table(s) and editor(s)
    that.destroyTables(row);

    row.child.hide();
    that.updateRowDetails(row);

    // successful
    return true;
};
