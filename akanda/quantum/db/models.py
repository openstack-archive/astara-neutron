import sqlalchemy as sa
from sqlalchemy import orm

from quantum.db import model_base
from quantum.db import models_v2 as models
from quantum.openstack.common import timeutils


class PortForward(model_base.BASEV2, models.HasId, models.HasTenant):
    name = sa.Column(sa.String(255))
    public_port = sa.Column(sa.Integer, nullable=False)
    instance_id = sa.Column(sa.String(36), nullable=False)
    private_port = sa.Column(sa.Integer, nullable=True)
    # Quantum port address are stored in ipallocation which are internally
    # referred to as fixed_id, thus the name below.
    # XXX can we add a docsting to this model that explains how fixed_id is
    # used?
    fixed_id = sa.Column(
        sa.String(36), sa.ForeignKey('ipallocation.id', ondelete="CASCADE"),
        nullable=True)


class AddressBookEntry(model_base.BASEV2, models.HasId, models.HasTenant):
    group_id = sa.Column(sa.String(36), sa.ForeignKey('addressbookgroup.id'),
                         nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)


class AddressBookGroup(model_base.BASEV2, models.HasId, models.HasTenant):
    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    table_id = sa.Column(sa.String(36), sa.ForeignKey('addressbook.id'),
                         nullable=False)
    entries = orm.relationship(AddressBookEntry, backref='groups')


class AddressBook(model_base.BASEV2, models.HasId, models.HasTenant):
    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    groups = orm.relationship(AddressBookGroup, backref='book')


class FilterRule(model_base.BASEV2, models.HasId, models.HasTenant):
    action = sa.Column(sa.String(6), nullable=False, primary_key=True)
    ip_version = sa.Column(sa.Integer, nullable=True)
    protocol = sa.Column(sa.String(4), nullable=False)
    source_alias = sa.Column(sa.String(36),
                             sa.ForeignKey('addressbookentry.id'),
                             nullable=False)
    source_port = sa.Column(sa.Integer, nullable=True)
    destination_alias = sa.Column(sa.String(36),
                                  sa.ForeignKey('addressbookentry.id'),
                                  nullable=False)
    destination_port = sa.Column(sa.Integer, nullable=True)
    created_at = sa.Column(sa.DateTime, default=timeutils.utcnow,
                           nullable=False)
