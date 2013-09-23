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
# DreamHost Neutron Extensions
# @author: Murali Raju, New Dream Network, LLC (DreamHost)
# @author: Mark Mcclain, New Dream Network, LLC (DreamHost)

from neutron.api import extensions
from neutron.api.v2 import attributes
from neutron.common import exceptions


from akanda.neutron.db import models_v2
from akanda.neutron.extensions import _authzbase


class AddressGroupResource(_authzbase.ResourceDelegate):
    """
    """
    model = models_v2.AddressGroup
    resource_name = 'addressgroup'
    collection_name = 'addressgroups'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'default': '', 'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'entries': {'allow_post': False, 'allow_put': False,
                    'is_visible': True}
    }

    def make_entry_dict(self, addressentry):
        return {
            'id': addressentry['id'],
            'name': addressentry['name'],
            'group_id': addressentry['group_id'],
            'tenant_id': addressentry['tenant_id'],
            'cidr': addressentry['cidr']
        }

    def make_dict(self, addressgroup):
        """
        Convert a address model object to a dictionary.
        """
        res = {
            'id': addressgroup['id'],
            'name': addressgroup['name'],
            'tenant_id': addressgroup['tenant_id'],
            'entries': [self.make_entry_dict(e)
                        for e in addressgroup['entries']]
        }
        return res

    def create(self, context, tenant_id, body):
        if body.get('name', '').lower() == 'any':
            raise exceptions.PolicyNotAuthorized(
                action='creation of wildcard address groups'
            )
        return super(AddressGroupResource, self).create(
            context,
            tenant_id,
            body,
        )

    def update(self, context, resource, resource_dict):
        if resource.name == 'Any':
            raise exceptions.PolicyNotAuthorized(
                action='modification of system address groups'
            )
        return super(AddressGroupResource, self).update(
            context,
            resource,
            resource_dict,
        )

    def before_delete(self, resource):
        if resource.name == 'Any':
            raise exceptions.PolicyNotAuthorized(
                action='modification of system address groups'
            )
        return super(AddressGroupResource, self).before_delete(resource)

_authzbase.register_quota('addressgroup', 'quota_addressgroup')


class Addressgroup(object):
    """
    """
    def get_name(self):
        return "addressgroup"

    def get_alias(self):
        return "dhaddressgroup"

    def get_description(self):
        return "An addressgroup extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhaddressgroup',
            _authzbase.create_extension(AddressGroupResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
