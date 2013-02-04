# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Nicira, Inc.
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
# @author: Somik Behera, Nicira Networks, Inc.
# @author: Brad Hall, Nicira Networks, Inc.
# @author: Aaron Rosen, Nicira Networks, Inc.

_ = lambda x: x

import hashlib
import logging

import webob.exc

from quantum.api.v2 import attributes
from quantum.api.v2 import base
from quantum.common import constants
from quantum.common import exceptions as q_exc
from quantum.common import rpc as q_rpc
from quantum.common import topics
from quantum.db import api as db
from quantum.db import db_base_plugin_v2
from quantum.db import dhcp_rpc_base
from quantum.db import l3_db
from quantum.db import models_v2
from quantum.db import portsecurity_db
# NOTE: quota_db cannot be removed, it is for db model
from quantum.db import quota_db
from quantum.extensions import l3
from quantum.extensions import portsecurity as psec
from quantum.extensions import providernet as pnet
from quantum.openstack.common import cfg
from quantum.openstack.common import rpc
from quantum import policy
from quantum.plugins.nicira.nicira_nvp_plugin.common import config
from quantum.plugins.nicira.nicira_nvp_plugin.common import (exceptions
                                                             as nvp_exc)
from quantum.plugins.nicira.nicira_nvp_plugin import nicira_db
from quantum.plugins.nicira.nicira_nvp_plugin import NvpApiClient
from quantum.plugins.nicira.nicira_nvp_plugin import nvplib
from quantum.plugins.nicira.nicira_nvp_plugin import nvp_cluster
from quantum.plugins.nicira.nicira_nvp_plugin.nvp_plugin_version import (
    PLUGIN_VERSION)

from akanda.quantum.plugins import decorators as akanda

LOG = logging.getLogger("QuantumPlugin")


# Provider network extension - allowed network types for the NVP Plugin
class NetworkTypes:
    """ Allowed provider network types for the NVP Plugin """
    STT = 'stt'
    GRE = 'gre'
    FLAT = 'flat'
    VLAN = 'vlan'


def parse_config():
    """Parse the supplied plugin configuration.

    :param config: a ConfigParser() object encapsulating nvp.ini.
    :returns: A tuple: (clusters, plugin_config). 'clusters' is a list of
        NVPCluster objects, 'plugin_config' is a dictionary with plugin
        parameters (currently only 'max_lp_per_bridged_ls').
    """
    nvp_options = cfg.CONF.NVP
    nvp_conf = config.ClusterConfigOptions(cfg.CONF)
    cluster_names = config.register_cluster_groups(nvp_conf)
    nvp_conf.log_opt_values(LOG, logging.DEBUG)

    clusters_options = []
    for cluster_name in cluster_names:
        clusters_options.append(
            {'name': cluster_name,
             'default_tz_uuid':
             nvp_conf[cluster_name].default_tz_uuid,
             'nvp_cluster_uuid':
             nvp_conf[cluster_name].nvp_cluster_uuid,
             'nova_zone_id':
             nvp_conf[cluster_name].nova_zone_id,
             'nvp_controller_connection':
             nvp_conf[cluster_name].nvp_controller_connection})
    LOG.debug(_("cluster options:%s"), clusters_options)
    return nvp_options, clusters_options


class NVPRpcCallbacks(dhcp_rpc_base.DhcpRpcCallbackMixin):

    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = '1.0'

    def create_rpc_dispatcher(self):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        return q_rpc.PluginRpcDispatcher([self])


class NvpPluginV2(db_base_plugin_v2.QuantumDbPluginV2,
                  portsecurity_db.PortSecurityDbMixin,
                  l3_db.L3_NAT_db_mixin):
    """
    NvpPluginV2 is a Quantum plugin that provides L2 Virtual Network
    functionality using NVP.
    """

    supported_extension_aliases = [
        "provider", "quotas", "port-security", "router"
    ] + akanda.SUPPORTED_EXTENSIONS

    # Default controller cluster
    # Map nova zones to cluster for easy retrieval
    novazone_cluster_map = {}
    # Default controller cluster (to be used when nova zone id is unspecified)
    default_cluster = None

    provider_network_view = "extension:provider_network:view"
    provider_network_set = "extension:provider_network:set"
    port_security_enabled_create = "create_port:port_security_enabled"
    port_security_enabled_update = "update_port:port_security_enabled"

    def __init__(self, loglevel=None):
        if loglevel:
            logging.basicConfig(level=loglevel)
            nvplib.LOG.setLevel(loglevel)
            NvpApiClient.LOG.setLevel(loglevel)

        # Routines for managing logical ports in NVP
        self._port_drivers = {
            'create': {l3_db.DEVICE_OWNER_FLOATINGIP:
                       self._nvp_create_fip_port,
                       'default': self._nvp_create_port},
            'delete': {l3_db.DEVICE_OWNER_FLOATINGIP:
                       self._nvp_delete_fip_port,
                       'default': self._nvp_delete_port}
        }

        self.nvp_opts, self.clusters_opts = parse_config()
        self.clusters = {}
        for c_opts in self.clusters_opts:
            # Password is guaranteed to be the same across all controllers
            # in the same NVP cluster.
            cluster = nvp_cluster.NVPCluster(c_opts['name'])
            for controller_connection in c_opts['nvp_controller_connection']:
                args = controller_connection.split(':')
                try:
                    args.extend([c_opts['default_tz_uuid'],
                                 c_opts['nvp_cluster_uuid'],
                                 c_opts['nova_zone_id']])
                    cluster.add_controller(*args)
                except Exception:
                    LOG.exception(_("Invalid connection parameters for "
                                    "controller %(conn)s in cluster %(name)s"),
                                  {'conn': controller_connection,
                                   'name': c_opts['name']})
                    raise nvp_exc.NvpInvalidConnection(
                        conn_params=controller_connection)

            api_providers = [(x['ip'], x['port'], True)
                             for x in cluster.controllers]
            cluster.api_client = NvpApiClient.NVPApiHelper(
                api_providers, cluster.user, cluster.password,
                request_timeout=cluster.request_timeout,
                http_timeout=cluster.http_timeout,
                retries=cluster.retries,
                redirects=cluster.redirects,
                concurrent_connections=self.nvp_opts['concurrent_connections'],
                nvp_gen_timeout=self.nvp_opts['nvp_gen_timeout'])

            self.clusters[c_opts['name']] = cluster

        def_cluster_name = self.nvp_opts.default_cluster_name
        if def_cluster_name and def_cluster_name in self.clusters:
            self.default_cluster = self.clusters[def_cluster_name]
        else:
            first_cluster_name = self.clusters.keys()[0]
            if not def_cluster_name:
                LOG.info(_("Default cluster name not specified. "
                           "Using first cluster:%s"), first_cluster_name)
            elif not def_cluster_name in self.clusters:
                LOG.warning(_("Default cluster name %(def_cluster_name)s. "
                              "Using first cluster:%(first_cluster_name)s"),
                            locals())
            # otherwise set 1st cluster as default
            self.default_cluster = self.clusters[first_cluster_name]

        db.configure_db()
        # Extend the fault map
        self._extend_fault_map()
        # Set up RPC interface for DHCP agent
        self.setup_rpc()

    def _build_ip_address_list(self, context, fixed_ips, subnet_ids=None):
        """  Build ip_addresses data structure for logical router port

        No need to perform validation on IPs - this has already been
        done in the l3_db mixin class
        """
        ip_addresses = []
        for ip in fixed_ips:
            if not subnet_ids or (ip['subnet_id'] in subnet_ids):
                subnet = self._get_subnet(context, ip['subnet_id'])
                ip_prefix = '%s/%s' % (ip['ip_address'],
                                       subnet['cidr'].split('/')[1])
                ip_addresses.append(ip_prefix)
        return ip_addresses

    def _get_port_by_device_id(self, context, device_id, device_owner):
        """ Retrieve ports associated with a specific device id.

        Used for retrieving all quantum ports attached to a given router.
        """
        port_qry = context.session.query(models_v2.Port)
        return port_qry.filter_by(
            device_id=device_id,
            device_owner=device_owner,).all()

    def _find_router_subnets_cidrs(self, context, router_id):
        """ Retrieve subnets attached to the specified router """
        ports = self._get_port_by_device_id(context, router_id,
                                            l3_db.DEVICE_OWNER_ROUTER_INTF)
        # No need to check for overlapping CIDRs
        cidrs = []
        for port in ports:
            for ip in port.get('fixed_ips', []):
                cidrs.append(self._get_subnet(context,
                                              ip.subnet_id).cidr)
        return cidrs

    def _nvp_create_port(self, context, port_data):
        """ Driver for creating a logical switch port on NVP platform """
        # FIXME(salvatore-orlando): On the NVP platform we do not really have
        # external networks. So if as user tries and create a "regular" VIF
        # port on an external network we are unable to actually create.
        # However, in order to not break unit tests, we need to still create
        # the DB object and return success
        if self._network_is_external(context, port_data['network_id']):
            LOG.error(_("NVP plugin does not support regular VIF ports on "
                        "external networks. Port %s will be down."),
                      port_data['network_id'])
            # No need to actually update the DB state - the default is down
            return port_data
        # port security extension checks
        (port_security, has_ip) = self._determine_port_security_and_has_ip(
            context, port_data)
        port_data[psec.PORTSECURITY] = port_security
        self._process_port_security_create(context, port_data)
        # provider networking extension checks
        # Fetch the network and network binding from Quantum db
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
                                        port_data[psec.PORTSECURITY])
            nicira_db.add_quantum_nvp_port_mapping(
                context.session, port_data['id'], lport['uuid'])
            d_owner = port_data['device_owner']
            if (not d_owner in (l3_db.DEVICE_OWNER_ROUTER_GW,
                                l3_db.DEVICE_OWNER_ROUTER_INTF)):
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
        # FIXME(salvatore-orlando): On the NVP platform we do not really have
        # external networks. So deleting regular ports from external networks
        # does not make sense. However we cannot raise as this would break
        # unit tests.
        if self._network_is_external(context, port_data['network_id']):
            LOG.error(_("NVP plugin does not support regular VIF ports on "
                        "external networks. Port %s will be down."),
                      port_data['network_id'])
            return

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

    def _find_router_gw_port(self, context, port_data):
        router_id = port_data['device_id']
        cluster = self._find_target_cluster(port_data)
        if not router_id:
            raise q_exc.BadRequest(_("device_id field must be populated in "
                                   "order to create an external gateway "
                                   "port for network %s"),
                                   port_data['network_id'])

        lr_port = nvplib.find_router_gw_port(context, cluster, router_id)
        if not lr_port:
            raise nvp_exc.NvpPluginException(
                err_msg=(_("The gateway port for the router %s "
                           "was not found on the NVP backend")
                         % router_id))
        return lr_port

    def _nvp_create_fip_port(self, context, port_data):
        # As we do not create ports for floating IPs in NVP,
        # this is a no-op driver
        pass

    def _nvp_delete_fip_port(self, context, port_data):
        # As we do not create ports for floating IPs in NVP,
        # this is a no-op driver
        pass

    def _extend_fault_map(self):
        """ Extends the Quantum Fault Map

        Exceptions specific to the NVP Plugin are mapped to standard
        HTTP Exceptions
        """
        base.FAULT_MAP.update({nvp_exc.NvpInvalidNovaZone:
                               webob.exc.HTTPBadRequest,
                               nvp_exc.NvpNoMorePortsException:
                               webob.exc.HTTPBadRequest})

    def _novazone_to_cluster(self, novazone_id):
        if novazone_id in self.novazone_cluster_map:
            return self.novazone_cluster_map[novazone_id]
        LOG.debug(_("Looking for nova zone: %s"), novazone_id)
        for x in self.clusters:
            LOG.debug(_("Looking for nova zone %(novazone_id)s in "
                        "cluster: %(x)s"), locals())
            if x.zone == str(novazone_id):
                self.novazone_cluster_map[x.zone] = x
                return x
        LOG.error(_("Unable to find cluster config entry for nova zone: %s"),
                  novazone_id)
        raise nvp_exc.NvpInvalidNovaZone(nova_zone=novazone_id)

    def _find_target_cluster(self, resource):
        """ Return cluster where configuration should be applied

        If the resource being configured has a paremeter expressing
        the zone id (nova_id), then select corresponding cluster,
        otherwise return default cluster.

        """
        if 'nova_id' in resource:
            return self._novazone_to_cluster(resource['nova_id'])
        else:
            return self.default_cluster

    def _check_view_auth(self, context, resource, action):
        return policy.check(context, action, resource)

    def _enforce_set_auth(self, context, resource, action):
        return policy.enforce(context, action, resource)

    def _handle_provider_create(self, context, attrs):
        # NOTE(salvatore-orlando): This method has been borrowed from
        # the OpenvSwtich plugin, altough changed to match NVP specifics.
        network_type = attrs.get(pnet.NETWORK_TYPE)
        physical_network = attrs.get(pnet.PHYSICAL_NETWORK)
        segmentation_id = attrs.get(pnet.SEGMENTATION_ID)
        network_type_set = attributes.is_attr_set(network_type)
        physical_network_set = attributes.is_attr_set(physical_network)
        segmentation_id_set = attributes.is_attr_set(segmentation_id)
        if not (network_type_set or physical_network_set or
                segmentation_id_set):
            return

        # Authorize before exposing plugin details to client
        self._enforce_set_auth(context, attrs, self.provider_network_set)
        err_msg = None
        if not network_type_set:
            err_msg = _("%s required") % pnet.NETWORK_TYPE
        elif network_type in (NetworkTypes.GRE, NetworkTypes.STT,
                              NetworkTypes.FLAT):
            if segmentation_id_set:
                err_msg = _("Segmentation ID cannot be specified with "
                            "flat network type")
        elif network_type == NetworkTypes.VLAN:
            if not segmentation_id_set:
                err_msg = _("Segmentation ID must be specified with "
                            "vlan network type")
            elif (segmentation_id_set and
                  (segmentation_id < 1 or segmentation_id > 4094)):
                err_msg = _("%s out of range (1 to 4094)") % segmentation_id
            else:
                # Verify segment is not already allocated
                binding = nicira_db.get_network_binding_by_vlanid(
                    context.session, segmentation_id)
                if binding:
                    raise q_exc.VlanIdInUse(vlan_id=segmentation_id,
                                            physical_network=physical_network)
        else:
            err_msg = _("%(net_type_param)s %(net_type_value)s not "
                        "supported") % {'net_type_param': pnet.NETWORK_TYPE,
                                        'net_type_value': network_type}
        if err_msg:
            raise q_exc.InvalidInput(error_message=err_msg)
        # TODO(salvatore-orlando): Validate tranport zone uuid
        # which should be specified in physical_network

    def _extend_network_dict_provider(self, context, network, binding=None):
        if self._check_view_auth(context, network, self.provider_network_view):
            if not binding:
                binding = nicira_db.get_network_binding(context.session,
                                                        network['id'])
            # With NVP plugin 'normal' overlay networks will have no binding
            # TODO(salvatore-orlando) make sure users can specify a distinct
            # tz_uuid as 'provider network' for STT net type
            if binding:
                network[pnet.NETWORK_TYPE] = binding.binding_type
                network[pnet.PHYSICAL_NETWORK] = binding.tz_uuid
                network[pnet.SEGMENTATION_ID] = binding.vlan_id

    def _handle_lswitch_selection(self, cluster, network,
                                  network_binding, max_ports,
                                  allow_extra_lswitches):
        lswitches = nvplib.get_lswitches(cluster, network.id)
        try:
            # TODO find main_ls too!
            return [ls for ls in lswitches
                    if (ls['_relations']['LogicalSwitchStatus']
                        ['lport_count'] < max_ports)].pop(0)
        except IndexError:
            # Too bad, no switch available
            LOG.debug(_("No switch has available ports (%d checked)"),
                      len(lswitches))
        if allow_extra_lswitches:
            main_ls = [ls for ls in lswitches if ls['uuid'] == network.id]
            tag_dict = dict((x['scope'], x['tag']) for x in main_ls[0]['tags'])
            if not 'multi_lswitch' in tag_dict:
                nvplib.update_lswitch(cluster,
                                      main_ls[0]['uuid'],
                                      main_ls[0]['display_name'],
                                      network['tenant_id'],
                                      tags=[{'tag': 'True',
                                             'scope': 'multi_lswitch'}])
            selected_lswitch = nvplib.create_lswitch(
                cluster, network.tenant_id,
                "%s-ext-%s" % (network.name, len(lswitches)),
                network_binding.binding_type,
                network_binding.tz_uuid,
                network_binding.vlan_id,
                network.id)
            return selected_lswitch
        else:
            LOG.error(_("Maximum number of logical ports reached for "
                        "logical network %s"), network.id)
            raise nvp_exc.NvpNoMorePortsException(network=network.id)

    def setup_rpc(self):
        # RPC support for dhcp
        self.topic = topics.PLUGIN
        self.conn = rpc.create_connection(new=True)
        self.dispatcher = NVPRpcCallbacks().create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        # Consume from all consumers in a thread
        self.conn.consume_in_thread()

    def get_all_networks(self, tenant_id, **kwargs):
        networks = []
        for c in self.clusters:
            networks.extend(nvplib.get_all_networks(c, tenant_id, networks))
        LOG.debug(_("get_all_networks() completed for tenant "
                    "%(tenant_id)s: %(networks)s"), locals())
        return networks

    @akanda.auto_add_ipv6_subnet
    def create_network(self, context, network):
        net_data = network['network'].copy()
        # Process the provider network extension
        self._handle_provider_create(context, net_data)
        # Replace ATTR_NOT_SPECIFIED with None before sending to NVP
        for attr, value in network['network'].iteritems():
            if value is attributes.ATTR_NOT_SPECIFIED:
                net_data[attr] = None
        # FIXME(arosen) implement admin_state_up = False in NVP
        if net_data['admin_state_up'] is False:
            LOG.warning(_("Network with admin_state_up=False are not yet "
                          "supported by this plugin. Ignoring setting for "
                          "network %s"), net_data.get('name', '<unknown>'))
        tenant_id = self._get_tenant_id_for_create(context, net_data)
        target_cluster = self._find_target_cluster(net_data)
        # An external network is a Quantum with no equivalent in NVP
        # so do not create a logical switch for an external network
        external = net_data.get(l3.EXTERNAL)
        if not attributes.is_attr_set(external):
            lswitch = nvplib.create_lswitch(
                target_cluster, tenant_id, net_data.get('name'),
                net_data.get(pnet.NETWORK_TYPE),
                net_data.get(pnet.PHYSICAL_NETWORK),
                net_data.get(pnet.SEGMENTATION_ID))
            network['network']['id'] = lswitch['uuid']

        with context.session.begin(subtransactions=True):
            new_net = super(NvpPluginV2, self).create_network(context,
                                                              network)
            self._process_network_create_port_security(context,
                                                       network['network'])
            # DB Operations for setting the network as external
            if net_data.get(pnet.NETWORK_TYPE):
                net_binding = nicira_db.add_network_binding(
                    context.session, new_net['id'],
                    net_data.get(pnet.NETWORK_TYPE),
                    net_data.get(pnet.PHYSICAL_NETWORK),
                    net_data.get(pnet.SEGMENTATION_ID))
                self._extend_network_dict_provider(context, new_net,
                                                   net_binding)
            self._extend_network_port_security_dict(context, new_net)
            self._process_l3_create(context, net_data, new_net['id'])
            self._extend_network_dict_l3(context, new_net)
        return new_net

    def delete_network(self, context, id):
        """
        Deletes the network with the specified network identifier
        belonging to the specified tenant.

        :returns: None
        :raises: exception.NetworkInUse
        :raises: exception.NetworkNotFound
        """
        external = self._network_is_external(context, id)
        # Before deleting ports, ensure the peer of a NVP logical
        # port with a patch attachment is removed too
        port_filter = {'network_id': [id],
                       'device_owner': ['network:router_interface']}
        router_iface_ports = self.get_ports(context, filters=port_filter)
        for port in router_iface_ports:
            nvp_port_id = nicira_db.get_nvp_port_id(context.session,
                                                    port['id'])
            if nvp_port_id:
                port['nvp_port_id'] = nvp_port_id
            else:
                LOG.warning(_("A nvp lport identifier was not found for "
                              "quantum port '%s'"), port['id'])

        super(NvpPluginV2, self).delete_network(context, id)
        # clean up network owned ports
        for port in router_iface_ports:
            try:
                if 'nvp_port_id' in port:
                    nvplib.delete_peer_router_lport(self.default_cluster,
                                                    port['device_id'],
                                                    port['network_id'],
                                                    port['nvp_port_id'])
            except (TypeError, KeyError,
                    NvpApiClient.NvpApiException,
                    NvpApiClient.ResourceNotFound):
                # Do not raise because the issue might as well be that the
                # router has already been deleted, so there would be nothing
                # to do here
                LOG.warning(_("Ignoring exception as this means the peer for "
                              "port '%s' has already been deleted."),
                            nvp_port_id)

        # Do not go to NVP for external networks
        if not external:
            # FIXME(salvatore-orlando): Failures here might lead NVP
            # and quantum state to diverge
            pairs = self._get_lswitch_cluster_pairs(id, context.tenant_id)
            for (cluster, switches) in pairs:
                nvplib.delete_networks(cluster, id, switches)

        LOG.debug(_("delete_network completed for tenant: %s"),
                  context.tenant_id)

    def _get_lswitch_cluster_pairs(self, netw_id, tenant_id):
        """Figure out the set of lswitches on each cluster that maps to this
           network id"""
        pairs = []
        for c in self.clusters.itervalues():
            lswitches = []
            try:
                results = nvplib.get_lswitches(c, netw_id)
                lswitches.extend([ls['uuid'] for ls in results])
            except q_exc.NetworkNotFound:
                continue
            pairs.append((c, lswitches))
        if len(pairs) == 0:
            raise q_exc.NetworkNotFound(net_id=netw_id)
        LOG.debug(_("Returning pairs for network: %s"), pairs)
        return pairs

    def get_network(self, context, id, fields=None):
        """
        Retrieves all attributes of the network, NOT including
        the ports of that network.

        :returns: a sequence of mappings with the following signature:
                    {'id': UUID representing the network.
                     'name': Human-readable name identifying the network.
                     'tenant_id': Owner of network. only admin user
                                  can specify a tenant_id other than its own.
                     'admin_state_up': Sets admin state of network. if down,
                                       network does not forward packets.
                     'status': Indicates whether network is currently
                               operational (limit values to "ACTIVE", "DOWN",
                               "BUILD", and "ERROR"?
                     'subnets': Subnets associated with this network. Plan
                                to allow fully specified subnets as part of
                                network create.
                   }

        :raises: exception.NetworkNotFound
        :raises: exception.QuantumException
        """
        with context.session.begin(subtransactions=True):
            # goto to the plugin DB and fecth the network
            network = self._get_network(context, id)
            net_result = self._make_network_dict(network, None)
            self._extend_network_dict_provider(context, net_result)
            self._extend_network_port_security_dict(context, net_result)

            # if the network is external, do not go to NVP
            if not self._network_is_external(context, id):
                # verify the fabric status of the corresponding
                # logical switch(es) in nvp
                try:
                    # FIXME(salvatore-orlando): This is not going to work
                    # unless we store the nova_id in the database once we'll
                    # enable multiple clusters
                    cluster = self._find_target_cluster(network)
                    lswitches = nvplib.get_lswitches(cluster, id)
                    net_op_status = constants.NET_STATUS_ACTIVE
                    quantum_status = network.status
                    for lswitch in lswitches:
                        relations = lswitch.get('_relations')
                        if relations:
                            lswitch_status = relations.get(
                                'LogicalSwitchStatus'
                            )
                            # FIXME(salvatore-orlando): Being unable to fetch
                            # logical switch status should be an exception.
                            if ((lswitch_status and
                                 not lswitch_status.get('fabric_status'))):
                                net_op_status = constants.NET_STATUS_DOWN
                                break
                    LOG.debug(_("Current network status:%(net_op_status)s; "
                                "Status in Quantum DB:%(quantum_status)s"),
                              locals())
                    if net_op_status != network.status:
                        # update the network status
                        with context.session.begin(subtransactions=True):
                            network.status = net_op_status
                except Exception:
                    err_msg = _("Unable to get logical switches")
                    LOG.exception(err_msg)
                    raise nvp_exc.NvpPluginException(err_msg=err_msg)

        # Don't do field selection here otherwise we won't be able
        # to add provider networks fields
        return self._fields(net_result, fields)

    def get_networks(self, context, filters=None, fields=None):
        nvp_lswitches = {}
        filters = filters or {}
        with context.session.begin(subtransactions=True):
            quantum_lswitches = (
                super(NvpPluginV2, self).get_networks(context, filters))
            for net in quantum_lswitches:
                self._extend_network_dict_provider(context, net)
                self._extend_network_port_security_dict(context, net)
                self._extend_network_dict_l3(context, net)
            quantum_lswitches = self._filter_nets_l3(context,
                                                     quantum_lswitches,
                                                     filters)
        tenant_ids = filters.get('tenant_id')
        filter_fmt = "&tag=%s&tag_scope=os_tid"
        if context.is_admin and not tenant_ids:
            tenant_filter = ""
        else:
            tenant_ids = tenant_ids or [context.tenant_id]
            tenant_filter = ''.join(filter_fmt % tid for tid in tenant_ids)

        lswitch_filters = "uuid,display_name,fabric_status,tags"
        lswitch_url_path = (
            "/ws.v1/lswitch?fields=%s&relations=LogicalSwitchStatus%s"
            % (lswitch_filters, tenant_filter))
        try:
            for c in self.clusters.itervalues():
                nvp_lswitches.update(
                    (s['uuid'], s)
                    for s in nvplib.get_all_query_pages(lswitch_url_path, c)
                )
        except Exception:
            err_msg = _("Unable to get logical switches")
            LOG.exception(err_msg)
            raise nvp_exc.NvpPluginException(err_msg=err_msg)

        # TODO (Aaron) This can be optimized
        if filters.get("id"):
            nvp_lswitches = dict(
                (k, v) for k, v in nvp_lswitches.iteritems()
                if k in set(filters['id'])
            )

        for quantum_lswitch in quantum_lswitches:
            if quantum_lswitch[l3.EXTERNAL]:
                continue
            elif quantum_lswitch['id'] not in nvp_lswitches:
                raise nvp_exc.NvpOutOfSyncException()

            n_sw = nvp_lswitches.pop(quantum_lswitch['id'])

            if n_sw["_relations"]["LogicalSwitchStatus"]["fabric_status"]:
                quantum_lswitch['status'] = constants.NET_STATUS_ACTIVE
            else:
                quantum_lswitch['status'] = constants.NET_STATUS_DOWN
            quantum_lswitch['name'] = n_sw['display_name']
        if nvp_lswitches:
            LOG.warning(_("Found %s logical switches not bound "
                        "to Quantum networks. Quantum and NVP are "
                        "potentially out of sync"), len(nvp_lswitches))

        LOG.debug(_("get_networks() completed for tenant %s"),
                  context.tenant_id)

        return [self._fields(sw, fields) for sw in quantum_lswitches]

    def update_network(self, context, id, network):
        if network["network"].get("admin_state_up"):
            if network['network']["admin_state_up"] is False:
                raise q_exc.NotImplementedError(_("admin_state_up=False "
                                                  "networks are not "
                                                  "supported."))
        pairs = self._get_lswitch_cluster_pairs(id, context.tenant_id)

        #Only field to update in NVP is name
        if network['network'].get("name"):
            for (cluster, switches) in pairs:
                for switch in switches:
                    nvplib.update_lswitch(cluster, switch,
                                          network['network']['name'])

        LOG.debug(_("update_network() completed for tenant: %s"),
                  context.tenant_id)
        with context.session.begin(subtransactions=True):
            net = super(NvpPluginV2, self).update_network(context, id, network)
            self._process_l3_update(context, network['network'], id)
            self._extend_network_dict_provider(context, net)
            self._extend_network_dict_l3(context, net)
        return net

    @akanda.auto_add_subnet_to_router
    def create_subnet(self, context, subnet):
        return super(NvpPluginV2, self).create_subnet(context, subnet)

    @akanda.sync_subnet_gateway_port
    def update_subnet(self, context, id, subnet):
        return super(NvpPluginV2, self).update_subnet(context, id, subnet)

    def get_ports(self, context, filters=None, fields=None):
        quantum_lports = super(NvpPluginV2, self).get_ports(context, filters)
        if ((filters.get('network_id') and
             self._network_is_external(context, filters['network_id'][0]))):
            # Do not perform check on NVP platform
            return quantum_lports

        vm_filter = ""
        tenant_filter = ""
        # This is used when calling delete_network. Quantum checks to see if
        # the network has any ports.
        if filters.get("network_id"):
            # FIXME (Aaron) If we get more than one network_id this won't work
            lswitch = filters["network_id"][0]
        else:
            lswitch = "*"

        vm_filter = ''.join(
            "&%stag_scope=vm_id&tag=%s" % hashlib.sha1(vm_id).hexdigest()
            for vm_id in filters.get('devive_id', [])
        )

        tenant_filter = ''.join(
            "&%stag_scope=os_id&tag=%s" % tenant_id
            for tenant_id in filters.get('tenant_id', [])
        )

        nvp_lports = {}

        lport_fields_str = ("tags,admin_status_enabled,display_name,"
                            "fabric_status_up")
        try:
            for c in self.clusters.itervalues():
                lport_query_path = (
                    "/ws.v1/lswitch/%s/lport?fields=%s%s%s"
                    "&tag_scope=q_port_id&relations=LogicalPortStatus" %
                    (lswitch, lport_fields_str, vm_filter, tenant_filter))

                ports = nvplib.get_all_query_pages(lport_query_path, c)
                if ports:
                    for port in ports:
                        for tag in port["tags"]:
                            if tag["scope"] == "q_port_id":
                                nvp_lports[tag["tag"]] = port

        except Exception:
            err_msg = _("Unable to get ports")
            LOG.exception(err_msg)
            raise nvp_exc.NvpPluginException(err_msg=err_msg)

        lports = []
        for quantum_lport in quantum_lports:
            # if a quantum port is not found in NVP, this migth be because
            # such port is not mapped to a logical switch - ie: floating ip
            if quantum_lport['device_owner'] in (l3_db.DEVICE_OWNER_FLOATINGIP,
                                                 l3_db.DEVICE_OWNER_ROUTER_GW):
                lports.append(quantum_lport)
                continue
            try:
                quantum_lport["admin_state_up"] = (
                    nvp_lports[quantum_lport["id"]]["admin_status_enabled"])

                quantum_lport["name"] = (
                    nvp_lports[quantum_lport["id"]]["display_name"])

                if (nvp_lports[quantum_lport["id"]]
                        ["_relations"]
                        ["LogicalPortStatus"]
                        ["fabric_status_up"]):
                    quantum_lport["status"] = constants.PORT_STATUS_ACTIVE
                else:
                    quantum_lport["status"] = constants.PORT_STATUS_DOWN

                del nvp_lports[quantum_lport["id"]]
                lports.append(quantum_lport)
            except KeyError:

                LOG.debug(_("Quantum logical port %s was not found on NVP"),
                          quantum_lport['id'])

        # do not make the case in which ports are found in NVP
        # but not in Quantum catastrophic.
        if len(nvp_lports):
            LOG.warning(_("Found %s logical ports not bound "
                          "to Quantum ports. Quantum and NVP are "
                          "potentially out of sync"), len(nvp_lports))

        return [self._fields(p, fields) for p in lports]

    def create_port(self, context, port):
        # If PORTSECURITY is not the default value ATTR_NOT_SPECIFIED
        # then we pass the port to the policy engine. The reason why we don't
        # pass the value to the policy engine when the port is
        # ATTR_NOT_SPECIFIED is for the case where a port is created on a
        # shared network that is not owned by the tenant.
        # TODO(arosen) fix policy engine to do this for us automatically.
        if attributes.is_attr_set(port['port'].get(psec.PORTSECURITY)):
            self._enforce_set_auth(context, port,
                                   self.port_security_enabled_create)
        port_data = port['port']
        with context.session.begin(subtransactions=True):
            # Set admin_state_up False since not created in NVP set
            # TODO(salvatore-orlando) : verify whether subtransactions can help
            # us avoiding multiple operations on the db. This might also allow
            # us to use the same identifier for the NVP and the Quantum port
            # Set admin_state_up False since not created in NVP yet
            requested_admin_state = port["port"]["admin_state_up"]
            port["port"]["admin_state_up"] = False

            # First we allocate port in quantum database
            quantum_db = super(NvpPluginV2, self).create_port(context, port)
            # Update fields obtained from quantum db (eg: MAC address)
            port["port"].update(quantum_db)

            # port security extension checks
            (port_security, has_ip) = self._determine_port_security_and_has_ip(
                context, port_data)
            port_data[psec.PORTSECURITY] = port_security
            self._process_port_security_create(context, port_data)
            # provider networking extension checks
            # Fetch the network and network binding from Quantum db
            try:
                port_data = port['port'].copy()
                port_data['admin_state_up'] = requested_admin_state
                port_create_func = self._port_drivers['create'].get(
                    port_data['device_owner'],
                    self._port_drivers['create']['default'])

                port_create_func(context, port_data)
            except Exception as e:
                # failed to create port in NVP delete port from quantum_db
                # FIXME (arosen) or the plugin_interface call failed in which
                # case we need to garbage collect the left over port in nvp.
                err_msg = _("An exception occured while plugging the "
                            "interface in NVP for port %s") % port_data['id']
                LOG.exception(err_msg)
                try:
                    super(NvpPluginV2, self).delete_port(context,
                                                         port['port']['id'])
                except q_exc.PortNotFound:
                    LOG.warning(_("The delete port operation failed for %s. "
                                  "This means the port was already deleted"),
                                port['port']['id'])
                raise e

            LOG.debug(_("create_port completed on NVP for tenant "
                        "%(tenant_id)s: (%(id)s)"), port_data)

            self._extend_port_port_security_dict(context, port_data)
        return port_data

    def update_port(self, context, id, port):
        self._enforce_set_auth(context, port,
                               self.port_security_enabled_update)
        tenant_id = self._get_tenant_id_for_create(context, port)
        with context.session.begin(subtransactions=True):
            ret_port = super(NvpPluginV2, self).update_port(
                context, id, port)
            # copy values over
            ret_port.update(port['port'])

            # Handle port security
            if psec.PORTSECURITY in port['port']:
                self._update_port_security_binding(
                    context, id, ret_port[psec.PORTSECURITY])
            # populate with value
            else:
                ret_port[psec.PORTSECURITY] = self._get_port_security_binding(
                    context, id)

            port_nvp, cluster = (
                nvplib.get_port_by_quantum_tag(self.clusters.itervalues(),
                                               ret_port["network_id"], id))
            LOG.debug(_("Update port request: %s"), port)
            nvplib.update_port(cluster, ret_port['network_id'],
                               port_nvp['uuid'], id, tenant_id,
                               ret_port['name'], ret_port['device_id'],
                               ret_port['admin_state_up'],
                               ret_port['mac_address'],
                               ret_port['fixed_ips'],
                               ret_port[psec.PORTSECURITY])

        # Update the port status from nvp. If we fail here hide it since
        # the port was successfully updated but we were not able to retrieve
        # the status.
        try:
            ret_port['status'] = nvplib.get_port_status(
                cluster, ret_port['network_id'], port_nvp['uuid'])
        except:
            LOG.warn(_("Unable to retrieve port status for: %s."),
                     port_nvp['uuid'])
        return ret_port

    def delete_port(self, context, id, l3_port_check=True):
        # if needed, check to see if this is a port owned by
        # a l3 router.  If so, we should prevent deletion here
        if l3_port_check:
            self.prevent_l3_port_deletion(context, id)
        quantum_db_port = self._get_port(context, id)
        port_delete_func = self._port_drivers['delete'].get(
            quantum_db_port.device_owner,
            self._port_drivers['delete']['default'])

        port_delete_func(context, quantum_db_port)
        self.disassociate_floatingips(context, id)
        with context.session.begin(subtransactions=True):
            super(NvpPluginV2, self).delete_port(context, id)

    def get_port(self, context, id, fields=None):
        quantum_db_port = super(NvpPluginV2, self).get_port(context,
                                                            id, fields)
        if self._network_is_external(context, quantum_db_port['network_id']):
            return quantum_db_port

        nvp_id = nicira_db.get_nvp_port_id(context.session, id)
        #TODO: pass the appropriate cluster here
        port = nvplib.get_logical_port_status(
            self.default_cluster, quantum_db_port['network_id'], nvp_id)
        quantum_db_port["admin_state_up"] = port["admin_status_enabled"]
        if port["fabric_status_up"]:
            quantum_db_port["status"] = constants.PORT_STATUS_ACTIVE
        else:
            quantum_db_port["status"] = constants.PORT_STATUS_DOWN

        return quantum_db_port

    def get_plugin_version(self):
        return PLUGIN_VERSION
