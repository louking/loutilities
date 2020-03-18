$.fn.dataTable.ext.buttons.editRefresh = {
    extend: 'edit',
    text: 'Edit',
    action: function (e, dt, node, config) {
        var that = this;
        this.processing( true );

        config.editor._event( 'preEditRefresh', [dt, config.editor.s.action] )

        // Get currently selected row ids
        var selectedRows = dt.rows({selected:true}).ids();

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
                // Update the rows we get data back for
                for ( var i=0 ; i<json.data.length ; i++ ) {
                    // shouldn't use DT_RowId because of rowId configuration possibility
                    dt.row( '#'+json.data[i][dt.init().rowId] ).data( json.data[i] );
                }
                dt.draw(false);

                // Trigger the original edit button's action
                $.fn.dataTable.ext.buttons.edit.action.call(that, e, dt, node, config);

                // if error, display message - application specific
                if (json.error) {
                    // this is application specific
                    // not sure if there's a generic way to find the current editor instance
                    config.editor.error('ERROR retrieving row from server:<br>' + json.error);
                }
            }
        } );
    }
};
