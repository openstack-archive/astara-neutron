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

from quantum.api import extensions
from quantum.api.v2 import attributes
from quantum.common import exceptions as q_exc
from sqlalchemy.orm import exc


from akanda.quantum.db import models_v2
from akanda.quantum.extensions import _authzbase


class FilterruleResource(_authzbase.ResourceDelegate):
    """
    """
    model = models_v2.FilterRule
    resource_name = 'filterrule'
    collection_name = 'filterrules'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'action': {'allow_post': True, 'allow_put': True,
                   'required_by_policy': True,
                   'is_visible': True},
        'protocol': {'allow_post': True, 'allow_put': True,
                     'required_by_policy': True,
                     'is_visible': True},
        'source_id': {'allow_post': True, 'allow_put': True,
                      'default': None, 'is_visible': True},
        'source': {'allow_post': False, 'allow_put': False,
                   'default': None, 'is_visible': True},
        'source_port': {'allow_post': True, 'allow_put': True,
                        'default': None, 'is_visible': True},
        'destination_id': {'allow_post': True, 'allow_put': True,
                           'default': None, 'is_visible': True},
        'destination': {'allow_post': False, 'allow_put': False,
                        'default': None, 'is_visible': True},
        'destination_port': {'allow_post': True, 'allow_put': True,
                             'is_visible': True},
        'created_at': {'allow_post': False, 'allow_put': False,
                       'is_visible': True}
    }

    def make_entry_dict(self, addressentry):
        res = {
            'id': addressentry['id'],
            'name': addressentry['name'],
            'tenant_id': addressentry['tenant_id'],
            'name': addressentry['name'],
            'cidr': addressentry['cidr']
        }
        return res

    def make_abgroup_dict(self, addressgroup):
        if addressgroup is None:
            return

        res = {
            'id': addressgroup['id'],
            'name': addressgroup['name'],
            'tenant_id': addressgroup['tenant_id'],
            'entries': [self.make_entry_dict(e)
                        for e in addressgroup.entries]
        }

        return res

    def make_dict(self, filterrule):
        """
        Convert a filterrule model object to a dictionary.
        """
        res = {
            'id': filterrule['id'],
            'action': filterrule['action'],
            'protocol': filterrule['protocol'],
            'source': self.make_abgroup_dict(filterrule['source']),
            'source_port': filterrule['source_port'],
            'destination': self.make_abgroup_dict(filterrule['destination']),
            'destination_port': filterrule['destination_port'],
            'created_at': filterrule['created_at'],
            'tenant_id': filterrule['tenant_id']}
        return res

    def create(self, context, tenant_id, body):
        with context.session.begin(subtransactions=True):
            if body.get('source_id'):
                self._owns_abgroup(context, tenant_id, body['source_id'])
            if body.get('destination_id'):
                self._owns_abgroup(context, tenant_id, body['destination_id'])
            item = self.model(**body)
            context.session.add(item)
        return self.make_dict(item)

    def _owns_abgroup(self, context, tenant_id, addressgroup_id):
        #verify group_id is owned by tenant
        if addressgroup_id is None:
            return True

        qry = context.session.query(models_v2.AddressGroup)
        qry = qry.filter_by(tenant_id=tenant_id, id=addressgroup_id)

        try:
            qry.one()
        except exc.NoResultFound:
            msg = ("Tenant %(tenant_id)s does not have an address "
                   "group with id %(group_id)s" %
                   {'tenant_id': tenant_id, 'group_id': addressgroup_id})
            raise q_exc.BadRequest(resource='filterrule', msg=msg)

        return True

_authzbase.register_quota('filterrule', 'quota_filterrule')


class Filterrule(object):
    """
    """
    def get_name(self):
        return "filterrule"

    def get_alias(self):
        return "dhfilterrule"

    def get_description(self):
        return "A filter rule extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhfilterrule',
            _authzbase.create_extension(FilterruleResource()))]
            #_authzbase.ResourceController(FilterRuleResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
