// generic datatables / Editor handling

// data is an list of objects for rendering or url for ajax retrieval of similar object
// buttons is a JSON parsable string, as it references editor which hasn't been instantiated yet
// options is an object with the following keys
//     dtopts:       options to be passed to DataTables instance, 
//                   except for data: and buttons: options, passed in data, buttons
//     editoropts:   options to be passed to Editor instance, 
//                   if not present, Editor will not be configured
//     updateopts:   options to configure Editor select fields with
//                   see crudapi.py for more details
//     yadcfopts:    yadcf options to be passed to yadcf 
//                   if not present, yadcf will not be configured

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
    if(_dt_table) {
        var height = jsGetDataTableHeightPx() + "px";
        $('.dataTables_scrollBody:has(#datatable)').css('max-height', height);
        $('.DTFC_LeftBodyLiner').css('max-height', height);
        _dt_table.draw();
    }
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

        // create editor instance
        $.extend(options.editoropts,{table:'#datatable'})
        editor = new $.fn.dataTable.Editor ( options.editoropts );

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

    // set up buttons, special care for editor buttons
    var button_options = [];
    for (i=0; i<buttons.length; i++) {
        button = buttons[i];
        if ($.inArray(button, ['create', 'edit', 'editRefresh', 'remove']) >= 0) {
            button_options.push({extend:button, editor:editor});
        } else {
            // convert button actions to javascript, // kludge for conversion from python
            if (button.hasOwnProperty('action')) {
                button.action = eval(button.action)
            }

            button_options.push(button);
        }
    };

    $.extend(options.dtopts, {buttons:button_options});

    // assume data is url if serverSide is truthy
    if (options.dtopts.serverSide) {
        $.extend(options.dtopts, { ajax: data });

    // otherwise assume it is object containing the data to render
    } else {
        $.extend(options.dtopts, { data: data });
    };

    // define the table
    _dt_table = $('#datatable').DataTable ( options.dtopts );

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

    // take care of any initialization which needs to be done after datatables is initialized
    if (typeof afterdatatables !== "undefined") {
        afterdatatables();
    };

    // adjust scrolling to fit window
    firstDataTableScrollAdjust();        
}

// from https://github.com/select2/select2/issues/1246#issuecomment-17428249
// $.ui.dialog.prototype._allowInteraction = function(e) {
//     return !!$(e.target).closest('.ui-dialog, .ui-datepicker, .select2-drop').length;
// };

// patch for select2 search. see https://stackoverflow.com/questions/19787982/select2-plugin-and-jquery-ui-modal-dialogs
if ($.ui && $.ui.dialog && $.ui.dialog.prototype._allowInteraction) {
    var ui_dialog_interaction = $.ui.dialog.prototype._allowInteraction;
    $.ui.dialog.prototype._allowInteraction = function(e) {
        if ($(e.target).closest('.select2-dropdown').length) return true;
        return ui_dialog_interaction.apply(this, arguments);
    };
}

