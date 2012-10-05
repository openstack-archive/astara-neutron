# Copyright (c) 2012 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# DreamHost Quantum Extensions
# Copyright 2012 New Dream Network, LLC (DreamHost)
# @author: Murali Raju, New Dream Network, LLC (DreamHost)
# @author: Mark Mcclain, New Dream Network, LLC (DreamHost)

from datetime import datetime
import netaddr
import re

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import validates


from quantum.api.v2 import attributes
from quantum.common import utils
from quantum.db import model_base
from quantum.db import models_v2
from quantum.openstack.common import timeutils


# DreamHost PortFoward, Firewall(FilterRule), AddressBook models as
# Quantum extensions
class PortForward(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a PortForward extension"""

    name = sa.Column(sa.String(255))
    protocol = sa.Column(sa.String(4), nullable=False)
    public_port = sa.Column(sa.Integer, nullable=False)
    instance_id = sa.Column(sa.String(36), nullable=False)
    private_port = sa.Column(sa.Integer, nullable=True)
    port_id = sa.Column(
              sa.String(36), sa.ForeignKey('ports.id',
                             ondelete="CASCADE"),
              nullable=True)

    #PortForward Model Validators using sqlalchamey simple validators

    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp', 'icmp')
        assert len(protocol) <= 4
        return protocol

    @validates('public_port')
    def validate_public_port(self, key, public_port):
        public_port = int(public_port)
        assert public_port >= 0 and public_port <= 65536
        return public_port

    @validates('instance_id')
    def validate_instance_id(self, key, instance_id):
        retype = type(re.compile(attributes.UUID_PATTERN))
        assert isinstance(re.compile(instance_id), retype)
        assert len(instance_id) <= 36
        return instance_id

    @validates('private_port')
    def validate_private_port(self, key, private_port):
        private_port = int(private_port)
        assert private_port >= 0 and private_port <= 65536
        return private_port

    @validates('port_id')
    def validate_port_id(self, key, port_id):
        retype = type(re.compile(attributes.UUID_PATTERN))
        assert isinstance(re.compile(port_id), retype)
        assert len(port_id) <= 36
        return port_id


class AddressBookEntry(model_base.BASEV2, models_v2.HasId,
                       models_v2.HasTenant):
    """Represents (part of) an AddressBook extension"""

    '''[murraju] __tablename__ seems to be needed for plural of models ending
    in 'y' for Quantum DB migrations'''
    __tablename__ = 'addressbookentries'

    name = sa.Column(sa.String(255))
    group_id = sa.Column(
        sa.String(36),
        sa.ForeignKey('addressbookgroups.id', ondelete="CASCADE"),
        nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)

    #AddressBookEntry Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    #def validate_group_id(self, key, group_id):
    #    retype = type(re.compile(attributes.UUID_PATTERN))
    #    assert isinstance(re.compile(group_id), retype)
    #    assert len(group_id) <= 36
    #    return group_id

    @validates('cidr')
    def validate_public_port(self, key, cidr):
        assert netaddr.IPNetwork(cidr)
        assert len(cidr) <= 64
        return cidr


class AddressBookGroup(model_base.BASEV2, models_v2.HasId,
                       models_v2.HasTenant):
    """Represents (part of) an AddressBook extension"""

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    book_id = sa.Column(
        sa.String(36),
        sa.ForeignKey('addressbooks.id', ondelete="CASCADE"),
        nullable=False)
    entries = orm.relationship(AddressBookEntry, backref='groups',
                               lazy='dynamic')

    #AddressBookGroup Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    @validates('book_id')
    def validate_book_id(self, key, book_id):
        retype = type(re.compile(attributes.UUID_PATTERN))
        assert isinstance(re.compile(book_id), retype)
        assert len(book_id) <= 36
        return book_id


class AddressBook(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents (part of) an AddressBook extension"""

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    groups = orm.relationship(AddressBookGroup, backref='book', lazy='dynamic')

    #AddressBook Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name


class FilterRule(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a FilterRule extension"""

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
    def validate_action(self, key, action):
        assert isinstance(action, basestring)
        assert len(action) <= 6
        return action

    @validates('ip_version')
    def validate_ip_version(self, key, ip_version):
        ip_version = int(ip_version)
        assert ip_version is None or isinstance(ip_version, int)
        return ip_version

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp', 'icmp')
        assert len(protocol) <= 4
        return protocol

    @validates('source_alias')
    def validate_source_alias(self, key, source_alias):
        retype = type(re.compile(attributes.UUID_PATTERN))
        assert isinstance(re.compile(source_alias), retype)
        assert len(source_alias) <= 36
        return source_alias

    @validates('source_port')
    def validate_source_port(self, key, source_port):
        source_port = int(source_port)
        assert source_port >= 0 and source_port <= 65536
        return source_port

    @validates('destination_alias')
    def validate_destination_alias(self, key, destination_alias):
        retype = type(re.compile(attributes.UUID_PATTERN))
        assert isinstance(re.compile(destination_alias), retype)
        assert len(destination_alias) <= 36
        return destination_alias

    @validates('destination_port')
    def validate_destination_port(self, key, destination_port):
        destination_port = int(destination_port)
        assert destination_port >= 0 and destination_port <= 65536
        return destination_port

    @validates('created_at')
    def validate_created_at(self, key, created_at):
        assert isinstance(created_at, datetime)
        return created_at


class PortAlias(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """A PortAlias Model used by Horizon. There is no
    need for a port alias extension and this is merely
    to satisfy a Horizon need to store alias information
    """
    __tablename__ = 'portaliases'

    name = sa.Column(sa.String(255))
    protocol = sa.Column(sa.String(4), nullable=False)
    port = sa.Column(sa.Integer, nullable=True)

    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp', 'icmp')
        assert len(protocol) <= 4
        return protocol

    @validates('port')
    def validate_port(self, key, port):
        port = int(port)
        assert port >= 0 and port <= 65536
        return port
