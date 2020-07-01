/**
 * Use the next generation of the popular [CKEditor v5](http://ckeditor.com) WYSIWYG input control
 * in Editor to allow easy creation of complex HTML and Markdown content in a regular form field.
 * 
 * This plug-in supports all three types of editing mode provided by CKEditor v5:
 * 
 * * For the classic editing interface use a field type of `ckeditorClassic`
 * * For CKEditor balloon editing use `ckeditorBalloon`
 * * For CKEditor inline editing use `ckeditorInline`
 * 
 * Please refer to the CKEditor documentation for the difference between the various types. You
 * will need to load the CKEditor Javascript for the editor that you wish to use.
 *
 * @name CKEditor v5
 * @summary WYSIWYG editor
 * @requires [CKEditor](http://ckeditor.com)
 *
 * @opt `e-type object` **`opts`**: CKEditor initialisation options object.
 *   Please refer to the CKEditor v5 documentation for the full range of options
 *   available.
 *
 * @method **`inst`**: Get the CKEditor instance so you can manipulate it directly
 *   with CKEditor's own API.
 * 
 * @example
 *     
 * new $.fn.dataTable.Editor( {
 *   "ajax": "/api/customers",
 *   "table": "#customers",
 *   "fields": [ {
 *       "label": "Info:",
 *       "name": "info",
 *       "type": "ckeditorClassic"
 *     }, 
 *     // additional fields...
 *   ]
 * } );
 */

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

var types = [
    {
        fieldType: 'ckeditorClassic',
        inst: 'ClassicEditor'
    },
    {
        fieldType: 'ckeditorBalloon',
        inst: 'BalloonEditor'
    },
    {
        fieldType: 'ckeditorInline',
        inst: 'InlineEditor'
    }
];

$.each( types, function (i, type) {
    var fieldType = type.fieldType;
    var ckType = window[ type.inst ];
    
    _fieldTypes[ fieldType ] = {
        create: function ( conf ) {
            var that = this;
            var id = DataTable.Editor.safeId( conf.id );

            conf._input = $('<div id="'+id+'"></div>');
            ckType.create( conf._input[0], conf.opts )
                .then( function (editor) {
                    conf._ckeditor = editor;
                } );

            return conf._input;
        },

        get: function ( conf ) {
            return conf._ckeditor.getData();
        },

        set: function ( conf, val ) {
            // this line changed from what was in https://editor.datatables.net/plug-ins/field-type/editor.ckeditor5
            conf._ckeditor.setData( val || '' );
        },

        enable: function ( conf ) {}, // not supported in CKEditor

        disable: function ( conf ) {}, // not supported in CKEditor

        destroy: function ( conf ) {
            conf._ckeditor.destroy();
        },

        inst: function ( conf ) {
            return conf._ckeditor;
        }
    };
} );


}));
