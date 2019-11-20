# adapted from https://gist.github.com/mattupstate/9257466

from flask import Flask, Blueprint
from flask.views import MethodView


class ApiResource(MethodView):
    endpoint = None
    url_prefix = None
    url_rules = {}

    @classmethod
    def as_blueprint(cls, name=None):
        name = name or cls.endpoint
        bp = Blueprint(name, cls.__module__, url_prefix=cls.url_prefix)
        for endpoint, options in cls.url_rules.items():
            url_rule = options
            methods = ('GET',)
            defaults = {}
            if len(options) == 2:
                url_rule, methods = options
            elif len(options) == 3:
                url_rule, methods, defaults = options
            bp.add_url_rule(url_rule, endpoint=endpoint, methods=methods,
                            defaults=defaults, view_func=cls.as_view(endpoint))
        return bp


class MyResource(ApiResource):
    endpoint = 'my'
    url_prefix = '/hello'
    url_rules = {
        'index': ['', ('GET',), {'id': None}],
        'select': ['/<id>', ('GET',)]
    }

    def get(self, id):
        if id is None:
            return 'hello'
        return id


if __name__ == '__main__':
    app = Flask(__name__)
    app.register_blueprint(MyResource.as_blueprint())

    assert app.url_map.is_endpoint_expecting('my.index')
    assert app.url_map.is_endpoint_expecting('my.select', 'id')

    with app.test_client() as client:
        assert client.get('/hello').data == 'hello'
        assert client.get('/hello/stuff').data == 'stuff'

    print('Tests passed successfully!')