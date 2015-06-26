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
import netaddr
import logging
import random

from neutron.api.v2 import attributes
from neutron.common.config import cfg
from neutron.common import exceptions as q_exc
from neutron.db import models_v2 as qmodels
from neutron.db import l3_db
from neutron.i18n import _
from neutron import manager

from neutron.plugins.common import constants


IPV6_ASSIGNMENT_ATTEMPTS = 1000
LOG = logging.getLogger(__name__)

akanda_opts = [
    cfg.StrOpt('akanda_ipv6_tenant_range',
               default='fdd6:a1fa:cfa8::/48',
               help='IPv6 address prefix'),
    cfg.IntOpt('akanda_ipv6_prefix_length',
               default=64,
               help='Default length of prefix to pre-assign'),
    cfg.ListOpt(
        'akanda_allowed_cidr_ranges',
        default=['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7'],
        help='List of allowed subnet cidrs for non-admin users')
]

cfg.CONF.register_opts(akanda_opts)

SUPPORTED_EXTENSIONS = [
    'dhrouterstatus',
]


def auto_add_ipv6_subnet(f):
    @functools.wraps(f)
    def wrapper(self, context, network):
        LOG.debug('auto_add_ipv6_subnet')
        net = f(self, context, network)
        _add_ipv6_subnet(context, net)
        return net
    return wrapper


def auto_add_subnet_to_router(f):
    @functools.wraps(f)
    def wrapper(self, context, subnet):
        LOG.debug('auto_add_subnet_to_router')
        check_subnet_cidr_meets_policy(context, subnet)
        subnet = f(self, context, subnet)
        _add_subnet_to_router(context, subnet)
        return subnet
    return wrapper


# NOTE(mark): in Havana gateway_ip cannot be updated leaving here if this
# returns in Icehouse.
def sync_subnet_gateway_port(f):
    @functools.wraps(f)
    def wrapper(self, context, id, subnet):
        LOG.debug('sync_subnet_gateway_port')
        retval = f(self, context, id, subnet)
        _update_internal_gateway_port_ip(context, retval)
        return retval
    return wrapper


def check_subnet_cidr_meets_policy(context, subnet):
    if context.is_admin:
        return
    elif getattr(context, '_akanda_auto_add', None):
        return

    net = netaddr.IPNetwork(subnet['subnet']['cidr'])

    for allowed_cidr in cfg.CONF.akanda_allowed_cidr_ranges:
        if net in netaddr.IPNetwork(allowed_cidr):
            return

    else:
        reason = _('Cannot create a subnet that is not within the '
                   'allowed address ranges [%s].' %
                   cfg.CONF.akanda_allowed_cidr_ranges)
        raise q_exc.AdminRequired(reason=reason)


def get_special_ipv6_addrs(ips, mac_address):
    current_ips = set(ips)
    special_ips = set([_generate_ipv6_address('fe80::/64', mac_address)])

    akanda_ipv6_cidr = netaddr.IPNetwork(cfg.CONF.akanda_ipv6_tenant_range)

    for ip in current_ips:
        if '/' not in ip and netaddr.IPAddress(ip) in akanda_ipv6_cidr:
            # Calculate the cidr here because the caller does not have access
            # to request context, subnet or port_id.
            special_ips.add(
                '%s/%s' % (
                    netaddr.IPAddress(
                        netaddr.IPNetwork(
                            '%s/%d' % (ip, cfg.CONF.akanda_ipv6_prefix_length)
                        ).first
                    ),
                    cfg.CONF.akanda_ipv6_prefix_length
                )
            )
    return special_ips - current_ips


def _add_subnet_to_router(context, subnet):
    LOG.debug('_add_subnet_to_router')
    if context.is_admin:
        # admins can manually add their own interfaces
        return

    if not subnet.get('gateway_ip'):
        return

    service_plugin = manager.NeutronManager.get_service_plugins().get(
        constants.L3_ROUTER_NAT)

    router_q = context.session.query(l3_db.Router)
    router_q = router_q.filter_by(tenant_id=context.tenant_id)

    router = router_q.first()

    if not router:
        router_args = {
            'tenant_id': subnet['tenant_id'],
            'name': 'ak-%s' % subnet['tenant_id'],
            'admin_state_up': True
        }
        router = service_plugin.create_router(context, {'router': router_args})
    if not _update_internal_gateway_port_ip(context, router['id'], subnet):
        service_plugin.add_router_interface(context.elevated(),
                                            router['id'],
                                            {'subnet_id': subnet['id']})


def _update_internal_gateway_port_ip(context, router_id, subnet):
    """Attempt to update internal gateway port if one already exists."""
    LOG.debug(
        'setting gateway port IP for router %s on network %s for subnet %s',
        router_id,
        subnet['network_id'],
        subnet['id'],
    )
    if not subnet.get('gateway_ip'):
        LOG.debug('no gateway set for subnet %s, skipping', subnet['id'])
        return

    q = context.session.query(l3_db.RouterPort)
    q = q.join(qmodels.Port)
    q = q.filter(
        l3_db.RouterPort.router_id == router_id,
        l3_db.RouterPort.port_type == l3_db.DEVICE_OWNER_ROUTER_INTF,
        qmodels.Port.network_id == subnet['network_id']

    )
    routerport = q.first()

    if not routerport:
        LOG.info(
            'Unable to find a %s port for router %s on network %s.'
            % ('DEVICE_OWNER_ROUTER_INTF', router_id, subnet['network_id'])
        )
        return

    fixed_ips = [
        {'subnet_id': ip["subnet_id"], 'ip_address': ip["ip_address"]}
        for ip in routerport.port["fixed_ips"]
    ]

    plugin = manager.NeutronManager.get_plugin()
    service_plugin = manager.NeutronManager.get_service_plugins().get(
        constants.L3_ROUTER_NAT)

    for index, ip in enumerate(fixed_ips):
        if ip['subnet_id'] == subnet['id']:
            if not subnet['gateway_ip']:
                del fixed_ips[index]
            elif ip['ip_address'] != subnet['gateway_ip']:
                ip['ip_address'] = subnet['gateway_ip']
            else:
                return True  # nothing to update
            break
    else:
        try:
            service_plugin._check_for_dup_router_subnet(
                context,
                routerport.router,
                subnet['network_id'],
                subnet['id'],
                subnet['cidr']
            )
        except:
            LOG.info(
                ('Subnet %(id)s will not be auto added to router because '
                 '%(gateway_ip)s is already in use by another attached '
                 'network attached to this router.'),
                subnet
            )
            return True  # nothing to add
        fixed_ips.append(
            {'subnet_id': subnet['id'], 'ip_address': subnet['gateway_ip']}
        )

    # we call into the plugin vs updating the db directly because of l3 hooks
    # baked into the plugins.
    port_dict = {'fixed_ips': fixed_ips}
    plugin.update_port(
        context.elevated(),
        routerport.port['id'],
        {'port': port_dict}
    )
    return True


def _add_ipv6_subnet(context, network):

    plugin = manager.NeutronManager.get_plugin()

    try:
        subnet_generator = _ipv6_subnet_generator(
            cfg.CONF.akanda_ipv6_tenant_range,
            cfg.CONF.akanda_ipv6_prefix_length)
    except:
        LOG.exception('Unable able to add tenant IPv6 subnet.')
        return

    remaining = IPV6_ASSIGNMENT_ATTEMPTS

    while remaining:
        remaining -= 1

        candidate_cidr = subnet_generator.next()

        sub_q = context.session.query(qmodels.Subnet)
        sub_q = sub_q.filter_by(cidr=str(candidate_cidr))
        existing = sub_q.all()

        if not existing:
            create_args = {
                'tenant_id': network['tenant_id'],
                'network_id': network['id'],
                'name': '',
                'cidr': str(candidate_cidr),
                'ip_version': candidate_cidr.version,
                'enable_dhcp': True,
                'ipv6_address_mode': 'slaac',
                'ipv6_ra_mode': 'slaac',
                'gateway_ip': attributes.ATTR_NOT_SPECIFIED,
                'dns_nameservers': attributes.ATTR_NOT_SPECIFIED,
                'host_routes': attributes.ATTR_NOT_SPECIFIED,
                'allocation_pools': attributes.ATTR_NOT_SPECIFIED
            }
            context._akanda_auto_add = True
            plugin.create_subnet(context, {'subnet': create_args})
            del context._akanda_auto_add
            break
    else:
        LOG.error('Unable to generate a unique tenant subnet cidr')


def _ipv6_subnet_generator(network_range, prefixlen):
    # coerce prefixlen to stay within bounds
    prefixlen = min(128, prefixlen)

    net = netaddr.IPNetwork(network_range)
    if net.version != 6:
        raise ValueError('Tenant range %s is not a valid IPv6 cidr' %
                         network_range)

    if prefixlen < net.prefixlen:
        raise ValueError('Prefixlen (/%d) must be larger than the network '
                         'range prefixlen (/%s)' % (prefixlen, net.prefixlen))

    rand = random.SystemRandom()
    max_range = 2 ** (prefixlen - net.prefixlen)

    while True:
        rand_bits = rand.randint(0, max_range)

        candidate_cidr = netaddr.IPNetwork(
            netaddr.IPAddress(net.value + (rand_bits << prefixlen)))
        candidate_cidr.prefixlen = prefixlen

        yield candidate_cidr


# Note(rods): we need to keep this method untill the nsx driver won't
# be updated to use neutron's native support for slaac
def _generate_ipv6_address(cidr, mac_address):
    network = netaddr.IPNetwork(cidr)
    tokens = ['%02x' % int(t, 16) for t in mac_address.split(':')]
    eui64 = int(''.join(tokens[0:3] + ['ff', 'fe'] + tokens[3:6]), 16)

    # the bit inversion is required by the RFC
    return str(netaddr.IPAddress(network.value + (eui64 ^ 0x0200000000000000)))
