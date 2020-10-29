/**
 * extend buttons with 'editChildRowRefresh'
 * generates preEditChildRowRefresh before start
 * generates postEditChildRowRefresh when ajax completes, after refreshing row in table
 *
 * @type {{extend: string, action: $.fn.dataTable.ext.buttons.editChildRowRefresh.action, text: string}}
 */
$.fn.dataTable.ext.buttons.editChildRowRefresh = {
    extend: 'edit',
    text: 'Edit',
    name: 'editRefresh',
    action: function (e, dt, node, config) {
        var that = this;

        // this puts spinner on the edit button until the form is about to open
        // see dataTables.editor.js _buttons.edit ( $.extend( _buttons, {edit: ... }) )
        that.processing( true );
        config.editor.one('preOpen', function() {
           that.processing( false );
        });

        // Get currently selected row ids
        var selectedRows = dt.rows({selected:true}).ids();

        config.editor._event( 'preEditChildRowRefresh', [dt, config.editor.s.action] )

        // Ajax request to refresh the data for those ids
        $.ajax( {
            // application specific: my application has different urls for different methods
            url: config.editor.ajax().editRefresh.url,
            type: 'post',
            dataType: 'json',
            data: {
                // application specific: my application wants 'action' in the POST method data
                action: 'refresh',
                refresh: 'rows',
                ids: selectedRows.toArray().join(',')
            },
            success: function ( json ) {
                if (json.data) {
                    // Update the rows we get data back for
                    for (var i = 0; i < json.data.length; i++) {
                        // shouldn't use DT_RowId because of rowId configuration possibility
                        dt.row('#' + json.data[i][dt.init().rowId]).data(json.data[i]);
                    }
                    // this seems to cause the parent table to close the row being edited
                    // dt.draw(false);
                }

                config.editor._event( 'postEditChildRowRefresh', [json, dt, node, config] );
                // triggered function is required to show child row and open edit window
            }
        } );
    }
};
