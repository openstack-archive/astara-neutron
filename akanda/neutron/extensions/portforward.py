# Copyright 2014 DreamHost, LLC
#
# Author: DreamHost, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from sqlalchemy.orm import exc

from neutron.api import extensions
from neutron.api.v2 import attributes
from neutron.common import exceptions as q_exc
from neutron.db import models_v2 as qmodels

from akanda.neutron.db import models_v2
from akanda.neutron.extensions import _authzbase


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
        'protocol': {'allow_post': True, 'allow_put': True,
                     'default': 'tcp',
                     'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
        'public_port': {'allow_post': True, 'allow_put': True,
                        'required_by_policy': True,
                        'is_visible': True},
        'private_port': {'allow_post': True, 'allow_put': True,
                         'default': None, 'is_visible': True},
        'port_id': {'allow_post': True, 'allow_put': True,
                    'validate': {'type:regex': attributes.UUID_PATTERN},
                    'required_by_policy': True,
                    'is_visible': True},
        'port': {'allow_post': False, 'allow_put': False, 'is_visible': True}
    }

    def make_port_dict(self, port):
        return {
            'id': port['id'],
            'name': port['name'],
            'network_id': port['network_id'],
            'tenant_id': port['tenant_id'],
            'mac_address': port['mac_address'],
            'admin_state_up': port['admin_state_up'],
            'status': port['status'],
            'fixed_ips': [{'subnet_id': ip['subnet_id'],
                           'ip_address': ip['ip_address']}
                          for ip in port['fixed_ips']],
            'device_id': port['device_id'],
            'device_owner': port['device_owner']
        }

    def make_dict(self, portforward):
        """
        Convert a portforward model object to a dictionary.
        """
        res = {'id': portforward['id'],
               'name': portforward['name'],
               'protocol': portforward['protocol'],
               'public_port': portforward['public_port'],
               'private_port': portforward['private_port'],
               'port': self.make_port_dict(portforward['port']),
               'tenant_id': portforward['tenant_id']}
        return res

    def create(self, context, tenant_id, body):
        with context.session.begin(subtransactions=True):
            # verify group_id is owned by tenant
            qry = context.session.query(qmodels.Port)
            qry = qry.filter_by(tenant_id=tenant_id, id=body.get('port_id'))

            try:
                qry.one()
            except exc.NoResultFound:
                msg = ("Tenant %(tenant_id) does not have an port "
                       "with id %(group_id)s" %
                       {'tenant_id': tenant_id,
                        'port_id': body.get('port_id'),
                        })
                raise q_exc.BadRequest(resource='addressentry', msg=msg)

            item = self.model(**body)
            if not item['private_port']:
                item['private_port'] = item['public_port']
            context.session.add(item)
        return self.make_dict(item)

    def update(self, context, resource, resource_dict):
        with context.session.begin(subtransactions=True):
            resource.update(resource_dict)
            # FIXME(dhellmann): This variable is undefined
            # but I don't know what it should have been.
            if not resource['private_port']:
                resource['private_port'] = resource['public_port']
            context.session.add(resource)
        return self.make_dict(resource)


_authzbase.register_quota('portforward', 'quota_portforward')


class Portforward(object):
    """
    """
    def get_name(self):
        return "portforward"

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
        # _authzbase.ResourceController(PortforwardResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
