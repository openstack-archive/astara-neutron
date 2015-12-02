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

import re

import netaddr
from neutron.common import constants as neutron_constants
from neutron.db import l3_db
from neutron.plugins.ml2 import plugin
from neutron.services.l3_router import l3_router_plugin

from astara_neutron.plugins import decorators as astara
from astara_neutron.plugins import floatingip


AKANDA_PORT_NAME_RE = re.compile(
    '^AKANDA:(MGT|VRRP):[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$'
)


class Ml2Plugin(floatingip.ExplicitFloatingIPAllocationMixin,
                plugin.Ml2Plugin):

    _supported_extension_aliases = (
        plugin.Ml2Plugin._supported_extension_aliases +
        ["dhrouterstatus"]
    )

    disabled_extensions = [
        neutron_constants.DHCP_AGENT_SCHEDULER_EXT_ALIAS,
        neutron_constants.L3_AGENT_SCHEDULER_EXT_ALIAS,
        neutron_constants.LBAAS_AGENT_SCHEDULER_EXT_ALIAS
    ]
    for ext in disabled_extensions:
        try:
            _supported_extension_aliases.remove(ext)
        except ValueError:
            pass

    @astara.auto_add_ipv6_subnet
    def create_network(self, context, network):
        return super(Ml2Plugin, self).create_network(context, network)

    @astara.auto_add_subnet_to_router
    def create_subnet(self, context, subnet):
        return super(Ml2Plugin, self).create_subnet(context, subnet)

    @astara.sync_subnet_gateway_port
    def update_subnet(self, context, id, subnet):
        return super(Ml2Plugin, self).update_subnet(
            context, id, subnet)

    # Nova is unhappy when the port does not have any IPs, so we're going
    # to add the v6 link local dummy data.
    # TODO(mark): limit this lie to service user
    def _make_port_dict(self, port, fields=None, process_extensions=True):
        res = super(Ml2Plugin, self)._make_port_dict(
            port,
            fields,
            process_extensions
        )

        if not res.get('fixed_ips') and res.get('mac_address'):
            v6_link_local = netaddr.EUI(res['mac_address']).ipv6_link_local()

            res['fixed_ips'] = [
                {
                    'subnet_id': '00000000-0000-0000-0000-000000000000',
                    'ip_address': str(v6_link_local)
                }
            ]
        return res

    # TODO(markmcclain) add upstream ability to remove port-security
    # workaround it for now by filtering out Akanda ports
    def get_ports_from_devices(self, context, devices):
        "this wrapper removes Akanda VRRP ports since they are router ports"
        ports = super(Ml2Plugin, self).get_ports_from_devices(context, devices)
        return (
            port
            for port in ports
            if port and not AKANDA_PORT_NAME_RE.match(port['name'])
        )


class L3RouterPlugin(l3_router_plugin.L3RouterPlugin):

    # An issue in neutron is making this class inheriting some
    # methods from l3_dvr_db.L3_NAT_with_dvr_db_mixin.As a workaround
    # we force it to use the original methods in the
    # l3_db.L3_NAT_db_mixin class.
    get_sync_data = l3_db.L3_NAT_db_mixin.get_sync_data
    add_router_interface = l3_db.L3_NAT_db_mixin.add_router_interface
    remove_router_interface = l3_db.L3_NAT_db_mixin.remove_router_interface

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
