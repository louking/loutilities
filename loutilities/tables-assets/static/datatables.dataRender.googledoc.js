/**
 * generate preview link for google doc id
 *
 * @returns {function(*, *, *): (*|string)}
 */
jQuery.fn.dataTable.render.googledoc = function ( label ) {
    return function ( d, type, row ) {
        var linktext;
        // if label is a function, the text for the link may depend on row information
        if (_.isFunction(label)) {
            linktext = label(row)
        } else {
            linktext = label;
        }
        // only add link if data is present
        if ( d != "" ) {
            return '<a target=_blank href="https://docs.google.com/document/d/' + d + '/preview">' + linktext + '</a>';
        } else {
            return d;
        }
    };
};