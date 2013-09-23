# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 New Dream Network, LLC (DreamHost)
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from neutron.plugins.openvswitch import ovs_neutron_plugin

from akanda.neutron.plugins import decorators as akanda
akanda.monkey_patch_ipv6_generator()


class OVSNeutronPluginV2(ovs_neutron_plugin.OVSNeutronPluginV2):
    _supported_extension_aliases = (
        ovs_neutron_plugin.OVSNeutronPluginV2._supported_extension_aliases +
        ["dhportforward", "dhaddressgroup", "dhaddressentry",
         "dhfilterrule", "dhportalias"])

    try:
        _supported_extension_aliases.remove('agent_scheduler')
    except ValueError:
        pass

    @akanda.auto_add_other_resources
    @akanda.auto_add_ipv6_subnet
    def create_network(self, context, network):
        return super(OVSNeutronPluginV2, self).create_network(context, network)

    @akanda.auto_add_subnet_to_router
    def create_subnet(self, context, subnet):
        return super(OVSNeutronPluginV2, self).create_subnet(context, subnet)

    @akanda.sync_subnet_gateway_port
    def update_subnet(self, context, id, subnet):
        return super(OVSNeutronPluginV2, self).update_subnet(
            context, id, subnet)
