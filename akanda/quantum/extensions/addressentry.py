# Copyright 2012 New Dream Network, LLC (DreamHost)
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
# @author: Murali Raju, New Dream Network, LLC (DreamHost)
# @author: Mark Mcclain, New Dream Network, LLC (DreamHost)

import logging

from quantum.api.v2 import attributes
from quantum.common import exceptions as q_exc
from quantum.extensions import extensions
from sqlalchemy.orm import exc


from akanda.quantum.db import models_v2
from akanda.quantum.extensions import _authzbase

LOG = logging.getLogger(__name__)


class AddressEntryResource(_authzbase.ResourceDelegate):
    """
    """
    model = models_v2.AddressEntry
    resource_name = 'addressentry'
    collection_name = 'addressentries'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'is_visible': True},
        'group_id': {'allow_post': True, 'allow_put': False,
                     'required_by_policy': True,
                     'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'cidr': {'allow_post': True, 'allow_put': True,
                 'is_visible': True}
    }

    def make_dict(self, addressentry):
        """
        Convert a address model object to a dictionary.
        """
        res = {'id': addressentry['id'],
               'name': addressentry['name'],
               'group_id': addressentry['group_id'],
               'tenant_id': addressentry['tenant_id'],
               'cidr': str(addressentry['cidr']),
               }
        return res

    def create(self, context, tenant_id, body):
        with context.session.begin(subtransactions=True):
            #verify group_id is owned by tenant
            qry = context.session.query(models_v2.AddressGroup)
            qry = qry.filter_by(tenant_id=tenant_id, id=body.get('group_id'))

            try:
                group = qry.one()
            except exc.NoResultFound:
                msg = ("Tenant %(tenant_id) does not have an address "
                       "group with id %(group_id)s" %
                       {'tenant_id': tenant_id,
                        'group_id': body.get('group_id'),
                        })
                raise q_exc.BadRequest(resource='addressentry', msg=msg)
            if group.name == 'Any':
                raise q_exc.PolicyNotAuthorized(
                    action='modification of system address groups'
                    )
            if 'tenant_id' in body:
                del body['tenant_id']
            item = self.model(tenant_id=tenant_id, **body)
            context.session.add(item)
        return self.make_dict(item)

    def update(self, context, resource, resource_dict):
        if resource.group.name == 'Any':
            raise q_exc.PolicyNotAuthorized(
                action='modification of system address groups'
                )
        return super(AddressEntryResource, self).update(
            context,
            resource,
            resource_dict,
            )

    def before_delete(self, resource):
        if resource.group.name == 'Any':
            raise q_exc.PolicyNotAuthorized(
                action='modification of system address groups'
                )
        return super(AddressEntryResource, self).before_delete(resource)


_authzbase.register_quota('addressentry', 'quota_addressentry')


class Addressentry(object):
    """
    """
    def get_name(self):
        return "addressentry"

    def get_alias(self):
        return "dhaddressentry"

    def get_description(self):
        return "An addressentry extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhaddressentry',
            _authzbase.create_extension(AddressEntryResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
