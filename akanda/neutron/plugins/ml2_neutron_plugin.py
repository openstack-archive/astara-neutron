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

from neutron.db import l3_db
from neutron.plugins.ml2 import plugin
from neutron.services.l3_router import l3_router_plugin

from akanda.neutron.plugins import decorators as akanda
from akanda.neutron.plugins import floatingip

akanda.monkey_patch_ipv6_generator()


class Ml2Plugin(floatingip.ExplicitFloatingIPAllocationMixin,
                plugin.Ml2Plugin):

    _supported_extension_aliases = (
        plugin.Ml2Plugin._supported_extension_aliases +
        ["dhrouterstatus"]
    )

    # The auto_add_other_resources decorator enable the automatic
    # creation of a bunch of resources. These resources are in the
    # form of neutron extensions and need to be registered with the
    # plugin. Since we are not enabling those extension right now,
    # lets comment out the decorator

    # @akanda.auto_add_other_resources
    @akanda.auto_add_ipv6_subnet
    def create_network(self, context, network):
        return super(Ml2Plugin, self).create_network(context, network)

    @akanda.auto_add_subnet_to_router
    def create_subnet(self, context, subnet):
        return super(Ml2Plugin, self).create_subnet(context, subnet)

    @akanda.sync_subnet_gateway_port
    def update_subnet(self, context, id, subnet):
        return super(Ml2Plugin, self).update_subnet(
            context, id, subnet)


class L3RouterPlugin(l3_router_plugin.L3RouterPlugin):

    # An issue in neutron is making this class inheriting some
    # methods from l3_dvr_db.L3_NAT_with_dvr_db_mixin.As a workaround
    # we force it to use the original methods in the
    # l3_db.L3_NAT_db_mixin class.
    get_sync_data = l3_db.L3_NAT_db_mixin.get_sync_data
    add_router_interface = l3_db.L3_NAT_db_mixin.add_router_interface

    def list_routers_on_l3_agent(self, context, agent_id):
        return {
            'routers': self.get_routers(context),
        }

    def list_active_sync_routers_on_active_l3_agent(
            self, context, host, router_ids):
        # Override L3AgentSchedulerDbMixin method
        filters = {}
        if router_ids:
            filters['id'] = router_ids
        routers = self.get_routers(context, filters=filters)
        new_router_ids = [r['id'] for r in routers]
        if new_router_ids:
            return self.get_sync_data(
                context,
                router_ids=new_router_ids,
                active=True,
            )
        return []
