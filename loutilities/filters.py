'''
filters - filters which work with tables-assets/static/filters.css

Usage::

    filters = filtercontainerdiv()
    filters += filterdiv('filter1-id', 'Filter 1 Label')
    filters += filterdiv('filter2-id', 'Filter 2 Label')

        :

    yadcf_options = [
        yadcfoption(colnum, 'filter1-id', 'multi_select', uselist=True, placeholder='Select filter 1')
    ]

    example = CrudApi(
            :
        pretablehtml = filters.render(),
            :
        yadcfoptions = yadcf_options,
    )
'''

from dominate.tags import div, span

class ParameterError(Exception):
    '''
    raised if unknown or bad parameters seen
    '''

def filterdiv(id, label):
    '''
    build div with spans for label, filter

    :param id: html id of filter container, specified in filterdiv()
    :param label: label to display to the left of the filter
    :return: dominate div
    '''
    return div(
        span(label, _class='label'),
        span(id=id, _class='filter'),
        _class='filter-item',
    )

def filtercontainerdiv(**kwargs):
    '''
    build div for filter container

    :param kwargs: optional div() keyword arguments
    :return: dominate div
    '''
    return div(_class='external-filter filter-container', **kwargs)

def yadcfoption(colselector, filterid, filtertype, placeholder=None, width=None, date_format='yyyy-mm-dd',
                filter_match_mode='contains', **kwargs):
    '''
    return yadcf option entry for filter

    :param colselector: datatables column selector (see https://datatables.net/reference/type/column-selector)
    :param filterid: html id of filter container, specified in filterdiv()
    :param filtertype: see https://github.com/vedmack/yadcf/blob/master/src/jquery.dataTables.yadcf.js
    :param placeholder: (for select2) placeholder for empty filter
    :param width: (for select2) css value for width of filter container
    :param date_format: (for range_date) format for date, default 'yyyy-mm-dd'
    :param filter_match_mode: one of 'contains', 'exact', 'startsWith', default 'contains'
    :param kwargs: other keyword arguments for yadcf column options
    :return: yadcf option for inclusion in yadcf option array
    '''
    option = {
        'column_selector': colselector,
        'filter_container_id': filterid,
        'filter_type': filtertype,
        'filter_match_mode': filter_match_mode,
        'date_format': date_format,
    }
    option.update(**kwargs)

    if filtertype in ['select', 'multi_select']:
        option['select_type'] = 'select2'
        option['filter_reset_button_text'] = False

        option['select_type_options'] = {
            'allowClear': True,  # show 'x' (remove) next to selection inside the select itself
        }

        if placeholder:
            option['filter_default_label'] = placeholder
            # this is needed to set the id for filter Storage areas
            option['select_type_options']['placeholder'] = {
                'id': -1,
                'text': placeholder
            }

        if width:
            option['select_type_options']['width'] = width

        if filtertype == 'multi_select':
            option['text_data_delimiter'] = ', ',

    return option