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
function ChildRow(table, template, config, editor) {
    // adapted from https://datatables.net/examples/api/row_details.html
    var that = this;
    that.table = table;
    that.editor = editor;
    that.template = template;
    that.config = config;

    // clicking +/- displays the data
    that.table.on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var tdi = tr.find("i.fa");
        var row = that.table.row( tr );

        if ( row.child.isShown() ) {
            // This row is already open - close it
            that.hideChild(row);
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

    // selecting will open the child row if it's not already open
    // if it's already open need to hide the text display and bring up the edit form
    that.table.on('select', function (e, dt, type, indexes) {
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
    that.table.on('deselect', function () {
        var tr = editor.s.modifier;
        var row = that.table.row( tr );
        that.closeChild(row);
        that.showChild(row);
    } );

    that.table.on('user-select', function (e, dt, type, cell, originalEvent) {
        if ($(cell.node()).hasClass('details-control')) {
            e.preventDefault();
        }
    });

}

/**
 * show child row
 *
 * @param row - row which gets expanded
 */
ChildRow.prototype.showChild = function(row) {
    var that = this;

    // see see https://datatables.net/examples/api/row_details.html, https://datatables.net/blog/2019-01-11
    var env = new nunjucks.Environment();
    var rowdata = row.data();
    rowdata._showedit = false;
    // todo: create table(s) and add to rowdata
    row.child(env.render(that.template, rowdata)).show();

};

/**
 * hide child row
 *
 * @param row - row to hide
 */
ChildRow.prototype.hideChild = function(row) {
    var that = this;

    row.child.hide();
    // todo: destroy table(s)
};

ChildRow.prototype.editChild = function(row) {
    var that = this;

    // see see https://datatables.net/examples/api/row_details.html, https://datatables.net/blog/2019-01-11
    var env = new nunjucks.Environment();
    var rowdata = row.data();
    rowdata._showedit = true;
    // todo: create table(s) and add to rowdata
    row.child(env.render(that.template, rowdata)).show();

    // todo: var that = this, add event handlers to make 'dirty' class to force saving later

    that.editor
        .buttons([
            {
                "label": "Save",
                "fn": function () {
                    editor.submit();
                }
            }
        ])
        .edit(row); // in https://datatables.net/forums/discussion/62880
}

/**
 * close child row
 *
 * @param row - row to hide
 */
ChildRow.prototype.closeChild = function(row) {
    var that = this;
    var rowdata = row.data();
    row.child.hide();
    // todo: destroy table(s)
};

/**
 * Child row element management for a child row
 *
 * @param {ChildRow} childrow - ChildRow instance
 * @param options
 * @constructor
 */
function ChildRowElement(childrow, options) {
    this.childrow = childrow;
    this.options = options;
}