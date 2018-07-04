###########################################################################################
#       Date            Author          Reason
#       ----            ------          ------
#       07/03/18        Lou King        Create
#
#   Copyright 2018 Lou King.  All rights reserved
###########################################################################################
'''
test_sqlalchemy_helpers  -- test sqlalchemy_helpers
=====================================================

'''
# standard
import unittest
from random import randint
from copy import deepcopy

# pypi
from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# home grown
from .models import Base, User, Address, NotUnique, SeveralAttrs
from loutilities.sqlalchemy_helpers import update, getunique, insert_or_update, dbConsistencyError, parameterError

TEST_DB = 'test.db'

class SqlalchemyHelpersTest(unittest.TestCase):

    # executed prior to each test
    def setUp(self):
        """Set up fake database session before all tests."""
        engine = create_engine('sqlite://', echo=False)  # echo=True for debug
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    # executed after each test
    def tearDown(self):
        pass

    ###############
    ### helpers ###
    ###############
    def populate_users(self, numUsers):
        """Create numUsers in fake database."""
        users = []
        addrs = []
        f = Faker()

        for i in range(numUsers):
            user, addr = self.create_user(f.name(), f.address())
            users.append(user)
            addrs.append(addr)

        self.session.add_all(users)
        self.session.commit()

        return users, addrs

    def create_user(self, name, address):
        """Create a fake user."""
        addr = Address(description=address)

        user = User(name=name, address=addr)

        return user, addr

    def populate_notunique(self, numValues):
        f = Faker()
        values = []
        for i in range(numValues):
            value = f.name()
            thisvalue = self.add_notunique(value)
            values.append(thisvalue)

        self.session.add_all(values)
        self.session.commit()

        return values

    def add_notunique(self, value):
        notunique = NotUnique(value=value)
        return notunique

    def populate_severalattrs(self, numRecs):
        f = Faker()
        records = []
        for i in range(numRecs):
            record = self.make_severalattrs()
            records.append(record)
        copyrecords = deepcopy(records)
        self.session.add_all(records)
        self.session.commit()

        return copyrecords

    def make_severalattrs(self):
        f = Faker()
        record = SeveralAttrs(intAttr1=randint(25, 42),
                              strAttr2=f.name(),
                              strAttr3=f.ssn(),
                              boolAttr4=bool(randint(0,1) == 1),
                              dateAttr5=f.date_time_this_decade()
            )
        return record

    ###############
    #### tests ####
    ###############

    def test_getunique_single(self):
        users, addrs = self.populate_users(3)

        thisuser = getunique(self.session, User, name=users[1].name)

        self.assertEqual(thisuser.name, users[1].name)

    def test_getunique_multiple(self):

        values = self.populate_notunique(3)
        notunique = self.add_notunique(values[1].value)
        self.session.add(notunique)
        self.session.commit()

        errormsg = ''
        try:
            thisuser = getunique(self.session, NotUnique, value=values[1].value)
        except dbConsistencyError as e:
            errormsg = str(e)

        self.assertIn('found multiple rows', errormsg)

    def test_getunique_none(self):

        values = self.populate_notunique(3)

        thisuser = getunique(self.session, NotUnique, value='nonesense')

        self.assertEqual(thisuser, None)

    def test_update(self):
        records = self.populate_severalattrs(5)

        oldinst = self.session.query(SeveralAttrs).filter_by(strAttr2=records[3].strAttr2).first()

        f = Faker()
        newattr3 = f.name()
        newattr5 = f.date_time_this_decade()
        newinst = SeveralAttrs(intAttr1=oldinst.intAttr1,
                               strAttr2=oldinst.strAttr2,
                               strAttr3=newattr3,
                               boolAttr4=oldinst.boolAttr4,
                               dateAttr5=newattr5
                )
        updated = update(self.session, SeveralAttrs, oldinst, newinst, skipcolumns=['id'])
        self.session.commit()

        self.assertEqual(updated, True)

        # check all but id field and sqlalchemy instance state field
        currinst = self.session.query(SeveralAttrs).filter_by(strAttr2=records[3].strAttr2).first()
        del currinst.id
        del currinst._sa_instance_state
        del newinst._sa_instance_state
        self.assertEquals(newinst.__dict__, currinst.__dict__)

    def test_insert_or_update_insert(self):
        oldrecords = self.populate_severalattrs(5)

        record = self.make_severalattrs()
        updated = insert_or_update(self.session, SeveralAttrs, record, skipcolumns=['id'], strAttr2=record.strAttr2)

        self.assertEqual(updated, True)

        newrecords = self.session.query(SeveralAttrs).all()
        self.assertEqual(len(newrecords), 6)

    def test_insert_or_update_update(self):
        oldrecords = self.populate_severalattrs(5)
        oldrecord = oldrecords[3]

        record = self.make_severalattrs()
        newinst = deepcopy(oldrecord)
        newinst.intAttr1 = record.intAttr1
        newinst.strAttr3 = record.strAttr3

        updated = insert_or_update(self.session, SeveralAttrs, newinst, skipcolumns=['id'], strAttr2=oldrecord.strAttr2)

        self.assertEqual(updated, True)

        newrecords = self.session.query(SeveralAttrs).all()
        self.assertEqual(len(newrecords), 5)

        currinst = self.session.query(SeveralAttrs).filter_by(strAttr2=oldrecord.strAttr2).first()
        del currinst.id
        del currinst._sa_instance_state
        del newinst._sa_instance_state
        self.assertEquals(newinst.__dict__, currinst.__dict__)
