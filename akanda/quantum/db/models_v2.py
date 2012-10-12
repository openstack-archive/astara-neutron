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

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import validates


from quantum.db import model_base
from quantum.db import models_v2
from quantum.openstack.common import timeutils


def validate_port_number(port):
    """Ensures the port number is within the valid range.
    """
    assert 0 <= port <= 65536


class PortForward(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a PortForward extension"""

    name = sa.Column(sa.String(255))
    protocol = sa.Column(sa.String(4), nullable=False)
    public_port = sa.Column(sa.Integer, nullable=False)
    port_id = sa.Column(
        sa.String(36),
        sa.ForeignKey('ports.id', ondelete="CASCADE"),
        nullable=True)
    private_port = sa.Column(sa.Integer, nullable=True)
    port = orm.relationship(models_v2.Port,
                             backref=orm.backref('forwards',
                                                 cascade='all,delete'))

    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp')
        return protocol

    @validates('public_port')
    def validate_public_port(self, key, public_port):
        public_port = int(public_port)
        validate_port_number(public_port)
        return public_port

    @validates('private_port')
    def validate_private_port(self, key, private_port):
        if private_port is not None:
            private_port = int(private_port)
            validate_port_number(private_port)
        return private_port


class AddressGroup(model_base.BASEV2, models_v2.HasId,
                       models_v2.HasTenant):
    """Represents AddressGroup extension"""

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)

    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        name = name[:255]
        return name


class AddressEntry(model_base.BASEV2, models_v2.HasId,
                       models_v2.HasTenant):
    """Represents (part of) an Address extension"""
    __tablename__ = 'addressentries'

    name = sa.Column(sa.String(255))
    group_id = sa.Column(
        sa.String(36),
        sa.ForeignKey('addressgroups.id', ondelete="CASCADE"),
        nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)
    group = orm.relationship(AddressGroup,
                             backref=orm.backref('entries',
                                                 cascade='all,delete'))

    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        name = name[:255]
        return name

    @validates('cidr')
    def validate_cidr(self, key, cidr):
        # this will also normalize the data too
        n = netaddr.IPNetwork(cidr)
        return str(n)


class FilterRule(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a FilterRule extension"""

    action = sa.Column(sa.String(5), default='block')
    ip_version = sa.Column(sa.Integer, nullable=True)
    protocol = sa.Column(sa.String(5), default='', nullable=False)
    source_id = sa.Column(
            sa.String(36),
            sa.ForeignKey('addressgroups.id', ondelete="CASCADE"),
            nullable=True)
    source_port = sa.Column(sa.Integer, nullable=True)
    destination_id = sa.Column(
            sa.String(36),
            sa.ForeignKey('addressgroups.id', ondelete="CASCADE"),
            nullable=True)
    destination_port = sa.Column(sa.Integer, nullable=True)
    created_at = sa.Column(sa.DateTime, default=timeutils.utcnow,
                           nullable=False)
    source = orm.relationship(
        AddressGroup,
        backref='rules_as_source',
        primaryjoin="AddressGroup.id==FilterRule.source_id")
    destination = orm.relationship(
        AddressGroup,
        backref='rules_as_destination',
        primaryjoin="AddressGroup.id==FilterRule.destination_id")

    @validates('action')
    def validate_action(self, key, action):
        assert isinstance(action, basestring)
        action = action[:5]
        assert action in ('pass', 'block')
        return action

    @validates('ip_version')
    def validate_ip_version(self, key, ip_version):
        if not ip_version is None:
            ip_version = int(ip_version)
            assert ip_version in (4, 6)
        return ip_version

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp', 'icmp', 'imcp6')
        return protocol

    @validates('source_port')
    def validate_source_port(self, key, source_port):
        if source_port is not None:
            source_port = int(source_port)
            validate_port_number(source_port)
        return source_port

    @validates('destination_port')
    def validate_destination_port(self, key, destination_port):
        if destination_port is not None:
            destination_port = int(destination_port)
            validate_port_number(destination_port)
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
        name = name[:255]
        return name

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp')
        return protocol

    @validates('port')
    def validate_port(self, key, port):
        port = int(port)
        validate_port_number(port)
        return port
