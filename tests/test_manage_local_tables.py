###########################################################################################
#       Date            Author          Reason
#       ----            ------          ------
#       08/13/26        Lou King        Create
#
#   Copyright 2026 Lou King.  All rights reserved
###########################################################################################
'''
test_manage_local_tables - regression tests for loutilities.user.model.ManageLocalTables

Uses a bare Flask app with file-based sqlite databases for both the default bind
(local models) and the 'users' bind (shared User/Interest/Application models), since
this repo's downstream users have hit cross-bind visibility gotchas with :memory:
sqlite under Flask-SQLAlchemy's multi-bind setup.
'''
# standard
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

# pypi
from flask import Flask

# homegrown
from loutilities.user.model import (
    db, Base, Column, Integer,
    User, Interest, Application, ManageLocalTables, LocalUserMixin,
)

APPNAME = 'testapp'


class LocalInterest(Base):
    __tablename__ = 'test_manage_local_tables_localinterest'
    id = Column(Integer, primary_key=True)
    interest_id = Column(Integer)


class LocalUser(LocalUserMixin, Base):
    __tablename__ = 'test_manage_local_tables_localuser'
    id = Column(Integer, primary_key=True)
    interest_id = Column(Integer)


class ManageLocalTablesTest(unittest.TestCase):

    def setUp(self):
        self.localdb_fd, self.localdb_path = tempfile.mkstemp(suffix='.db')
        self.usersdb_fd, self.usersdb_path = tempfile.mkstemp(suffix='.db')

        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///{}'.format(self.localdb_path)
        app.config['SQLALCHEMY_BINDS'] = {'users': 'sqlite:///{}'.format(self.usersdb_path)}
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        self.app = app
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

        self.application = Application(application=APPNAME)
        db.session.add(self.application)
        db.session.commit()

        self.interest = Interest(interest='test-interest', applications=[self.application])
        db.session.add(self.interest)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        os.close(self.localdb_fd)
        os.close(self.usersdb_fd)
        os.unlink(self.localdb_path)
        os.unlink(self.usersdb_path)

    def create_user(self, active):
        user = User(
            email='user-{}@example.com'.format(uuid.uuid4()),
            name='Test User',
            given_name='Test',
            active=active,
            fs_uniquifier=str(uuid.uuid4()),
        )
        db.session.add(user)
        db.session.commit()
        return user

    def test_inactive_user_not_duplicated_on_repeated_update(self):
        # regression test for louking/loutilities#103: an inactive LocalUser row
        # dropped out of the active=True seed filter, so the next update() call
        # couldn't find it and inserted a duplicate row instead of updating it.
        user = self.create_user(active=False)

        mlt = ManageLocalTables(db, APPNAME, LocalUser, LocalInterest, hasuserinterest=True)
        mlt.update()
        mlt.update()

        rows = LocalUser.query.filter_by(user_id=user.id).all()
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].active)

    def test_orphaned_null_interest_rows_do_not_raise_multipleresultsfound(self):
        # regression test for louking/webmodules#44: LocalUser rows left with
        # interest_id=None (e.g. after their Interest was deleted) must not enter
        # the working set, else two such rows for the same user_id collide in the
        # final deactivate query's .one() call.
        user = self.create_user(active=True)

        mlt = ManageLocalTables(db, APPNAME, LocalUser, LocalInterest, hasuserinterest=True)
        mlt.update()

        # simulate two orphaned rows left behind by separate deleted interests
        db.session.add(LocalUser(user_id=user.id, interest_id=None, active=True,
                                  name=user.name, email=user.email, given_name=user.given_name))
        db.session.add(LocalUser(user_id=user.id, interest_id=None, active=True,
                                  name=user.name, email=user.email, given_name=user.given_name))
        db.session.commit()

        # must not raise sqlalchemy.orm.exc.MultipleResultsFound
        mlt.update()

        orphans = LocalUser.query.filter_by(user_id=user.id, interest_id=None).all()
        self.assertEqual(len(orphans), 2)

    def test_update_without_lockfile_does_not_lock(self):
        # default behavior (no lockfile given) must stay unserialized, matching every
        # caller before this parameter existed -- see louking/contracts#578.
        user = self.create_user(active=True)

        with patch('loutilities.user.model.InterProcessLock') as MockLock:
            mlt = ManageLocalTables(db, APPNAME, LocalUser, LocalInterest, hasuserinterest=True)
            mlt.update()

        MockLock.assert_not_called()
        rows = LocalUser.query.filter_by(user_id=user.id).all()
        self.assertEqual(len(rows), 1)

    def test_update_with_lockfile_wraps_work_in_lock(self):
        # regression test for louking/contracts#578: concurrently booting gunicorn
        # workers each independently ran the select-then-insert in
        # _updateuser_byinterest(), so each found no existing row for a new user and
        # inserted its own duplicate. update() must hold a lock around its whole body
        # (interest sync, user sync, and the commit) when given a lockfile.
        user = self.create_user(active=True)
        lockfile = '/tmp/test-loutilities-managelocaltables.lock'
        calls = []

        class RecordingLock:
            def __init__(self, path):
                calls.append(('init', path))
            def __enter__(self):
                calls.append(('enter',))
            def __exit__(self, *exc_info):
                calls.append(('exit',))

        with patch('loutilities.user.model.InterProcessLock', RecordingLock):
            mlt = ManageLocalTables(db, APPNAME, LocalUser, LocalInterest, hasuserinterest=True,
                                     lockfile=lockfile)
            mlt.update()

        self.assertEqual(calls[0], ('init', lockfile))
        self.assertEqual(calls[1], ('enter',))
        self.assertEqual(calls[-1], ('exit',))
        # and the work inside the lock still ran correctly
        rows = LocalUser.query.filter_by(user_id=user.id).all()
        self.assertEqual(len(rows), 1)


if __name__ == '__main__':
    unittest.main()
