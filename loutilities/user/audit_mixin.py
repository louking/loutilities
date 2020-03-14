# from https://gist.github.com/techniq/5174410
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr
from flask_security import current_user


class AuditMixin(object):
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # @declared_attr
    # def created_by_id(cls):
    #     return Column(Integer,
    #         ForeignKey('user.id', name='fk_%s_created_by_id' % cls.__name__, use_alter=True),
    #         # nullable=False,
    #         default=_current_user_id_or_none
    #     )
    #
    # @declared_attr
    # def created_by(cls):
    #     return relationship(
    #         'User',
    #         primaryjoin='User.id == %s.created_by_id' % cls.__name__,
    #         remote_side='User.id'
    #     )
    #
    # @declared_attr
    # def updated_by_id(cls):
    #     return Column(Integer,
    #         ForeignKey('user.id', name='fk_%s_updated_by_id' % cls.__name__, use_alter=True),
    #         # nullable=False,
    #         default=_current_user_id_or_none,
    #         onupdate=_current_user_id_or_none
    #     )
    #
    # @declared_attr
    # def updated_by(cls):
    #     return relationship(
    #         'User',
    #         primaryjoin='User.id == %s.updated_by_id' % cls.__name__,
    #         remote_side='User.id'
    #     )


def _current_user_id_or_none():
    try:
        return current_user.id
    except:
        return None