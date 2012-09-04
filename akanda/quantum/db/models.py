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


from quantum.api import api_common as common
from quantum.db import model_base
from quantum.db import models_v2 as models
from quantum.openstack.common import timeutils


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


class AddressBookEntry(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'addressbookentries'

    group_id = sa.Column(sa.String(36), sa.ForeignKey('addressbookgroups.id'),
        nullable=False)
    cidr = sa.Column(sa.String(64), nullable=False)
    #pass


class AddressBookGroup(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'addressbookgroups'

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    table_id = sa.Column(sa.String(36), sa.ForeignKey('addressbooks.id'),
        nullable=False)
    entries = orm.relationship(AddressBookEntry, backref='groups')
    #pass


class AddressBook(model_base.BASEV2, models.HasId, models.HasTenant):

    __tablename__ = 'addressbooks'

    name = sa.Column(sa.String(255), nullable=False, primary_key=True)
    groups = orm.relationship(AddressBookGroup, backref='book')
    #pass


class FilterRule(model_base.BASEV2, models.HasId, models.HasTenant):

    # __tablename__ = 'filterrules'

    #  action = sa.Column(sa.String(6), nullable=False, primary_key=True)
    #  ip_version = sa.Column(sa.Integer, nullable=True)
    #  protocol = sa.Column(sa.String(4), nullable=False)
    #  source_alias = sa.Column(sa.String(36),
    #      sa.ForeignKey('addressbookentry.id'),
    #      nullable=False)
    #  source_port = sa.Column(sa.Integer, nullable=True)
    #  destination_alias = sa.Column(sa.String(36),
    #      sa.ForeignKey('addressbookentry.id'),
    #      nullable=False)
    #  destination_port = sa.Column(sa.Integer, nullable=True)
    #  created_at = sa.Column(sa.DateTime, default=timeutils.utcnow,
    #      nullable=False)
    pass
