###########################################################################################
# blueprints - blueprint helpers
#
#       Date            Author          Reason
#       ----            ------          ------
#       07/21/18        Lou King        Create
#                                       adapted from https://gist.github.com/mattupstate/9257466
#
#   Copyright 2018 Lou King
#
###########################################################################################
'''
blueprints - blueprint helpers
=================================
'''

#------------------------------------------------------------------
def add_url_rules(bp, cls, decorator=None, decorator_args=[]):
#------------------------------------------------------------------
    '''
    add url rules to bp for class cls

    cls may define the following class attribute
        url_rules   dict {endpoint: options, ...} 
            endpoint    the endpoint for the registered URL rule
            options     tuple (url_rule[, methods[, defaults]])
                url_rule    the URL rule as string
                methods     tuple of supported methods, e.g. 'GET', 'POST'
                defaults    optional dict with defaults for other rules with the same endpoint
                            see http://werkzeug.pocoo.org/docs/0.14/routing/#werkzeug.routing.Rule
    '''
    for endpoint, options in cls.url_rules.iteritems():
        url_rule = options
        methods = ('GET',)
        defaults = {}
        if len(options) == 2:
            url_rule, methods = options
        elif len(options) == 3:
            url_rule, methods, defaults = options

        # decorator may be specified. 
        # see http://flask.pocoo.org/docs/0.12/views/#decorating-views,
        # http://scottlobdell.me/2015/04/decorators-arguments-python/
        if not decorator:
            view_func = cls.as_view(endpoint)
        else:
            view_func = decorator(*decorator_args)(cls.as_view(endpoint))
        
        # add url rule
        bp.add_url_rule(url_rule, endpoint=endpoint, methods=methods,
                        defaults=defaults, view_func=view_func)

#------------------------------------------------------------------
def list_routes(app):
#------------------------------------------------------------------
    '''
    debug to list routes for app
    '''
    # adapted from http://flask.pocoo.org/snippets/117/
    import urllib
    from flask import url_for
    output = []
    for rule in app.url_map.iter_rules():

        options = {}
        for arg in rule.arguments:
            options[arg] = "[{0}]".format(arg)

        methods = ','.join(rule.methods)
        url = url_for(rule.endpoint, **options)
        line = urllib.unquote("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
        output.append(line)
    
    for line in sorted(output):
        print line

