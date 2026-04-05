###########################################################################################
#       Date            Author          Reason
#       ----            ------          ------
#       04/05/26        Lou King        Create
#
#   Copyright 2026 Lou King.  All rights reserved
###########################################################################################
'''
test_user_tables - tests for loutilities.user.tables

Unit tests cover the classes that can be exercised without a live Flask-SQLAlchemy
app or flask-security session.  Heavier integration tests that require the Interest
model, LocalInterest model, and an authenticated current_user are collected but
skipped with an explanatory message.
'''
# standard
import unittest
from unittest.mock import MagicMock, patch

# pypi
from flask import Flask, g
from sqlalchemy import Column, Integer, Enum as SaEnum
from sqlalchemy.orm import declarative_base

# homegrown
from loutilities.user import tables as user_tables


# ===========================================================================
# DbPermissionsMethodViewApi — lightweight MethodView with permission check
# ===========================================================================

class TestDbPermissionsMethodViewApiInit(unittest.TestCase):
    """__init__ stores all kwargs as attributes with safe defaults."""

    def test_attributes_stored(self):
        app = Flask(__name__)
        api = user_tables.DbPermissionsMethodViewApi(
            app=app,
            db=MagicMock(),
            roles_accepted=['admin'],
            endpoint='testapi',
            rule='/test',
            methods=['GET'],
        )
        self.assertEqual(api.roles_accepted, ['admin'])
        self.assertEqual(api.endpoint, 'testapi')
        self.assertEqual(api.rule, '/test')
        self.assertEqual(api.methods, ['GET'])

    def test_defaults_are_none(self):
        api = user_tables.DbPermissionsMethodViewApi()
        self.assertIsNone(api.app)
        self.assertIsNone(api.roles_accepted)
        self.assertIsNone(api.endpoint)


class TestDbPermissionsMethodViewApiPermission(unittest.TestCase):
    """
    permission() is purely conditional logic: check g.interest → Interest table
    → current_user.is_authenticated → interest in current_user.interests → role.
    All external calls are mocked so no live DB or flask-security session is needed.
    """

    def setUp(self):
        self.app = Flask(__name__)
        self.api = user_tables.DbPermissionsMethodViewApi(
            app=self.app,
            roles_accepted=['admin'],
        )

    def _run(self, interest_slug, mock_interest, mock_user):
        """Execute permission() inside a request context with g.interest set."""
        with self.app.test_request_context('/'):
            g.interest = interest_slug
            with patch.object(user_tables.Interest, 'query') as mock_q, \
                 patch('loutilities.user.tables.current_user', mock_user):
                mock_q.filter_by.return_value.one_or_none.return_value = mock_interest
                return self.api.permission()

    def test_granted_authenticated_user_with_role_and_interest(self):
        mock_interest = MagicMock()
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.interests = [mock_interest]
        mock_user.has_role.return_value = True
        self.assertTrue(self._run('myclub', mock_interest, mock_user))

    def test_denied_when_interest_not_found_in_db(self):
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        # Interest.query returns None → no permission
        self.assertFalse(self._run('unknown', None, mock_user))

    def test_denied_when_user_not_authenticated(self):
        mock_interest = MagicMock()
        mock_user = MagicMock()
        mock_user.is_authenticated = False
        self.assertFalse(self._run('myclub', mock_interest, mock_user))

    def test_denied_when_interest_not_in_user_interests(self):
        mock_interest = MagicMock()
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.interests = []     # interest exists in DB but not assigned to user
        self.assertFalse(self._run('myclub', mock_interest, mock_user))

    def test_denied_when_user_lacks_required_role(self):
        mock_interest = MagicMock()
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.interests = [mock_interest]
        mock_user.has_role.return_value = False
        self.assertFalse(self._run('myclub', mock_interest, mock_user))

    def test_granted_first_matching_role_is_enough(self):
        """roles_accepted=['admin','editor']: user has 'editor' → granted."""
        api = user_tables.DbPermissionsMethodViewApi(
            app=self.app,
            roles_accepted=['admin', 'editor'],
        )
        mock_interest = MagicMock()
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        mock_user.interests = [mock_interest]
        mock_user.has_role.side_effect = lambda r: r == 'editor'
        with self.app.test_request_context('/'):
            g.interest = 'myclub'
            with patch.object(user_tables.Interest, 'query') as mock_q, \
                 patch('loutilities.user.tables.current_user', mock_user):
                mock_q.filter_by.return_value.one_or_none.return_value = mock_interest
                self.assertTrue(api.permission())


# ===========================================================================
# AssociationSelect — parameter validation at construction time
# ===========================================================================

class TestAssociationSelectInit(unittest.TestCase):
    """
    __init__ validates that required fields are present and that
    associationfields and selectattrs have the same length.
    The loop that inspects each selectattr.type is also exercised via a
    throwaway declarative model with a real SQLAlchemy Enum column.
    """

    def _mock_attr(self):
        """A mock SQLAlchemy column attribute whose type is NOT an Enum."""
        attr = MagicMock()
        attr.type = MagicMock()   # type() != SaEnum → uses else branch
        attr.class_ = MagicMock()
        attr.key = 'fieldname'
        return attr

    def _valid_kwargs(self, **overrides):
        kwargs = dict(
            tablemodel=MagicMock(),
            associationmodel=MagicMock(),
            associationtablemodelfield='task',
            associationfields=['taskfield'],
            selectattrs=[self._mock_attr()],
            dbfield='fields',
            labelfield='fields',
            formfield='fields',
        )
        kwargs.update(overrides)
        return kwargs

    def test_valid_instantiation_non_enum(self):
        """All required params supplied with a non-Enum selectattr."""
        sel = user_tables.AssociationSelect(**self._valid_kwargs())
        self.assertEqual(sel.dbfield, 'fields')
        self.assertEqual(len(sel.optionlevels), 1)

    def test_missing_associationmodel_raises(self):
        with self.assertRaises(user_tables.ParameterError):
            user_tables.AssociationSelect(**self._valid_kwargs(associationmodel=None))

    def test_missing_associationtablemodelfield_raises(self):
        with self.assertRaises(user_tables.ParameterError):
            user_tables.AssociationSelect(**self._valid_kwargs(associationtablemodelfield=None))

    def test_missing_dbfield_raises(self):
        with self.assertRaises(user_tables.ParameterError):
            user_tables.AssociationSelect(**self._valid_kwargs(dbfield=None))

    def test_mismatched_field_lengths_raises(self):
        """Two associationfields but only one selectattr → length mismatch."""
        kwargs = self._valid_kwargs(
            associationfields=['f1', 'f2'],
            selectattrs=[self._mock_attr()],   # length 1 ≠ 2
        )
        with self.assertRaises(user_tables.ParameterError):
            user_tables.AssociationSelect(**kwargs)

    def test_enum_selectattr_populates_options_and_ids(self):
        """
        When a selectattr has a real SQLAlchemy Enum type, __init__ extracts
        enum values into optionlevels[n]['options'] and matching integer ids.
        """
        TmpBase = declarative_base()

        class TmpModel(TmpBase):
            __tablename__ = 'tmp'
            id = Column(Integer, primary_key=True)
            need = Column(SaEnum('required', 'optional', name='need_enum'))

        sel = user_tables.AssociationSelect(
            tablemodel=MagicMock(),
            associationmodel=MagicMock(),
            associationtablemodelfield='task',
            associationfields=['need'],
            selectattrs=[TmpModel.need],
            dbfield='fields',
            labelfield='fields',
            formfield='fields',
        )
        level = sel.optionlevels[0]
        self.assertIn('options', level)
        self.assertEqual(list(level['options']), ['required', 'optional'])
        self.assertEqual(list(level['ids']), [0, 1])


# ===========================================================================
# Integration tests — skipped, require full Flask-SQLAlchemy + flask-security
# ===========================================================================

@unittest.skip(
    'Requires a Flask-SQLAlchemy app with Interest / LocalInterest tables '
    'created, flask-security current_user authenticated, and g.interest set '
    'to a valid slug.  Cover these in application-level integration tests.'
)
class TestDbCrudApiInterestsRolePermissions(unittest.TestCase):
    """
    All methods depend on Interest.query (flask-security model), g.interest,
    current_user.is_authenticated, and current_user.interests.  The parent
    DbCrudApi.__init__ also requires db, model, app, dbmapping, formmapping,
    and clientcolumns, all wired to a real Flask-SQLAlchemy session.
    """
    def test_permission_granted(self): pass
    def test_permission_denied_wrong_interest(self): pass
    def test_permission_denied_unauthenticated(self): pass
    def test_beforequery_sets_local_interest_id(self): pass
    def test_createrow_stamps_interest_id(self): pass
    def test_local_interest_model_required(self): pass


@unittest.skip(
    'AssociationSelect.get(), set(), and options() all call db.session and '
    'execute model queries.  They need a Flask-SQLAlchemy app with the '
    'association model tables populated.  Cover in application-level tests.'
)
class TestAssociationSelectIntegration(unittest.TestCase):
    """
    get() and set() translate between form values and association model rows.
    options() cross-products Enum values with fieldmodel query results.
    All require a live db.session.
    """
    def test_get_uselist_returns_separator_joined_labels(self): pass
    def test_get_single_returns_label_and_value(self): pass
    def test_set_uselist_creates_association_instances(self): pass
    def test_options_cross_product_enum_with_model_rows(self): pass
    def test_nullable_prepends_none_option(self): pass


@unittest.skip(
    'AssociationCrudApi.updaterow() deletes and re-creates association rows '
    'via db.session.  The parent __init__ chain (AssociationCrudApi → '
    'DbCrudApiInterestsRolePermissions → DbCrudApi) requires the full '
    'Flask-SQLAlchemy + flask-security setup described above.'
)
class TestAssociationCrudApi(unittest.TestCase):
    """
    updaterow() clears assnlistfield, calls super().updaterow(), then
    re-links new association rows to the parent model row.
    """
    def test_updaterow_clears_and_rebuilds_associations(self): pass
    def test_assnlistfield_required(self): pass
    def test_assnmodelfield_required(self): pass


if __name__ == '__main__':
    unittest.main()
