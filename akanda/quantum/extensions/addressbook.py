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


class AddressbookResource(_authzbase.ResourceDelegate):
    """
    """
    model = models_v2.AddressBookEntry
    #model = models_v2.AddressBook
    resource_name = 'addressbook'
    collection_name = 'addressbooks'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'default': '', 'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True},
        'cidr': {'allow_post': True, 'allow_put': True,
                      'is_visible': True}
    }

    def make_dict(self, addressbook):
        """
        Convert a addressbook model object to a dictionary.
        """
        res = {'id': addressbook['id'],
               'name': addressbook['name'],
               'cidr': addressbook['cidr'],
               'tenant_id': addressbook['tenant_id']}
        return res

        #res = {'id': addressbook['id'],
        #       'name': addressbook['name'],
        #       'groups': [group['id']
        #       for group in addressbook['groups']]}
        #return res


_authzbase.register_quota('addressbook', 'quota_addressbook')


class Addressbook(object):
    """
    """
    def get_name(self):
        return "addressbook"

    def get_alias(self):
        return "dhaddressbook"

    def get_description(self):
        return "An addressbook extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhaddressbook',
            _authzbase.create_extension(AddressbookResource()))]
            #_authzbase.ResourceController(AddressBookResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
