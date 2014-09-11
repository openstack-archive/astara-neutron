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

import functools
import os

from neutron.common import topics
from neutron.db import l3_db
from neutron.db import l3_rpc_base as l3_rpc
from neutron.db import api as db
from neutron.extensions import portbindings as pbin
from neutron.openstack.common import log as logging
from neutron.openstack.common import rpc
from neutron.plugins.nicira.common import sync as nvp_sync
from neutron.plugins.nicira.dhcp_meta import rpc as nvp_rpc
from neutron.plugins.nicira.NeutronPlugin import nicira_db
from neutron.plugins.nicira import NeutronPlugin as nvp
from oslo.config import cfg

from akanda.neutron.plugins import decorators as akanda
from akanda.neutron.plugins import floatingip

LOG = logging.getLogger("NeutronPlugin")
akanda.monkey_patch_ipv6_generator()

NVP_EXT_PATH = os.path.join(os.path.dirname(__file__), 'extensions')


def akanda_nvp_ipv6_port_security_wrapper(f):
    @functools.wraps(f)
    def wrapper(lport_obj, mac_address, fixed_ips, port_security_enabled,
                security_profiles, queue_id, mac_learning_enabled,
                allowed_address_pairs):

        f(lport_obj, mac_address, fixed_ips, port_security_enabled,
          security_profiles, queue_id, mac_learning_enabled,
          allowed_address_pairs)

        # evaulate the state so that we only override the value when enabled
        # otherwise we are preserving the underlying behavior of the NVP plugin
        if port_security_enabled:
            # hotfix to enable egress mulitcast
            lport_obj['allow_egress_multicast'] = True

            # TODO(mark): investigate moving away from this an wrapping
            # (create|update)_port
            # add link-local and subnet cidr for IPv6 temp addresses
            special_ipv6_addrs = akanda.get_special_ipv6_addrs(
                (p['ip_address'] for p in lport_obj['allowed_address_pairs']),
                mac_address
            )

            lport_obj['allowed_address_pairs'].extend(
                {'mac_address': mac_address, 'ip_address': addr}
                for addr in special_ipv6_addrs
            )

    return wrapper


nvp.nvplib._configure_extensions = akanda_nvp_ipv6_port_security_wrapper(
    nvp.nvplib._configure_extensions
)


class AkandaNvpRpcCallbacks(l3_rpc.L3RpcCallbackMixin,
                            nvp_rpc.NVPRpcCallbacks):
    pass


class NvpSynchronizer(nvp_sync.NvpSynchronizer):
    """
    The NvpSynchronizer class in Neutron runs a synchronization thread to
    sync nvp objects with neutron objects. Since we don't use nvp's routers
    the sync was failing making neutron showing all the routers like if the
    were in Error state. To fix this behaviour we override the two methods
    responsible for the routers synchronization in the NvpSynchronizer class
    to be a noop

    """
    def _synchronize_lrouters(self, *args, **kwargs):
        pass

    def synchronize_router(self, *args, **kwargs):
        pass


class NvpPluginV2(floatingip.ExplicitFloatingIPAllocationMixin,
                  nvp.NvpPluginV2):
    """
    NvpPluginV2 is a Neutron plugin that provides L2 Virtual Network
    functionality using NVP.
    """
    supported_extension_aliases = (
        nvp.NvpPluginV2.supported_extension_aliases +
        akanda.SUPPORTED_EXTENSIONS
    )

    def __init__(self):
        super(NvpPluginV2, self).__init__()

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

        # ---------------------------------------------------------------------
        # Note(rods):
        # This code has been copied from our custom quantum repo
        # https://github.com/dreamhost/quantum/blob/akanda_h2/neutron/plugins/
        # nicira/NeutronPlugin.py#L188-L215
        # We added this code with the only purpose to make the nsx driver use
        # our subclass of the NvpSynchronizer object.
        #
        # DHC-2385
        #

        # If no api_extensions_path is provided set the following
        if not cfg.CONF.api_extensions_path:
            cfg.CONF.set_override('api_extensions_path', NVP_EXT_PATH)
        self.nvp_opts = cfg.CONF.NVP
        self.nvp_sync_opts = cfg.CONF.NVP_SYNC
        self.cluster = nvp.create_nvp_cluster(
            cfg.CONF,
            self.nvp_opts.concurrent_connections,
            self.nvp_opts.nvp_gen_timeout
        )

        self.base_binding_dict = {
            pbin.VIF_TYPE: pbin.VIF_TYPE_OVS,
            pbin.CAPABILITIES: {
                pbin.CAP_PORT_FILTER:
                'security-group' in self.supported_extension_aliases}}

        db.configure_db()
        self._extend_fault_map()
        self.setup_dhcpmeta_access()
        # Set this flag to false as the default gateway has not
        # been yet updated from the config file
        self._is_default_net_gw_in_sync = False

        # Note(rods):
        # The following line includes the only change we made to the original
        # code

        # - self._synchronizer = sync.NvpSynchronizer(
        # + self._synchronizer = NvpSynchronizer(

        # Create a synchronizer instance for backend sync
        self._synchronizer = NvpSynchronizer(
            self, self.cluster,
            self.nvp_sync_opts.state_sync_interval,
            self.nvp_sync_opts.min_sync_req_delay,
            self.nvp_sync_opts.min_chunk_size,
            self.nvp_sync_opts.max_random_sync_delay)
        # ---------------------------------------------------------------------

    def setup_dhcpmeta_access(self):
        # Ok, so we're going to add L3 here too with the DHCP
        self.conn = rpc.create_connection(new=True)
        self.conn.create_consumer(
            topics.PLUGIN,
            AkandaNvpRpcCallbacks().create_rpc_dispatcher(),
            fanout=False
        )

        # Consume from all consumers in a thread
        self.conn.consume_in_thread()

        self.handle_network_dhcp_access_delegate = noop
        self.handle_port_dhcp_access_delegate = noop
        self.handle_port_metadata_access_delegate = noop
        self.handle_metadata_access_delegate = noop

    @akanda.auto_add_other_resources
    @akanda.auto_add_ipv6_subnet
    def create_network(self, context, network):
        return super(NvpPluginV2, self).create_network(context, network)

    @akanda.auto_add_subnet_to_router
    def create_subnet(self, context, subnet):
        return super(NvpPluginV2, self).create_subnet(context, subnet)

    # we need to use original versions l3_db.L3_NAT_db_mixin mixin and not
    # NVP versions that manage NVP's logical router

    create_router = l3_db.L3_NAT_db_mixin.create_router
    update_router = l3_db.L3_NAT_db_mixin.update_router
    delete_router = l3_db.L3_NAT_db_mixin.delete_router
    get_router = l3_db.L3_NAT_db_mixin.get_router
    get_routers = l3_db.L3_NAT_db_mixin.get_routers
    add_router_interface = l3_db.L3_NAT_db_mixin.add_router_interface
    remove_router_interface = l3_db.L3_NAT_db_mixin.remove_router_interface
    update_floatingip = l3_db.L3_NAT_db_mixin.update_floatingip
    delete_floatingip = l3_db.L3_NAT_db_mixin.delete_floatingip
    get_floatingip = l3_db.L3_NAT_db_mixin.get_floatingip
    get_floatings = l3_db.L3_NAT_db_mixin.get_floatingips
    _update_fip_assoc = l3_db.L3_NAT_db_mixin._update_fip_assoc
    _update_router_gw_info = l3_db.L3_NAT_db_mixin._update_router_gw_info
    disassociate_floatingips = l3_db.L3_NAT_db_mixin.disassociate_floatingips

    def _ensure_metadata_host_route(self, *args, **kwargs):
        """ Akanda metadata services are provided by router so make no-op/"""
        pass

    def _nvp_create_port(self, context, port_data):
        """ Driver for creating a logical switch port on NVP platform """
        # NOTE(mark): Akanda does want ports for external networks so
        # this method is basically same with external check removed and
        # the auto plugging of router ports
        lport = None
        selected_lswitch = None
        try:
            selected_lswitch = self._nvp_find_lswitch_for_port(context,
                                                               port_data)
            lport = self._nvp_create_port_helper(self.cluster,
                                                 selected_lswitch['uuid'],
                                                 port_data,
                                                 True)
            nicira_db.add_neutron_nvp_port_mapping(
                context.session, port_data['id'], lport['uuid'])

            nvp.nvplib.plug_interface(self.cluster, selected_lswitch['uuid'],
                                      lport['uuid'], "VifAttachment",
                                      port_data['id'])

            LOG.debug(_("_nvp_create_port completed for port %(name)s "
                        "on network %(network_id)s. The new port id is "
                        "%(id)s."), port_data)
        except (nvp.NvpApiClient.NvpApiException, nvp.q_exc.NeutronException):
            self._handle_create_port_exception(
                context, port_data['id'],
                selected_lswitch and selected_lswitch['uuid'],
                lport and lport['uuid'])

    def _nvp_delete_port(self, context, port_data):
        # NOTE(mark): Akanda does want ports for external networks so
        # this method is basically same with external check removed
        nvp_port_id = self._nvp_get_port_id(context, self.cluster,
                                            port_data)
        if not nvp_port_id:
            LOG.debug(_("Port '%s' was already deleted on NVP platform"), id)
            return
        # TODO(bgh): if this is a bridged network and the lswitch we just got
        # back will have zero ports after the delete we should garbage collect
        # the lswitch.
        try:
            nvp.nvplib.delete_port(self.cluster,
                                   port_data['network_id'],
                                   nvp_port_id)
            LOG.debug(_("_nvp_delete_port completed for port %(port_id)s "
                        "on network %(net_id)s"),
                      {'port_id': port_data['id'],
                       'net_id': port_data['network_id']})

        except nvp.q_exc.NotFound:
            LOG.warning(_("Port %s not found in NVP"), port_data['id'])


def noop(*args, **kwargs):
    pass
