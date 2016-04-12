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

from neutron.api import extensions

from neutron.db.l3_db import Router
from neutron.db import models_v2
from astara_neutron.extensions import _authzbase


STATUS_ACTIVE = 'ACTIVE'
STATUS_DOWN = 'DOWN'


class RouterstatusResource(_authzbase.ResourceDelegate):
    """This resource is intended as a private API that allows the rug to change
    a router's status (which is normally a read-only attribute)
    """
    model = Router
    resource_name = 'routerstatus'
    collection_name = 'routerstatuses'

    ATTRIBUTE_MAP = {
        'tenant_id': {
            'allow_post': False,
            'allow_put': False,
            'is_visible': False
        },
        'status': {
            'allow_post': False,
            'allow_put': True,
            'is_visible': True,
            'enforce_policy': True,
            'required_by_policy': True
        }
    }

    def make_dict(self, router):
        """
        Convert a router model object to a dictionary.
        """
        return {
            'tenant_id': router['tenant_id'],
            'status': router['status']
        }

    def update(self, context, resource, resource_dict):
        with context.session.begin(subtransactions=True):
            resource.update(resource_dict)
            context.session.add(resource)

            # sync logical ports to backing port status
            for router_port in resource.attached_ports:
                if router_port.port.status != resource.status:
                    self._update_port_status(
                        context,
                        resource,
                        router_port.port
                    )
                    context.session.add(router_port.port)
            return self.make_dict(resource)

    def _update_port_status(self, context, router, port):
        # assume port is down until proven otherwise

        # find backing ports works with both  ASTARA and AKANDA
        partial_name = 'A%%:VRRP:%s' % router.id

        query = context.session.query(models_v2.Port)
        query = query.filter(
                models_v2.Port.network_id == port.network_id,
                models_v2.Port.name.like(partial_name)
        )

        next_status = STATUS_DOWN

        for backing_port in query.all():
            if not backing_port.device_owner or not backing_port.device_id:
                continue

            next_status = backing_port.status
            if next_status != STATUS_ACTIVE:
                break

        port.status = next_status


class Routerstatus(extensions.ExtensionDescriptor):
    """
    """
    @classmethod
    def get_name(cls):
        return "routerstatus"

    @classmethod
    def get_alias(cls):
        return "dhrouterstatus"

    @classmethod
    def get_description(cls):
        return "A router-status extension"

    @classmethod
    def get_namespace(cls):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    @classmethod
    def get_updated(cls):
        return "2014-06-04T09:14:43-05:00"

    @classmethod
    def get_resources(cls):
        return [extensions.ResourceExtension(
            'dhrouterstatus',
            _authzbase.create_extension(RouterstatusResource()))]
