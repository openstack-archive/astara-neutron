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

import functools

from quantum.common import topics
from quantum.db import l3_db
from quantum.db import l3_rpc_base as l3_rpc
from quantum.extensions import portsecurity as psec
from quantum.extensions import securitygroup as ext_sg
from quantum.openstack.common import log as logging
from quantum.openstack.common import rpc
from quantum.plugins.nicira.nicira_nvp_plugin.QuantumPlugin import nicira_db
from quantum.plugins.nicira.nicira_nvp_plugin import QuantumPlugin as nvp
from quantum.plugins.nicira.nicira_nvp_plugin.QuantumPlugin import nvplib

from akanda.quantum.plugins import decorators as akanda

LOG = logging.getLogger("QuantumPlugin")
akanda.monkey_patch_ipv6_generator()


def egress_multicast_hotfix(f):
    @functools.wraps(f)
    def wrapper(lport_obj, mac_address, fixed_ips, port_security_enabled,
                security_profiles, queue_id):
        f(lport_obj, mac_address, fixed_ips, port_security_enabled,
          security_profiles, queue_id)

        # evaulate the state so that we only override the value when enabled
        # otherwise we are preserving the underlying behavior of the NVP plugin
        if port_security_enabled:
            # hotfix to enable egress mulitcast
            lport_obj['allow_egress_multicast'] = True
    return wrapper


nvp.nvplib._configure_extensions = egress_multicast_hotfix(
    nvp.nvplib._configure_extensions
)


class AkandaNvpRpcCallbacks(l3_rpc.L3RpcCallbackMixin, nvp.NVPRpcCallbacks):
    pass


class NvpPluginV2(nvp.NvpPluginV2):
    """
    NvpPluginV2 is a Quantum plugin that provides L2 Virtual Network
    functionality using NVP.
    """
    supported_extension_aliases = (
        nvp.NvpPluginV2.supported_extension_aliases +
        akanda.SUPPORTED_EXTENSIONS
    )

    def __init__(self, loglevel=None):
        super(NvpPluginV2, self).__init__(loglevel)

        # replace port drivers with Akanda compatible versions
        self._port_drivers = {
            'create': {
                l3_db.DEVICE_OWNER_FLOATINGIP: self._nvp_create_fip_port,
                'default': self._nvp_create_port
            },
            'delete': {
                l3_db.DEVICE_OWNER_FLOATINGIP: self._nvp_delete_fip_port,
                'default': self._nvp_delete_port
            }
        }

    def setup_rpc(self):
        # RPC support for dhcp + L3 protocol
        self.conn = rpc.create_connection(new=True)
        self.conn.create_consumer(
            topics.PLUGIN,
            AkandaNvpRpcCallbacks().create_rpc_dispatcher(),
            fanout=False
        )

        # Consume from all consumers in a thread
        self.conn.consume_in_thread()

    @akanda.auto_add_other_resources
    @akanda.auto_add_ipv6_subnet
    def create_network(self, context, network):
        return super(NvpPluginV2, self).create_network(context, network)

    @akanda.auto_add_subnet_to_router
    def create_subnet(self, context, subnet):
        return super(NvpPluginV2, self).create_subnet(context, subnet)

    @akanda.sync_subnet_gateway_port
    def update_subnet(self, context, id, subnet):
        return super(NvpPluginV2, self).update_subnet(context, id, subnet)

    # we need to use original versions l3_db.L3_NAT_db_mixin mixin and not
    # NVP versions that manage NVP's logical router

    create_router = l3_db.L3_NAT_db_mixin.create_router
    update_router = l3_db.L3_NAT_db_mixin.update_router
    delete_router = l3_db.L3_NAT_db_mixin.delete_router
    get_router = l3_db.L3_NAT_db_mixin.get_router
    get_routers = l3_db.L3_NAT_db_mixin.get_routers
    add_router_interface = l3_db.L3_NAT_db_mixin.add_router_interface
    remove_router_interface = l3_db.L3_NAT_db_mixin.remove_router_interface
    create_floatingip = l3_db.L3_NAT_db_mixin.create_floatingip
    update_floatingip = l3_db.L3_NAT_db_mixin.update_floatingip
    delete_floatingip = l3_db.L3_NAT_db_mixin.delete_floatingip
    get_floatingip = l3_db.L3_NAT_db_mixin.get_floatingip
    get_floatings = l3_db.L3_NAT_db_mixin.get_floatingips
    _update_fip_assoc = l3_db.L3_NAT_db_mixin._update_fip_assoc
    disassociate_floatingips = l3_db.L3_NAT_db_mixin.disassociate_floatingips

    def _ensure_metadata_host_route(self, *args, **kwargs):
        """ Akanda metadata services are provided by router so make no-op/"""
        pass

    def _nvp_create_port(self, context, port_data):
        """ Driver for creating a logical switch port on NVP platform """
        # NOTE(mark): Akanda does want ports for external networks so
        # this method is basically same with external check removed
        network = self._get_network(context, port_data['network_id'])
        network_binding = nicira_db.get_network_binding(
            context.session, port_data['network_id'])
        max_ports = self.nvp_opts.max_lp_per_overlay_ls
        allow_extra_lswitches = False
        if (network_binding and
            network_binding.binding_type in (NetworkTypes.FLAT,
                                             NetworkTypes.VLAN)):
            max_ports = self.nvp_opts.max_lp_per_bridged_ls
            allow_extra_lswitches = True
        try:
            cluster = self._find_target_cluster(port_data)
            selected_lswitch = self._handle_lswitch_selection(
                cluster, network, network_binding, max_ports,
                allow_extra_lswitches)
            lswitch_uuid = selected_lswitch['uuid']
            lport = nvplib.create_lport(cluster,
                                        lswitch_uuid,
                                        port_data['tenant_id'],
                                        port_data['id'],
                                        port_data['name'],
                                        port_data['device_id'],
                                        port_data['admin_state_up'],
                                        port_data['mac_address'],
                                        port_data['fixed_ips'],
                                        port_data[psec.PORTSECURITY],
                                        port_data[ext_sg.SECURITYGROUPS])
            nicira_db.add_quantum_nvp_port_mapping(
                context.session, port_data['id'], lport['uuid'])
            d_owner = port_data['device_owner']

            nvplib.plug_interface(cluster, lswitch_uuid,
                                  lport['uuid'], "VifAttachment",
                                  port_data['id'])
            LOG.debug(_("_nvp_create_port completed for port %(port_name)s "
                        "on network %(net_id)s. The new port id is "
                        "%(port_id)s. NVP port id is %(nvp_port_id)s"),
                      {'port_name': port_data['name'],
                       'net_id': port_data['network_id'],
                       'port_id': port_data['id'],
                       'nvp_port_id': lport['uuid']})
        except Exception:
            # failed to create port in NVP delete port from quantum_db
            LOG.exception(_("An exception occured while plugging "
                            "the interface"))
            raise

    def _nvp_delete_port(self, context, port_data):
        # NOTE(mark): Akanda does want ports for external networks so
        # this method is basically same with external check removed
        port = nicira_db.get_nvp_port_id(context.session, port_data['id'])
        if port is None:
            raise q_exc.PortNotFound(port_id=port_data['id'])
        # TODO(bgh): if this is a bridged network and the lswitch we just got
        # back will have zero ports after the delete we should garbage collect
        # the lswitch.
        nvplib.delete_port(self.default_cluster,
                           port_data['network_id'],
                           port)
        LOG.debug(_("_nvp_delete_port completed for port %(port_id)s "
                    "on network %(net_id)s"),
                  {'port_id': port_data['id'],
                   'net_id': port_data['network_id']})
