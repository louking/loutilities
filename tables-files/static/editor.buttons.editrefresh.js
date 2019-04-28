$.fn.dataTable.ext.buttons.editRefresh = {
    extend: 'edit',
    text: 'Edit',
    action: function (e, dt, node, config) {
        this.processing( true );

        // Get currently selected row ids
        var selectedRows = dt.rows({selected:true}).ids();
        var that = this;

        // Ajax request to refresh the data for those ids
        $.ajax( {
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
                    editor.error('ERROR retrieving row from server:<br>' + json.error);
                }
            }
        } );
    }
};
