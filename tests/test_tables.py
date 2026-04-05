'''
test_tables - tests for loutilities.tables
'''
# standard
import unittest

# pypi
from flask import Flask, json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

# homegrown
from loutilities import tables
from .models import User, Address, Base


# ---------------------------------------------------------------------------
# DbWrapper: presents the db.session interface expected by DbCrudApi
# (Flask-SQLAlchemy uses db.session; here we wrap a scoped_session)
# ---------------------------------------------------------------------------
class DbWrapper:
    def __init__(self, session):
        self.session = session


def _make_engine():
    """In-memory SQLite engine with StaticPool so all connections share one DB."""
    return create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )


def _make_scoped_session(engine):
    """Create a scoped session and bind query_property to model classes."""
    Session = scoped_session(sessionmaker(bind=engine))
    # query_property lets Model.query work like Flask-SQLAlchemy
    User.query = Session.query_property()
    Address.query = Session.query_property()
    return Session


# ===========================================================================
# Standalone utility function tests
# ===========================================================================

class TestIsJsonable(unittest.TestCase):
    def test_serializable_types(self):
        self.assertTrue(tables.is_jsonable({'a': 1}))
        self.assertTrue(tables.is_jsonable([1, 2, 3]))
        self.assertTrue(tables.is_jsonable('string'))
        self.assertTrue(tables.is_jsonable(42))
        self.assertTrue(tables.is_jsonable(None))

    def test_non_serializable(self):
        self.assertFalse(tables.is_jsonable({1, 2, 3}))   # set is not JSON-serializable


class TestCopyopts(unittest.TestCase):
    def test_dict(self):
        d = {'a': 1, 'b': [2, 3], 'c': {'d': 4}}
        self.assertEqual(tables.copyopts(d), d)

    def test_list(self):
        lst = [1, 'x', {'y': 2}]
        self.assertEqual(tables.copyopts(lst), lst)

    def test_non_serializable_becomes_str(self):
        result = tables.copyopts({'a': {1, 2}})
        self.assertIsInstance(result['a'], str)

    def test_scalar(self):
        self.assertEqual(tables.copyopts(42), 42)
        self.assertEqual(tables.copyopts('hello'), 'hello')


class TestGetDbattr(unittest.TestCase):
    """get_dbattr traverses using type() at each intermediate level."""

    def test_simple(self):
        class Obj:
            value = 7
        self.assertEqual(tables.get_dbattr(Obj(), 'value'), 7)

    def test_dotted(self):
        # Intermediate traversal uses type(getattr(...)), so inner.value must be a class attribute
        class Inner:
            value = 99
        class Outer:
            inner = Inner()
        self.assertEqual(tables.get_dbattr(Outer(), 'inner.value'), 99)


class TestGetattrdeep(unittest.TestCase):
    def test_simple(self):
        class Obj:
            pass
        obj = Obj()
        obj.name = 'hello'
        self.assertEqual(tables.getattrdeep(obj, 'name'), 'hello')

    def test_dotted(self):
        class Inner:
            pass
        class Outer:
            pass
        inner = Inner()
        inner.val = 42
        outer = Outer()
        outer.inner = inner
        self.assertEqual(tables.getattrdeep(outer, 'inner.val'), 42)


class TestSetattrdeep(unittest.TestCase):
    def test_simple(self):
        class Obj:
            pass
        obj = Obj()
        tables.setattrdeep(obj, 'x', 100)
        self.assertEqual(obj.x, 100)

    def test_dotted(self):
        class Inner:
            pass
        class Outer:
            pass
        inner = Inner()
        outer = Outer()
        outer.inner = inner
        tables.setattrdeep(outer, 'inner.val', 55)
        self.assertEqual(inner.val, 55)


class TestGetRequestAction(unittest.TestCase):
    def test_present(self):
        self.assertEqual(tables.get_request_action({'action': 'create'}), 'create')
        self.assertEqual(tables.get_request_action({'action': 'remove'}), 'remove')

    def test_absent(self):
        self.assertIsNone(tables.get_request_action({}))
        self.assertIsNone(tables.get_request_action({'other': 'x'}))


class TestGetRequestData(unittest.TestCase):
    def test_basic_parse(self):
        form = {
            'data[1][name]': 'Alice',
            'data[1][age]': '30',
            'data[2][name]': 'Bob',
        }
        data = tables.get_request_data(form)
        self.assertEqual(data[1]['name'], 'Alice')
        self.assertEqual(data[1]['age'], '30')
        self.assertEqual(data[2]['name'], 'Bob')

    def test_action_key_ignored(self):
        form = {'action': 'create', 'data[1][name]': 'Test'}
        data = tables.get_request_data(form)
        self.assertNotIn('action', data)

    def test_string_id(self):
        form = {'data[abc][x]': '1'}
        data = tables.get_request_data(form)
        self.assertEqual(data['abc']['x'], '1')


# ===========================================================================
# DataTablesEditor tests
# ===========================================================================

class TestDataTablesEditor(unittest.TestCase):
    def setUp(self):
        class Row:
            pass
        self.Row = Row
        self.dte = tables.DataTablesEditor(
            dbmapping={'name': 'name', 'age': 'age'},
            formmapping={'name': 'name', 'age': 'age'},
        )

    def test_get_response_data_simple(self):
        row = self.Row()
        row.name = 'Alice'
        row.age = 30
        data = self.dte.get_response_data(row)
        self.assertEqual(data['name'], 'Alice')
        self.assertEqual(data['age'], 30)

    def test_set_dbrow_simple(self):
        row = self.Row()
        self.dte.set_dbrow({'name': 'Bob', 'age': '25'}, row)
        self.assertEqual(row.name, 'Bob')
        self.assertEqual(row.age, '25')

    def test_readonly_field_not_written(self):
        dte = tables.DataTablesEditor(
            dbmapping={'name': '__readonly__', 'age': 'age'},
            formmapping={'name': 'name', 'age': 'age'},
        )
        row = self.Row()
        row.name = 'original'
        dte.set_dbrow({'name': 'changed', 'age': '25'}, row)
        self.assertEqual(row.name, 'original')   # skipped because __readonly__

    def test_null2emptystring_get(self):
        dte = tables.DataTablesEditor({'name': 'name'}, {'name': 'name'}, null2emptystring=True)
        row = self.Row()
        row.name = None
        data = dte.get_response_data(row)
        self.assertEqual(data['name'], '')

    def test_skip_formmapping_field(self):
        dte = tables.DataTablesEditor({}, {'name': 'name', 'computed': '__skip__'})
        row = self.Row()
        row.name = 'x'
        data = dte.get_response_data(row)
        self.assertNotIn('computed', data)

    def test_callable_formmapping(self):
        dte = tables.DataTablesEditor({}, {'upper': lambda r: r.name.upper()})
        row = self.Row()
        row.name = 'alice'
        self.assertEqual(dte.get_response_data(row)['upper'], 'ALICE')

    def test_callable_dbmapping(self):
        dte = tables.DataTablesEditor({'name': lambda form: form.get('name', '').strip()}, {})
        row = self.Row()
        dte.set_dbrow({'name': '  Bob  '}, row)
        self.assertEqual(row.name, 'Bob')

    def test_response_hook_called(self):
        calls = []
        def hook(data):
            calls.append(True)
            data['_extra'] = 'added'
        self.dte.set_response_hook(hook)
        row = self.Row()
        row.name = 'Test'
        row.age = 1
        data = self.dte.get_response_data(row)
        self.assertTrue(calls)
        self.assertEqual(data['_extra'], 'added')


# ===========================================================================
# CrudApi abstract method tests
# The base class raises tables.NotImplementedError for open/nexttablerow/close/permission.
# ===========================================================================

class TestCrudApiAbstractMethods(unittest.TestCase):
    def setUp(self):
        # Minimum kwargs to avoid TypeError in __init__ (rule defaults to /endpoint)
        self.api = tables.CrudApi(app=Flask(__name__), endpoint='testapi')

    def test_open_raises(self):
        with self.assertRaises(tables.NotImplementedError):
            self.api.open()

    def test_nexttablerow_raises(self):
        with self.assertRaises(tables.NotImplementedError):
            self.api.nexttablerow()

    def test_close_raises(self):
        with self.assertRaises(tables.NotImplementedError):
            self.api.close()

    def test_permission_raises(self):
        with self.assertRaises(tables.NotImplementedError):
            self.api.permission()


# ===========================================================================
# DbCrudApi integration tests using in-memory SQLite
# ===========================================================================

class TestDbCrudApiIntegration(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True

        self.engine = _make_engine()
        Base.metadata.create_all(self.engine)
        self.Session = _make_scoped_session(self.engine)
        self.db = DbWrapper(self.Session)

        class UserApi(tables.DbCrudApi):
            def permission(self):
                return True

        self.api = UserApi(
            app=self.app,
            endpoint='userapi',
            rule='/users',
            db=self.db,
            model=User,
            dbmapping={'name': 'name'},
            formmapping={'name': 'name'},
            clientcolumns=[
                {'data': 'name', 'name': 'name', 'label': 'Name', '_unique': True}
            ],
        )
        self.api.register()
        self.client = self.app.test_client()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.Session.remove()

    def test_create_returns_row_data(self):
        resp = self.client.post('/users/rest', data={
            'action': 'create',
            'data[0][name]': 'Alice',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn('data', data)
        self.assertEqual(data['data'][0]['name'], 'Alice')

    def test_get_returns_list_of_rows(self):
        self.client.post('/users/rest', data={'action': 'create', 'data[0][name]': 'Bob'})
        resp = self.client.get('/users/rest')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIsInstance(data, list)
        self.assertTrue(any(row.get('name') == 'Bob' for row in data))

    def test_update_row(self):
        # SQLite auto-increment gives the first inserted row id=1
        self.client.post('/users/rest', data={'action': 'create', 'data[0][name]': 'Carol'})
        resp = self.client.put('/users/rest/1', data={
            'action': 'edit',
            'data[1][name]': 'Caroline',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn('data', data)
        self.assertEqual(data['data'][0]['name'], 'Caroline')

    def test_delete_row(self):
        self.client.post('/users/rest', data={'action': 'create', 'data[0][name]': 'Dave'})
        # delete action comes from request.args (formrequest=False)
        resp = self.client.delete('/users/rest/1', query_string={'action': 'remove'})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get('/users/rest')
        data = json.loads(resp.data)
        self.assertFalse(any(row.get('name') == 'Dave' for row in data))

    def test_duplicate_unique_returns_error_json(self):
        """Creating a duplicate unique value returns HTTP 200 with error/fieldErrors."""
        self.client.post('/users/rest', data={'action': 'create', 'data[0][name]': 'Eve'})
        resp = self.client.post('/users/rest', data={'action': 'create', 'data[0][name]': 'Eve'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue('error' in data or 'fieldErrors' in data)


# ===========================================================================
# DbCrudApiRolePermissions tests
# ===========================================================================

def _mock_user(roles):
    class MockUser:
        def __init__(self, r):
            self._roles = r
        def has_role(self, role):
            return role in self._roles
    return MockUser(roles)


class TestDbCrudApiRolePermissions(unittest.TestCase):
    _ep_counter = 0

    def _make_api(self, **extra):
        TestDbCrudApiRolePermissions._ep_counter += 1
        ep = 'roleapi_{}'.format(TestDbCrudApiRolePermissions._ep_counter)

        # Inline subclass: disable auth decorator and expose current_user as property
        class RoleApi(tables.DbCrudApiRolePermissions):
            decorators = []  # bypass auth_required() for unit testing

            @property
            def current_user(self):
                return self._mock_user

        api = RoleApi(
            app=self.app,
            endpoint=ep,
            rule='/' + ep,
            db=self.db,
            model=User,
            dbmapping={'name': 'name'},
            formmapping={'name': 'name'},
            clientcolumns=[{'data': 'name', 'name': 'name', 'label': 'Name'}],
            **extra,
        )
        return api

    def setUp(self):
        self.app = Flask(__name__)
        self.engine = _make_engine()
        Base.metadata.create_all(self.engine)
        self.Session = _make_scoped_session(self.engine)
        self.db = DbWrapper(self.Session)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.Session.remove()

    def test_roles_accepted_grants_permission(self):
        api = self._make_api(roles_accepted=['admin'])
        api._mock_user = _mock_user(['admin'])
        self.assertTrue(api.permission())

    def test_roles_accepted_denies_permission(self):
        api = self._make_api(roles_accepted=['admin'])
        api._mock_user = _mock_user(['user'])
        self.assertFalse(api.permission())

    def test_no_roles_configured_grants_permission(self):
        api = self._make_api()
        api._mock_user = _mock_user([])
        self.assertTrue(api.permission())

    def test_roles_required_all_must_be_present(self):
        api = self._make_api(roles_required=['admin', 'superuser'])
        api._mock_user = _mock_user(['admin'])        # only one role → denied
        self.assertFalse(api.permission())
        api._mock_user = _mock_user(['admin', 'superuser'])   # both → granted
        self.assertTrue(api.permission())

    def test_roles_accepted_and_required_raises(self):
        with self.assertRaises(tables.ParameterError):
            self._make_api(roles_accepted=['admin'], roles_required=['superuser'])

    def test_roles_accepted_string_normalised_to_list(self):
        api = self._make_api(roles_accepted='admin')
        self.assertEqual(api.roles_accepted, ['admin'])

    def test_roles_required_string_normalised_to_list(self):
        api = self._make_api(roles_required='admin')
        self.assertEqual(api.roles_required, ['admin'])


if __name__ == '__main__':
    unittest.main()
