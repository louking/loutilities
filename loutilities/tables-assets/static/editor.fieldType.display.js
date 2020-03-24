(function( factory ){
    if ( typeof define === 'function' && define.amd ) {
        // AMD
        define( ['jquery', 'datatables', 'datatables-editor'], factory );
    }
    else if ( typeof exports === 'object' ) {
        // Node / CommonJS
        module.exports = function ($, dt) {
            if ( ! $ ) { $ = require('jquery'); }
            factory( $, dt || $.fn.dataTable || require('datatables') );
        };
    }
    else if ( jQuery ) {
        // Browser standard
        factory( jQuery, jQuery.fn.dataTable );
    }
}(function( $, DataTable ) {
'use strict';


if ( ! DataTable.ext.editorFields ) {
    DataTable.ext.editorFields = {};
}

var _fieldTypes = DataTable.Editor ?
    DataTable.Editor.fieldTypes :
    DataTable.ext.editorFields;


_fieldTypes.display = {
    create: function ( conf ) {
        conf._div = $('<div/>').attr( $.extend( {
            id: conf.id
        }, conf.attr || {} ) );

        return conf._div[0];
    },

    get: function ( conf ) {
        return conf._rawHtml;
    },

    set: function ( conf, val ) {
        conf._rawHtml = val;
        conf._div.html( val );
    },

    enable: function ( conf ) {},

    disable: function ( conf ) {}
};


}));