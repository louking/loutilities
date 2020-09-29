/**
 * generate preview link for google doc id
 *
 * @returns {function(*, *, *): (*|string)}
 */
jQuery.fn.dataTable.render.googledoc = function ( label ) {
    return function ( d, type, row ) {
        // only add link if data is present
        if ( d != "" ) {
            return '<a target=_blank href="https://docs.google.com/document/d/' + d + '/preview">' + label + '</a>';
        } else {
            return d;
        }
    };
};