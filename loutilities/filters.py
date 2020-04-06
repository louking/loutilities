###########################################################################################
#   filters - filters which work with tables-assets/static/filters.css
#
#       Date            Author          Reason
#       ----            ------          ------
#       06/30/19        Lou King        Create
#
#   Copyright 2019 Lou King.  All rights reserved
###########################################################################################
'''
filters - filters which work with tables-assets/static/filters.css

Usage::

    filters = filtercontainerdiv()
    filters += filterdiv('filter1-id', 'Filter 1 Label')
    filters += filterdiv('filter2-id', 'Filter 2 Label')

        :

    yadcf_options = [
        yadcffilter(colnum, 'filter1-id', uselist=True, placeholder='Select filter 1')
    ]

    example = CrudApi(
            :
        pretablehtml = filters,
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

def filtercontainerdiv():
    '''
    build div for filter container
    :return: dominate div
    '''
    return div(_class='external-filter filter-container')

def yadcfoption(colselector, filterid, filtertype, placeholder=None, width=None, date_format='yyyy-mm-dd'):
    '''
    return yadcf option entry for filter

    :param colselector: datatables column selector (see https://datatables.net/reference/type/column-selector)
    :param filterid: html id of filter container, specified in filterdiv()
    :param filtertype: one of 'select', 'multi_select', 'range_date'
    :param placeholder: (for select2) placeholder for empty filter
    :param width: (for select2) css value for width of filter container
    :param date_format: (for range_date) format for date, default 'yyyy-mm-dd'
    :return: yadcf option for inclusion in yadcf option array
    '''
    option = {
        'column_selector': colselector,
        'filter_container_id': filterid,
        'filter_type': filtertype,
    }

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

    elif filtertype == 'range_date':
        option['date_format'] = date_format

    else:
        raise ParameterError('filtertype \'{}\' not handled yet'.format(filtertype))

    return option