# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright 2011 Nicira Networks, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
# @author: Somik Behera, Nicira Networks, Inc.
# @author: Brad Hall, Nicira Networks, Inc.
# @author: Dan Wendlandt, Nicira Networks, Inc.
# @author: Salvatore Orlando, Citrix Systems

import sqlalchemy as sa
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy import orm
from sqlalchemy.orm import validates


from quantum.api import api_common as common
from quantum.db import model_base
from quantum.db import models_v2 as models
from quantum.openstack.common import timeutils

from datetime import datetime

BASE = model_base.BASE


#DreamHost PortFoward, Firewall(FilterRule), AddressBook models as
#Quantum extensions
class PortForward(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'portfowards'

    name = sa.Column(sa.String(255))
    public_port = sa.Column(sa.Integer, nullable=False)
    instance_id = sa.Column(sa.String(36), nullable=False)
    private_port = sa.Column(sa.Integer, nullable=True)
    # Quantum port address are stored in ipallocation which are internally
    # referred to as fixed_id, thus the name below.
    # XXX can we add a docsting to this model that explains how fixed_id is
    # used?
    fixed_id = sa.Column(
        sa.String(36), sa.ForeignKey('ipallocations.id', ondelete="CASCADE"),
        nullable=True)
    op_status = Column(String(16))

    #PortForward Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert type(name) is str
        assert len(name) <= 255
        return name

    @validates('public_port')
    def validate_public_port(self, key, public_port):
        assert type(public_port) is int
        return public_port

    @validates('instance_id')
    def validate_instance_id(self, key, instance_id):
        assert type(instance_id) is str
        assert len(instance_id) <= 36
        return instance_id

    @validates('private_port')
    def validate_private_port(self, key, private_port):
        assert type(private_port) is int
        return private_port

    @validates('fixed_id')
    def validate_fixed_id(self, key, fixed_id):
        assert type(fixed_id) is str
        assert len(fixed_id) <= 36
        return fixed_id


class AddressBookEntry(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'addressbookentries'

    group_id = sa.Column(sa.String(36), sa.ForeignKey('addressbookgroups.id'),
        nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)

    #AddressBookEntry Model Validators using sqlalchamey simple validators
    @validates('group_id')
    def validate_name(self, key, group_id):
        assert type(group_id) is str
        assert len(group_id) <= 36
        return group_id

    @validates('cidr')
    def validate_public_port(self, key, cidr):
        assert type(cidr) is str
        assert len(cidr) <= 64
        return cidr


class AddressBookGroup(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'addressbookgroups'

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    table_id = sa.Column(sa.String(36), sa.ForeignKey('addressbooks.id'),
        nullable=False)
    entries = orm.relationship(AddressBookEntry, backref='groups')

    #AddressBookGroup Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert type(name) is str
        assert len(name) <= 255
        return name

    @validates('table_id')
    def validate_public_port(self, key, table_id):
        assert type(table_id) is str
        assert len(table_id) <= 36
        return table_id

    @validates('entries')
    def validate_entry(self, key, entries):
        assert entries.group_id is None
        return entries


class AddressBook(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'addressbooks'

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    groups = orm.relationship(AddressBookGroup, backref='book')

    #AddressBook Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert type(name) is str
        assert len(name) <= 255
        return name

    @validates('table_id')
    def validate_public_port(self, key, table_id):
        assert type(table_id) is str
        assert len(table_id) <= 36
        return table_id


class FilterRule(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'filterrules'

    action = sa.Column(sa.String(6), nullable=False, primary_key=True)
    ip_version = sa.Column(sa.Integer, nullable=True)
    protocol = sa.Column(sa.String(4), nullable=False)
    source_alias = sa.Column(sa.String(36),
        sa.ForeignKey('addressbookentries.id'),
        nullable=False)
    source_port = sa.Column(sa.Integer, nullable=True)
    destination_alias = sa.Column(sa.String(36),
        sa.ForeignKey('addressbookentries.id'),
        nullable=False)
    destination_port = sa.Column(sa.Integer, nullable=True)
    created_at = sa.Column(sa.DateTime, default=timeutils.utcnow,
         nullable=False)

    #FilterRule Model Validators using sqlalchamey simple validators
    @validates('action')
    def validate_name(self, key, action):
        assert type(action) is str
        assert len(action) <= 6
        return action

    @validates('ip_version')
    def validate_ip_version(self, key, ip_version):
        assert type(ip_version) is int
        return ip_version

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert type(protocol) is str
        assert len(protocol) <= 4
        return protocol

    @validates('source_alias')
    def validate_source_alias(self, key, source_alias):
        assert type(source_alias) is str
        assert len(source_alias) <= 36
        return source_alias

    @validates('source_port')
    def validate_source_port(self, key, source_port):
        assert type(source_port) is int
        return source_port

    @validates('destination_alias')
    def validate_destination_alias(self, key, destination_alias):
        assert type(destination_alias) is str
        assert len(destination_alias) <= 36
        return destination_alias

    @validates('destination_port')
    def validate_destination_port(self, key, destination_port):
        assert type(destination_port) is str
        assert len(destination_port) <= 36
        return destination_port

    @validates('created_at')
    def validate_created_at(self, key, created_at):
        assert type(created_at) is datetime
        return created_at
