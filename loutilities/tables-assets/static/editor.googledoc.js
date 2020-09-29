// googledoc field type plug-in code
(function ($, DataTable) {
 
if ( ! DataTable.ext.editorFields ) {
    DataTable.ext.editorFields = {};
}
 
var Editor = DataTable.Editor;
var _fieldTypes = DataTable.ext.editorFields;
 
_fieldTypes.googledoc = {
    create: function ( conf ) {
        var that = this;
 
        conf._enabled = true;
 
        // Create the elements to use for the input
        conf._input = $(
            '<div id="'+Editor.safeId( conf.id )+'">'+
            '</div>');
 
        var atext = 'use opts:{text:"text for link"}';
        if ( conf.hasOwnProperty( 'opts' ) && conf.opts.hasOwnProperty( 'text' )) {
            atext = conf.opts.text;
        }
        $(conf._input).attr('atext', atext)

        return conf._input;
    },
 
    get: function ( conf ) {
        return $(conf._input).attr('value');
    },
 
    set: function ( conf, val ) {
        // remove any links present
        $('.'+Editor.safeId( conf.id )+'.DTE_FieldType_googledoc').remove();
        $(conf._input).attr( 'value', val );
        // add link to google doc if val present
        if (val != "") {
            // note uses /preview so not editable
            $(conf._input).append('<a class="'+Editor.safeId( conf.id )+' DTE_FieldType_googledoc" target=_blank href="https://docs.google.com/document/d/' + $(conf._input).attr( 'value' ) + '/preview">'+$(conf._input).attr( 'atext' )+'</a>')
        }
    },
 
    enable: function ( conf ) {
        conf._enabled = true;
        $(conf._input).removeClass( 'disabled' );
    },
 
    disable: function ( conf ) {
        conf._enabled = false;
        $(conf._input).addClass( 'disabled' );
    }
};
 
})(jQuery, jQuery.fn.dataTable);