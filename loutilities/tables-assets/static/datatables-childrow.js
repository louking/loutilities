/**
 * generic datatables child row handling
 */

/**
 * Child row management for a table
 *
 * @param {dataTable} table - dataTables instance of the table for which this child row is maintained
 * @param {string} template - name of nunjucks template file for display of the child row
 * @param config - list of ChildRowElement configurations
 *          options:    options to be passed to childrow DataTables instance,
 *                      except for data: and buttons: options, passed in childdata, childbuttons
 * @param {Editor} editor - Editor instance to use for create/open form
 * @constructor
 */
function ChildRow(table, config, editor) {
    var that = this;
    that.debug = true;

    if (that.debug) {console.log(new Date().toISOString() + ' ChildRow()');}

    // adapted from https://datatables.net/examples/api/row_details.html
    that.table = table;
    that.editor = editor;
    that.template = config.template;
    that.config = config;

    // childtable may be per table within row
    // current implementation has only one childeditor row open at a time, but it supports multiple tables
    that.childtable = {};
    that.childeditor = {};

    // clicking +/- displays the data
    that.table.on('click.dt', 'td.details-control', function () {
        if (that.debug) {console.log(new Date().toISOString() + ' click.dt event');}
        var tr = $(this).closest('tr');
        var tdi = tr.find("i.fa");
        var row = that.table.row( tr );

        if ( row.child.isShown() ) {
            // This row is already open - close it, close editor if open
            that.hideChild(row);
            that.closeChild(row);
            tr.removeClass('shown');
            tdi.first().removeClass('fa-minus-square');
            tdi.first().addClass('fa-plus-square');
        }
        else {
            // Open this row
            that.showChild(row);
            tr.addClass('shown');
            tdi.first().removeClass('fa-plus-square');
            tdi.first().addClass('fa-minus-square');
        }
    } );

    // set up events
    // selecting will open the child row if it's not already open
    // if it's already open need to hide the text display and bring up the edit form
    that.table.on('select.dt', function (e, dt, type, indexes) {
        if (that.debug) {console.log(new Date().toISOString() + ' select.dt event type = ' + type + ' indexes = ' + indexes);}
        var row = that.table.row( indexes );
        var tr = $(row.node());
        var tdi = tr.find("i.fa");

        if ( row.child.isShown() ) {
            // This row is already open - close it first
            that.hideChild(row);
        };
        that.editChild(row);
        tr.addClass('shown');
        tdi.first().removeClass('fa-plus-square');
        tdi.first().addClass('fa-minus-square');
    } );

    // deselect just hides the edit form and brings up the text display
    that.table.on('deselect.dt', function (e, dt, type, indexes) {
        if (that.debug) {console.log(new Date().toISOString() + ' deselect.dt event type = ' + type + ' indexes = ' + indexes);}
        // var tr = editor.s.modifier;
        // var row = that.table.row( tr );
        var row = that.table.row( indexes );
        var tr = $(row.node());
        if (row.child.isShown()) {
            that.closeChild(row);
            that.showChild(row);
        }
    } );

    // prevent user select on details control column
    that.table.on('user-select.dt', function (e, dt, type, cell, originalEvent) {
        if (that.debug) {console.log(new Date().toISOString() + ' user-select.dt event');}
        if ($(cell.node()).hasClass('details-control')) {
            e.preventDefault();
        }
    });
}

/**
 * get the table id for specified row, tablename
 *
 * @param row - datatables row
 * @param tablename - name of table
 * @returns {string} - hashtagged id for table row
 */
ChildRow.prototype.getTableId = function(row, tablename) {
    return '#childrow-table-' + tablename + '-' + row.id();
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
    var rowdata = row.data();
    for (var i=0; rowdata.tables && i<rowdata.tables.length; i++) {
        var tablemeta = rowdata.tables[i];
        var tableconfig = that.config.childelements[tablemeta.name];
        if (tableconfig) {
            var buttons = [];
            // if (showedit) {
            //     var edopts = _.cloneDeep(tableconfig.args.edopts);
            //
            //     that.childeditor[tablemeta.name] = new $.fn.dataTable.Editor(
            //         edopts
            //     )
            //
            //     buttons = [];
            // }
            var dtopts = _.cloneDeep(tableconfig.args.dtopts);
            if (tableconfig.args.columns && tableconfig.args.columns.datatable) {
                var dtextend = tableconfig.args.columns.datatable;
                $.each(dtopts.columns, function(index, col) {
                    if (dtextend.hasOwnProperty(col.data)) {
                        $.extend(col, dtextend[col.data]);
                    }
                })
            }
            $.extend(dtopts, {
                ajax: {
                    url: tablemeta.url,
                    type: 'get'
                },
                buttons: buttons,
                // need to remove scrollCollapse as we don't want to hide rows
                scrollCollapse: false,
            });
            if (!showedit) {
                $.extend(dtopts, {
                    select: false
                });
            };
            var table = $(that.getTableId(row, tablemeta.name));
            that.childtable[id] = that.childtable[id] || {}
            that.childtable[id][tablemeta.name] = table.DataTable(dtopts);
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

    // kill editor(s) if they exist
    if (that.childeditor) {
        $.each(that.childeditor, function(tablename, editor) {
            // editor.destroy();
        })
    }

    // kill table(s) if they exist
    if (that.childtable[id]) {
        $.each(that.childtable[id], function(tablename, table) {
            var table = $(that.getTableId(row, tablename));
            table.detach();
            table.DataTable().destroy();
        })
        delete that.childtable[id];
        // that.resetEvents();
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

    var id = row.id();

    // remove table(s) and editor(s)
    that.destroyTables(row);

    row.child.hide();
};

ChildRow.prototype.editChild = function(row) {
    var that = this;
    if (that.debug) {console.log(new Date().toISOString() + ' editChild()');}

    // see see https://datatables.net/examples/api/row_details.html, https://datatables.net/blog/2019-01-11
    var env = new nunjucks.Environment();
    var rowdata = row.data();
    rowdata._showedit = true;
    // todo: create table(s) and add to rowdata
    row.child(env.render(that.template, rowdata)).show();

    that.editor
        .title('Edit')
        .buttons([
            {
                "label": "Save",
                "fn": function () {
                    that.editor.submit();
                }
            }
        ])
        .edit(row); // in https://datatables.net/forums/discussion/62880

    // todo: add event handlers to make 'dirty' class to force saving later

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

    var rowdata = row.data();

    // remove table(s) and editor(s)
    that.destroyTables(row);

    row.child.hide();
};
