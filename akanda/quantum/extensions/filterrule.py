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

from quantum.api.v2 import attributes
from quantum.extensions import extensions

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
        'action': {'allow_post': True, 'allow_put': False,
                   'required_by_policy': True,
                   'is_visible': True},
        'protocol': {'allow_post': True, 'allow_put': False,
                     'required_by_policy': True,
                     'is_visible': True},
        'source_alias': {'allow_post': True, 'allow_put': False,
                         'required_by_policy': True,
                         'is_visible': True},
        'source_port': {'allow_post': True, 'allow_put': False,
                        'required_by_policy': True,
                        'is_visible': True},
        'destination_alias': {'allow_post': True, 'allow_put': False,
                              'required_by_policy': True,
                              'is_visible': True},
        'destination_port': {'allow_post': True, 'allow_put': False,
                             'required_by_policy': True,
                             'is_visible': True},
        'created_at': {'allow_post': False, 'allow_put': False,
                       'required_by_policy': True,
                       'is_visible': True}

    }

    def make_dict(self, filterrule):
        """
        Convert a filterrule model object to a dictionary.
        """
        res = {'id': filterrule['id'],
               'action': filterrule['action'],
               'protocol': filterrule['protocol'],
               'source_alias': filterrule['source_alias'],
               'source_port': filterrule['source_port'],
               'destination_alias': filterrule['destination_alias'],
               'destination_port': filterrule['destination_port'],
               'created_at': filterrule['created_at'],
               'tenant_id': filterrule['tenant_id']}
        return res


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
