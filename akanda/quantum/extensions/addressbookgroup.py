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
from quantum.common import exceptions as q_exc
from quantum.extensions import extensions
from sqlalchemy.orm import exc

# Disabling until Mark's setup works
#
# from akanda.quantum.db import models_v2
# from akanda.quantum.extensions import _authzbase


from quantum.db import models_v2
from quantum.extensions import _authzbase


class AddressbookgroupResource(_authzbase.ResourceDelegate):
    """
    """
    model = models_v2.AddressBookGroup
    resource_name = 'addressbookgroup'
    collection_name = 'addressbookgroups'

    # To be used if addressbook is used

    # ATTRIBUTE_MAP = {
    #     'id': {'allow_post': False, 'allow_put': False,
    #            'validate': {'type:regex': attributes.UUID_PATTERN},
    #            'is_visible': True},
    #     'book_id': {'allow_post': True, 'allow_put': False,
    #                 'default': '', 'is_visible': True},
    #     'name': {'allow_post': True, 'allow_put': True,
    #              'default': '', 'is_visible': True},
    #     'tenant_id': {'allow_post': True, 'allow_put': False,
    #                   'is_visible': True},
    #     'entries': {'allow_post': False, 'allow_put': False,
    #                'is_visible': True}
    # }

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'default': '', 'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True},
        'entries': {'allow_post': False, 'allow_put': False,
                   'is_visible': True}
    }

    def make_dict(self, addressbookgroup):
        """
        Convert a addressbook model object to a dictionary.
        """
        res = {'id': addressbookgroup['id'],
               'name': addressbookgroup['name'],
               'tenant_id': addressbookgroup['tenant_id'],
               'entries': [e['id'] for e in addressbookgroup['entries']]}
        return res


    # Use default create via _authzbase. Comment out the following
    # if addressbook is used

    # def create(self, context, tenant_id, body):
    #     with context.session.begin(subtransactions=True):
    #         #verify book_id is owned by tenant
    #         qry = context.session.query(models_v2.AddressBook)
    #         qry = qry.filter_by(tenant_id=tenant_id, id=body.get('book_id'))

    #         try:
    #             table = qry.one()
    #         except exc.NoResultFound:
    #             msg = ("Tenant %(tenant_id) does not have an address book with"
    #                    " id %(book_id)s" %
    #                    {'tenant_id': tenant_id, 'book_id': book_id})
    #             raise q_exc.BadRequest(resource='addressbookgroup', msg=msg)
    #         item = self.model(**body)
    #         context.session.add(item)
    #     return self.make_dict(item)


_authzbase.register_quota('addressbookgroup', 'quota_addressbookgroup')


class Addressbookgroup(object):
    """
    """
    def get_name(self):
        return "addressbookgroup"

    def get_alias(self):
        return "dhaddressbookgroup"

    def get_description(self):
        return "An addressbookgroup extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhaddressbookgroup',
            _authzbase.create_extension(AddressbookgroupResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
