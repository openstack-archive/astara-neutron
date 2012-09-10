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
# DreamHost Qauntum Extensions
# Copyright 2012 New Dream Network, LLC (DreamHost)
# @author: Murali Raju, New Dream Network, LLC (DreamHost)
# @author: Mark Mcclain, New Dream Network, LLC (DreamHost)

from datetime import datetime
import logging
import netaddr
import re

import sqlalchemy as sa
from sqlalchemy import Column, String
from sqlalchemy import orm
from sqlalchemy.orm import validates


from quantum.api import api_common as common
from quantum.common import utils
from quantum.db import model_base
from quantum.openstack.common import timeutils


LOG = logging.getLogger(__name__)


class Validator:

    #VALIDATORS
    #Validate private and public port ranges
    '''Consider moving the following to some shared
    attributes class'''

    #Used by type() regex to check if IDs are UUID
    HEX_ELEM = '[0-9A-Fa-f]'
    UUID_PATTERN = '-'.join([HEX_ELEM + '{8}', HEX_ELEM + '{4}',
                             HEX_ELEM + '{4}', HEX_ELEM + '{4}',
                             HEX_ELEM + '{12}'])


class HasTenant(object):
    """Tenant mixin, add to subclasses that have a tenant."""
    # NOTE(jkoelker) tenant_id is just a free form string ;(
    tenant_id = sa.Column(sa.String(255))


class HasId(object):
    """id mixin, add to subclasses that have an id."""
    id = sa.Column(sa.String(36), primary_key=True, default=utils.str_uuid)


class IPAvailabilityRange(model_base.BASEV2):
    """Internal representation of available IPs for Quantum subnets.

    Allocation - first entry from the range will be allocated.
    If the first entry is equal to the last entry then this row
    will be deleted.
    Recycling ips involves appending to existing ranges. This is
    only done if the range is contiguous. If not, the first_ip will be
    the same as the last_ip. When adjacent ips are recycled the ranges
    will be merged.

    """
    allocation_pool_id = sa.Column(sa.String(36),
                                   sa.ForeignKey('ipallocationpools.id',
                                                 ondelete="CASCADE"),
                                   nullable=True,
                                   primary_key=True)
    first_ip = sa.Column(sa.String(64), nullable=False, primary_key=True)
    last_ip = sa.Column(sa.String(64), nullable=False, primary_key=True)

    def __repr__(self):
        return "%s - %s" % (self.first_ip, self.last_ip)


class IPAllocationPool(model_base.BASEV2, HasId):
    """Representation of an allocation pool in a Quantum subnet."""

    subnet_id = sa.Column(sa.String(36), sa.ForeignKey('subnets.id',
                                                       ondelete="CASCADE"),
                          nullable=True)
    first_ip = sa.Column(sa.String(64), nullable=False)
    last_ip = sa.Column(sa.String(64), nullable=False)
    available_ranges = orm.relationship(IPAvailabilityRange,
                                        backref='ipallocationpool',
                                        lazy="dynamic")

    def __repr__(self):
        return "%s - %s" % (self.first_ip, self.last_ip)


class IPAllocation(model_base.BASEV2, HasId):
    """Internal representation of allocated IP addresses in a Quantum subnet.
    """
    port_id = sa.Column(sa.String(36), sa.ForeignKey('ports.id',
                                                     ondelete="CASCADE"),
                        nullable=True)
    ip_address = sa.Column(sa.String(64), nullable=False, primary_key=True)
    subnet_id = sa.Column(sa.String(36), sa.ForeignKey('subnets.id',
                                                       ondelete="CASCADE"),
                          nullable=False, primary_key=True)
    network_id = sa.Column(sa.String(36), sa.ForeignKey("networks.id",
                                                        ondelete="CASCADE"),
                           nullable=False, primary_key=True)
    expiration = sa.Column(sa.DateTime, nullable=True)


class Port(model_base.BASEV2, HasId, HasTenant):
    """Represents a port on a quantum v2 network."""
    name = sa.Column(sa.String(255))
    network_id = sa.Column(sa.String(36), sa.ForeignKey("networks.id"),
                           nullable=False)
    fixed_ips = orm.relationship(IPAllocation, backref='ports', lazy="dynamic")
    mac_address = sa.Column(sa.String(32), nullable=False)
    admin_state_up = sa.Column(sa.Boolean(), nullable=False)
    status = sa.Column(sa.String(16), nullable=False)
    device_id = sa.Column(sa.String(255), nullable=False)
    device_owner = sa.Column(sa.String(255), nullable=False)


class DNSNameServer(model_base.BASEV2):
    """Internal representation of a DNS nameserver."""
    address = sa.Column(sa.String(128), nullable=False, primary_key=True)
    subnet_id = sa.Column(sa.String(36),
                          sa.ForeignKey('subnets.id',
                                        ondelete="CASCADE"),
                          primary_key=True)


class Route(model_base.BASEV2):
    """Represents a route for a subnet or port."""
    destination = sa.Column(sa.String(64), nullable=False, primary_key=True)
    nexthop = sa.Column(sa.String(64), nullable=False, primary_key=True)
    subnet_id = sa.Column(sa.String(36),
                          sa.ForeignKey('subnets.id',
                                        ondelete="CASCADE"),
                          primary_key=True)


class Subnet(model_base.BASEV2, HasId, HasTenant):
    """Represents a quantum subnet.

    When a subnet is created the first and last entries will be created. These
    are used for the IP allocation.
    """
    name = sa.Column(sa.String(255))
    network_id = sa.Column(sa.String(36), sa.ForeignKey('networks.id'))
    ip_version = sa.Column(sa.Integer, nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)
    gateway_ip = sa.Column(sa.String(64))
    allocation_pools = orm.relationship(IPAllocationPool,
                                        backref='subnet',
                                        lazy="dynamic")
    enable_dhcp = sa.Column(sa.Boolean())
    dns_nameservers = orm.relationship(DNSNameServer,
                                       backref='subnet',
                                       cascade='delete')
    routes = orm.relationship(Route,
                              backref='subnet',
                              cascade='delete')
    shared = sa.Column(sa.Boolean)


class Network(model_base.BASEV2, HasId, HasTenant):
    """Represents a v2 quantum network."""
    name = sa.Column(sa.String(255))
    ports = orm.relationship(Port, backref='networks')
    subnets = orm.relationship(Subnet, backref='networks')
    status = sa.Column(sa.String(16))
    admin_state_up = sa.Column(sa.Boolean)
    shared = sa.Column(sa.Boolean)


#DreamHost PortFoward, Firewall(FilterRule), AddressBook models as
#Quantum extensions


class PortForward(model_base.BASEV2, HasId, HasTenant):
    """Represents a PortForward extension"""

    name = sa.Column(sa.String(255))
    public_port = sa.Column(sa.Integer, nullable=False)
    instance_id = sa.Column(sa.String(36), nullable=False)
    private_port = sa.Column(sa.Integer, nullable=True)
    # Quantum port address are stored in ipallocation which are internally
    # referred to as fixed_id, thus the name below.
    # XXX can we add a docsting to this model that explains how fixed_id is
    # used?
    fixed_id = sa.Column(
        sa.String(36), sa.ForeignKey('ipallocations.id',
            ondelete="CASCADE"),
        nullable=True)
    op_status = Column(String(16))

    #PortForward Model Validators using sqlalchamey simple validators

    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    @validates('public_port')
    def validate_public_port(self, key, public_port):
        public_port = int(public_port)
        assert public_port >= 0 and public_port <= 65536
        return public_port

    @validates('instance_id')
    def validate_instance_id(self, key, instance_id):
        retype = type(re.compile(Validator.UUID_PATTERN))
        assert isinstance(re.compile(instance_id), retype)
        assert len(instance_id) <= 36
        return instance_id

    @validates('private_port')
    def validate_private_port(self, key, private_port):
        private_port = int(private_port)
        assert private_port >= 0 and private_port <= 65536
        return private_port

    @validates('fixed_id')
    def validate_fixed_id(self, key, fixed_id):
        retype = type(re.compile(Validator.UUID_PATTERN))
        assert isinstance(re.compile(fixed_id), retype)
        assert len(fixed_id) <= 36
        return fixed_id

    @validates('op_status')
    def validate_op_status(self, key, op_status):
        assert isinstance(op_status, basestring)
        assert len(op_status) <= 16
        return op_status


class AddressBookEntry(model_base.BASEV2, HasId, HasTenant):
    """Represents as part of an AddressBook extension"""

    '''__tablename__ seems to be needed for plural of models ending
    with 'y in Quantum DB migrations'''
    __tablename__ = 'addressbookentries'

    group_id = sa.Column(sa.String(36), sa.ForeignKey('addressbookgroups.id'),
        nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)

    #AddressBookEntry Model Validators using sqlalchamey simple validators
    @validates('group_id')
    def validate_name(self, key, group_id):
        retype = type(re.compile(UUID_PATTERN))
        assert isinstance(re.compile(group_id), retype)
        assert len(group_id) <= 36
        return group_id

    @validates('cidr')
    def validate_public_port(self, key, cidr):
        assert netaddr.IPNetwork(cidr)
        assert len(cidr) <= 64
        return cidr


class AddressBookGroup(model_base.BASEV2, HasId, HasTenant):
    """Represents as part of an AddressBook extension"""

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    table_id = sa.Column(sa.String(36), sa.ForeignKey('addressbooks.id'),
        nullable=False)
    entries = orm.relationship(AddressBookEntry, backref='groups')

    #AddressBookGroup Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name

    @validates('table_id')
    def validate_table_id(self, key, table_id):
        retype = type(re.compile(Validator.UUID_PATTERN))
        assert isinstance(re.compile(table_id), retype)
        assert len(table_id) <= 36
        return table_id


class AddressBook(model_base.BASEV2, HasId, HasTenant):
    """Represents as part of an AddressBook extension"""

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    groups = orm.relationship(AddressBookGroup, backref='book')

    #AddressBook Model Validators using sqlalchamey simple validators
    @validates('name')
    def validate_name(self, key, name):
        assert isinstance(name, basestring)
        assert len(name) <= 255
        return name


class FilterRule(model_base.BASEV2, HasId, HasTenant):
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
    def validate_name(self, key, action):
        assert isinstance(action, basestring)
        assert len(action) <= 6
        return action

    @validates('ip_version')
    def validate_ip_version(self, key, ip_version):
        assert isinstance(ip_version) is int
        assert isinstance(ip_version, None)
        return ip_version

    @validates('protocol')
    def validate_protocol(self, key, protocol):
        assert isinstance(protocol, basestring)
        assert protocol.lower() in ('tcp', 'udp', 'icmp')
        assert len(protocol) <= 4
        return protocol

    @validates('source_alias')
    def validate_source_alias(self, key, source_alias):
        retype = type(re.compile(Validator.UUID_PATTERN))
        assert isinstance(re.compile(source_alias), retype)
        assert len(source_alias) <= 36
        return source_alias

    @validates('source_port')
    def validate_source_port(self, key, source_port):
        source_port = int(source_port)
        assert source_port >= 0 and source_port <= 65536
        assert len(source_port) <= 36
        return source_port

    @validates('destination_alias')
    def validate_destination_alias(self, key, destination_alias):
        retype = type(re.compile(Validator.UUID_PATTERN))
        assert isinstance(re.compile(destination_alias), retype)
        assert len(destination_alias) <= 36
        return destination_alias

    @validates('destination_port')
    def validate_destination_port(self, key, destination_port):
        destination_port = int(destination_port)
        assert destination_port >= 0 and destination_port <= 65536
        assert len(destination_port) <= 36
        return destination_port

    @validates('created_at')
    def validate_created_at(self, key, created_at):
        assert isinstance(created_at) is datetime
        return created_at
