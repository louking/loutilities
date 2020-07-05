/**
 * from https://editor.datatables.net/plug-ins/display-controller/editor.onPage
 *
 * Example:
 *   var formeditor = new $.fn.dataTable.Editor( {
 *     ajax: '/api/staff',
 *     table: '#staff',
 *     display: onPageDisplay( $('#form-container') )
 *   } );
 *
 * @param elm - jquery element on which to hang the editor form
 * @returns {string} - name of created editor form
 */
function onPageDisplay ( elm ) {
    // from https://editor.datatables.net/plug-ins/display-controller/editor.onPage
    // also see https://editor.datatables.net/examples/plug-ins/displayController.html
    var name = 'onPage'+Math.random();
    var Editor = $.fn.dataTable.Editor;
    var emptyInfo;

    Editor.display[name] = $.extend( true, {}, Editor.models.display, {
        // Create the HTML mark-up needed the display controller
        init: function ( editor ) {
            // Setup the jqueryui - we'll use it for new entries
            Editor.display.jqueryui.init(editor);

            // emptyInfo = $(elm).html();
            return Editor.display[name];
        },

        // Show the form
        open: function ( editor, form, callback ) {
            if (editor.mode() == 'create') {
                // Its a new row. Use jqueryui
                Editor.display.jqueryui.open(editor, form, callback);

            } else if (editor.mode() == 'remove') {
                Editor.display.jqueryui.open(editor, form, callback);

            } else {
                $(elm).children().detach();
                $(elm).append( form );

                if ( callback ) {
                    callback();
                }
            }
        },

        // Hide the form
        close: function ( editor, callback ) {
            // close jqueryui if it's open
            Editor.display.jqueryui.close(editor, callback);

            $(elm).children().detach();
            // $(elm).html( emptyInfo );

            if ( callback ) {
                callback();
            }
        }
    } );

    return name;
}