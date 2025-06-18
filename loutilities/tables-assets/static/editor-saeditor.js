/**
 * @file provides class for standalone Editor management
 */

/**
 * Standalone Editor management
 *
 * @class
 * @param {object} options - options for the SaEditor instance
 * @param {string} options.title - title for standalone editor window
 * @param {field-options[]} [options.fields=[]] - array of Editor fields
 * @param {button-options[]} [options.buttons=['Submit']] - array of button-options
 * @param {SaEditor~UrlParams} [options.get_urlparams] - callback function which returns object of parameters to
 *      override in url params of ajax url
 * @param {SaEditor~AfterInit} [options.after_init] - callback function called at end of init()
 * @param {SaEditor~FormValues} options.form_values - return fieldNames object based on json object per
 *      https://editor.datatables.net/reference/api/set(). json is response from ajax call in this.edit_button_hook()
 * @constructor
 */
function SaEditor(options) {
    var that = this;

    // save parameters
    that.title = options.title;
    that.fields = options.fields || [];
    that.buttons = options.buttons || ['Submit'];
    that.after_init = options.after_init || function () {
    }
    that.get_urlparams = options.get_urlparams || function () {
        return {}
    }
    that.form_values = options.form_values || function (json) {
        return json
    }

    // remember the standalone editor instance
    that.saeditor = undefined;

    // note we can't initialize here, because there's some chicken/egg problem with initializing ckeditor
    // that.init();
};

/**
 * Return a function which does action for table button. This needs to be invoked before datatables is initialized.
 *
 * @param url - this url is used to retrieve initial values for form. This should be without arguments. Current
 *      location arguments are merged with result of get_urlparams() response
 * @returns {fn}
 */
SaEditor.prototype.edit_button_hook = function(url) {
    var that = this;
    fn = function (e, dt, node, config) {
        // add motion_id to url parameters
        var urlparams = allUrlParams();
        _.assign(urlparams, that.get_urlparams(e, dt, node, config));

        // update the url parameter for the standalone view, used by submit button
        var editorajax = that.saeditor.ajax() || {};
        editorajax.url = url + '?' + setParams(urlparams);
        that.saeditor.ajax(editorajax);

        // get values for form
        $.ajax( {
            url: url + '?' + setParams(urlparams),
            type: 'get',
            dataType: 'json',
            success: function ( json ) {
                // if error, display message - application specific
                if (json.error) {
                    // this is application specific
                    // not sure if there's a generic way to find the current editor instance
                    that.saeditor.error(json.error);
                    showerrorpopup(json.error);

                } else {
                    that.saeditor
                        .title(that.title)
                        // no editing id, and don't show immediately
                        .edit(null, false)
                        .set(that.form_values(json))
                        .open();
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                showerrorpopup(textStatus + ' ' + jqXHR.status +' ' + errorThrown);
            }
        } );
    }
    return fn;
};

SaEditor.prototype.init = function() {
    var that = this;
    that.saeditor = new $.fn.dataTable.Editor({
        fields: that.fields
    });

    // buttons needs to be set up outside of ajax call else the button action doesn't fire
    // (see https://stackoverflow.com/a/19237302/799921 for ajax hint)
    that.saeditor
        .buttons(that.buttons)

    // user function called after init
    that.after_init();
};

/**
 * return url parameters for SaEditor
 *
 * @callback SaEditor~UrlParams
 * @param e - parameters for https://datatables.net/reference/option/buttons.buttons.action()
 * @param dt - parameters for https://datatables.net/reference/option/buttons.buttons.action()
 * @param node - parameters for https://datatables.net/reference/option/buttons.buttons.action()
 * @param config - parameters for https://datatables.net/reference/option/buttons.buttons.action()
 * @returns {object} object with url parameters to add override in url params of ajax url
 */

/**
 * callback function called at end of init()
 * 
 * @callback SaEditor~AfterInit
 */

/**
 * return fieldNames object based on json object per https://editor.datatables.net/reference/api/set()
 *
 * @callback SaEditor~FormValues
 * @param {object} [json=ajax_response] - json response from ajax call in edit_button_hook()
 * @returns {object} fieldNames object based on json object per https://editor.datatables.net/reference/api/set()
 */

/**
 * Fields to add to the form during initialisation - see {@link https://editor.datatables.net/reference/option/fields}
 * @typedef field-options
 */
/**
 * Define the control buttons to be shown in the form - see {@link https://editor.datatables.net/reference/api/buttons()}
 * @typedef button-options
 */

