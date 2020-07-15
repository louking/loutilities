'''
decorators - decorators to help with flask applications
'''

# standard
from datetime import timedelta
from functools import update_wrapper

# pypi
from flask import make_response, request, current_app

def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    '''
    crossdomain decorator (from https://web.archive.org/web/20190128010149/http://flask.pocoo.org/snippets/56/)

    :param methods: Optionally a list of methods that are allowed for this view. If not provided it will allow all methods that are implemented.
    :param headers: Optionally a list of headers that are allowed for this request.
    :param origin: '*' to allow all origins, otherwise a string with a URL or a list of URLs that might access the resource.
    :param max_age: The number of seconds as integer or timedelta object for which the preflighted request is valid.
    :param attach_to_all: True if the decorator should add the access control headers to all HTTP methods or False if it should only add them to OPTIONS responses.
    :param automatic_options: If enabled the decorator will use the default Flask OPTIONS response and attach the headers there, otherwise the view function will be called to generate an appropriate response.
    '''
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator