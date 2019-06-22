// provide colvisToggleGroup plugin for Buttons

var DataTable = $.fn.dataTable;

function button_update( dt, button, conf ) {
    dt.columns( conf.columns ).visible( conf.visible, false );
    dt.columns.adjust();
    dt.draw();

    if (conf.visible) {
    dt.button(button).text( conf.visibletext );
    } else {
    dt.button(button).text( conf.hiddentext );  
    }
}

$.extend( DataTable.ext.buttons, {
    colvisToggleGroup: {
        className: 'buttons-colvisToggleGroup',

        init: function ( dt, button, conf ) {
        dt.on('init.dt', function(){
            button_update ( dt, button, conf )  
        });
    }, 
    
    action: function ( e, dt, button, conf ) {
        conf.visible = !conf.visible
        button_update ( dt, button, conf )       
        },

        visible: true,
    
    columns: [],
    
    visibletext: '',
    hiddentext: '',

    }
} );