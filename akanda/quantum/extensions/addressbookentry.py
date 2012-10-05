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
from akanda.quantum.db import models_v2
from akanda.quantum.extensions import _authzbase


# from quantum.db import models_v2
# from quantum.extensions import _authzbase


class AddressbookentryResource(_authzbase.ResourceDelegate):
    """
    """
    model = models_v2.AddressBookEntry
    resource_name = 'addressbookentry'
    collection_name = 'addressbookentries'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'is_visible': True},
        'group_id': {'allow_post': True, 'allow_put': False,
                     'default': '', 'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True},
        'cidr': {'allow_post': True, 'allow_put': True,
                 'is_visible': True}
    }

    def make_dict(self, addressbookentry):
        """
        Convert a addressbook model object to a dictionary.
        """
        res = {'id': addressbookentry['id'],
               'name': addressbookentry['name'],
               'group_id': addressbookentry['group_id'],
               'tenant_id': addressbookentry['tenant_id'],
               'cidr': str(addressbookentry['cidr'])}
        return res

    def create(self, context, tenant_id, body):
        with context.session.begin(subtransactions=True):
            #verify group_id is owned by tenant
            qry = context.session.query(models_v2.AddressBookGroup)
            qry = qry.filter_by(tenant_id=tenant_id, id=body.get('group_id'))

            try:
                table = qry.one()
            except exc.NoResultFound:
                msg = ("Tenant %(tenant_id) does not have an address book "
                       "group with id %(group_id)s" %
                       {'tenant_id': tenant_id, 'group_id': group_id})
                raise q_exc.BadRequest(resource='addressbookentry', msg=msg)
            item = self.model(**body)
            context.session.add(item)
        return self.make_dict(item)


_authzbase.register_quota('addressbookentry', 'quota_addressbookentry')


class Addressbookentry(object):
    """
    """
    def get_name(self):
        return "addressbookentry"

    def get_alias(self):
        return "dhaddressbookentry"

    def get_description(self):
        return "An addressbookentry extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhaddressbookentry',
            _authzbase.create_extension(AddressbookentryResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
