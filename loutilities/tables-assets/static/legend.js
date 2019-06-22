// adapted from https://stackoverflow.com/questions/48313985/show-legend-using-jquery
function create_legend(tableid, legend_data) {
    $.each(legend_data, function(index, legend) {
        $('#'+tableid).append('<tr><td>'+legend.label+'</td><td class="legend-cell '+legend.class+'"></td></tr>')
    });
}
function create_legend_header(tableid, text) {
    $('#'+tableid).append('<tr><td class="legend-header" colspan="2">'+text+'</td></tr>');
}