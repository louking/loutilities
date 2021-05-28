/**
 * @file provides class for Background Post Data Manager
 */

/**
 * Background Post Data Data Manager
 *
 * @class
 * @param {object} options - options for the BackgroundPostDataManager instance
 * @param {string} options.urlpath - url for resource update request
 * @param {object} options.urlparams - object containing any required url parameters for POST request
 * @param {BackgroundPostDataManager~PostData} [options.get_postdata] - callback function which returns data to be sent with
 *          the POST
 * @param {BackgroundPostDataManager~AfterPost} [options.afterposthook] - callback function which is called after
 *          the POST
 * @param {BackgroundPostDataManager~AfterSuccess} [options.aftersuccesshook] - callback function which is called after
 *          successful completion of background task
 * @param {string} options.progressbarcontainer - id for progress bar container, defaults to 'progressbar-container'
 * 
 * @constructor
 */
function BackgroundPostDataManager(options) {
    var that = this;

    // save parameters
    that.urlpath = options.urlpath;
    that.get_postdata = options.get_postdata || function() {return null};
    that.afterposthook = options.afterposthook || function() {};
    that.aftersuccesshook = options.aftersuccesshook || function() {};
    that.progressbarcontainer = options.progressbarcontainer || 'progressbar-container';
    that.urlparams = $.extend({}, options.urlparams || {})

};

/**
 * issue POST to options.urlpath
 * 
 * @param {boolean} force - true if the POST is to overwrite data in the server
 */
BackgroundPostDataManager.prototype.post = function(force) {
    var that = this;

    var form_data = that.get_postdata();
    var urlparams = $.extend({}, that.urlparams, {force: force})
    var url = that.urlpath + '?' + $.param(urlparams)

    $.ajax({
        type: 'POST',
        url: url,
        data: form_data,
        contentType: false,
        cache: false,
        processData: false,
        async: true,
        success: function(data) {that._resp(data)},
        error: function() {
            alert('Unexpected error');
        }
    });

    // caller wants something done after the ajax POST
    that.afterposthook();
};

/**
 * process response from server
 * 
 * @param {BackgroundPostDataManager~ResponseData} data 
 */
BackgroundPostDataManager.prototype._resp = function(data) {
    var that = this;

    window.console && console.log(data);
    if (data.success) {
        // show we're doing something and start updating progress
        $('#' + that.progressbarcontainer).after('<div id="progressbar"><div class="progress-label">Initializing...</div></div>');
        var status_url = data.location;
        var current = data.current;
        var total = data.total;
        var percent = current * 100 / total;
        var progressbar = $('#progressbar'),
            progressLabel = $('.progress-label');
        progressbar.progressbar({
            value: percent,
            // progressLabel needs style - see https://jqueryui.com/progressbar/#label
            change: function () {
                progressLabel.text( progressbar.progressbar( 'value') + '%' )
            },
            complete: function () {
                progressLabel.text( 'Complete!' )
                // caller wants something done after the completion of task
                that.aftersuccesshook();
            }
        });
        that._update_progress(status_url, progressbar);
    } else {
        window.console && console.log('FAILURE: ' + data.cause);
        // if overwrite requested, force the overwrite
        if (data.confirm) {
            $("<div>"+data.cause+"</div>").dialog({
                dialogClass: 'no-titlebar',
                height: "auto",
                modal: true,
                buttons: [
                    {   text:  'Cancel',
                        click: function() {
                            $( this ).dialog('destroy');
                        }
                    },{ text:  'Overwrite',
                        click: function(){
                            that.post(true);
                            $( this ).dialog('destroy');
                        }
                    }
                ],
            });
        } else {
            $("<div>Error Occurred: "+data.cause+"</div>").dialog({
                dialogClass: 'no-titlebar',
                height: "auto",
                buttons: [
                    {   text:  'OK',
                        click: function(){
                            $( this ).dialog('destroy');
                        }
                    }
                ],
            });
        };
    };
};

/**
 * get latest processing status
 * 
 * @param {string} status_url 
 * @param {progressbar} jqueryui progressbar widget
 */
BackgroundPostDataManager.prototype._update_progress = function(status_url, progressbar) {
    var that = this;

    // send GET request to status URL
    $.getJSON(status_url, function(data) {
        // update UI
        var percent = parseInt(data.current * 100 / data.total);

        progressbar.progressbar({value:percent});

        // when we're done
        if (data.state != 'PENDING' && data.state != 'PROGRESS') {
            if (data.state == 'SUCCESS' && data.cause == '') {
                // we're done, remove progress bar and redirect if necessary
                $('#progressbar').progressbar('destroy');
                $('#progressbar').remove();
                if (data.redirect){
                    window.location.replace(data.redirect);
                } else {
                    location.reload();
                };
            }
            else {
                // something unexpected happened
                $("<div>Error Occurred: " + data.cause + "</div>").dialog({
                    dialogClass: 'no-titlebar',
                    height: "auto",
                    buttons: [
                        {   text:  'OK',
                            click: function(){
                                $( this ).dialog('destroy');
                                location.reload();
                            }
                        }
                    ],
                });
            }
        }
        else {
            // rerun in 0.5 seconds
            setTimeout(function() {
                that._update_progress(status_url, progressbar);
            }, 500);
        }
    });
};

/**
 * response which comes back from server when posting data
 * 
 * @typedef {Object} BackgroundPostDataManager~ResponseData
 * @property {boolean} success - true if successful
 * @property {string} redirect - if success, web page for redirect
 * @property {boolean} confirm - if overwrite would occur, true brings up confirmation dialog
 * @property {string} cause - if not success and and not confirm, cause of failure
 * @property {string} location - if success, location to retrieve status from
 * @property {number} current - if success, current amount of completion, out of total
 * @property {number} total - if success, total amount for completion
*/

/**
 * return data to be sent with POST
 *
 * @callback BackgroundPostDataManager~PostData
 * @returns {object} data to be put into the $.ajax data parameter
 */

/**
 * callback after POST
 *
 * @callback BackgroundPostDataManager~AfterPost
 * @returns null
 */
