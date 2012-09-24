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
from quantum.db import models_v2
from quantum.extensions import extensions

from quantum.extensions import _authzbase


class PortforwardResource(_authzbase.ResourceDelegate):
    """
    This class is responsible for receiving REST requests and operating on the
    defined data model to create, update, or delete portforward-related data.
    """
    model = models_v2.PortForward
    resource_name = 'portforward'
    collection_name = 'portforwards'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'default': '', 'is_visible': True},
        'protocol': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'instance_id': {'allow_post': True, 'allow_put': False,
                        'required_by_policy': True,
                        'is_visible': True},
        'public_port': {'allow_post': True, 'allow_put': False,
                        'required_by_policy': True,
                        'is_visible': True},
        'private_port': {'allow_post': True, 'allow_put': False,
                         'required_by_policy': True,
                         'is_visible': True},
        'fixed_id': {'allow_post': True, 'allow_put': False,
                     'required_by_policy': True,
                     'is_visible': True},
        'op_status': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True}
    }

    def make_dict(self, portforward):
        """
        Convert a portforward model object to a dictionary.
        """
        res = {'id': portforward['id'],
               'name': portforward['name'],
               'protocol': portforward['protocol'],
               'instance_id': portforward['instance_id'],
               'public_port': portforward['public_port'],
               'private_port': portforward['private_port'],
               'fixed_id': portforward['fixed_id'],
               'op_status': portforward['op_status']}
        return res


_authzbase.register_quota('portforward', 'quota_portforward')


class Portforward(object):
    """
    """
    def get_name(self):
        return "port forward"

    def get_alias(self):
        return "dhportforward"

    def get_description(self):
        return "A port forwarding extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhportforward',
            _authzbase.create_extension(PortforwardResource()))]
            #_authzbase.ResourceController(PortforwardResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
