import functools
import logging
import random

import netaddr
from quantum.api.v2 import attributes
from quantum.common import exceptions as q_exc
from quantum.db import db_base_plugin_v2
from quantum.db import models_v2 as qmodels
from quantum.db import l3_db
from quantum import manager
from quantum.openstack.common import cfg
from sqlalchemy.orm import exc

# this import is here to ensure that models are loaded by SQLAlchemy
from akanda.quantum.db import models_v2 as akmodels

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
        default=['10.0.0.8/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7'],
        help='List of allowed subnet cidrs for non-admin users')
]

cfg.CONF.register_opts(akanda_opts)

SUPPORTED_EXTENSIONS = [
    'dhportforward', 'dhaddressgroup', 'dhaddressentry', 'dhfilterrule',
    'dhportalias'
]


def auto_add_ipv6_subnet(f):
    @functools.wraps(f)
    def wrapper(self, context, network):
        net = f(self, context, network)
        _add_ipv6_subnet(context, net)
        return net
    return wrapper


def auto_add_subnet_to_router(f):
    @functools.wraps(f)
    def wrapper(self, context, subnet):
        check_subnet_cidr_meets_policy(context, subnet)
        subnet = f(self, context, subnet)
        if subnet['ip_version'] == 4:
            _add_subnet_to_router(context, subnet)
        return subnet
    return wrapper


def sync_subnet_gateway_port(f):
    @functools.wraps(f)
    def wrapper(self, ontext, id, subnet):
        retval = f(self, context, id, subnet)
        _update_internal_gateway_port_ip(context, retval)
        return retval
    return wrapper


def monkey_patch_ipv6_generator():
    cls = db_base_plugin_v2.QuantumDbPluginV2
    cls._generate_mac = _wrap_generate_mac(cls._generate_mac)
    cls._generate_ip = _wrap_generate_ip(cls, cls._generate_ip)


def check_subnet_cidr_meets_policy(context, subnet):
    if context.is_admin:
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


def _add_subnet_to_router(context, subnet):
    if context.is_admin:
        # admins can manually add their own interfaces
        return

    if not subnet.get('gateway_ip'):
        return

    plugin = manager.QuantumManager.get_plugin()

    router_q = context.session.query(l3_db.Router)
    router_q = router_q.filter_by(tenant_id=context.tenant_id)

    router = router_q.first()

    if not router:
        router_args = {'tenant_id': context.tenant_id,
                       'name': 'ak-%s' % context.tenant_id,
                       'admin_state_up': True}
        router = plugin.create_router(context, {'router': router_args})

    if not _update_internal_gateway_port_ip(context, subnet):
        plugin.add_router_interface(context.elevated(),
                                    router['id'],
                                    {'subnet_id': subnet['id']})


def _update_internal_gateway_port_ip(context, subnet):
    if not subnet.get('gateway_ip'):
        return

    plugin = manager.QuantumManager.get_plugin()

    filters = {
        'device_owner': [l3_db.DEVICE_OWNER_ROUTER_INTF],
        'network_id': [subnet['network_id']]
    }
    ports = plugin.get_ports(context, filters=filters)

    for port in ports:
        for fixed_ip in port['fixed_ips']:
            if fixed_ip['subnet_id'] == subnet['id']:
                fixed_ip['ip_address'] = subnet['gateway_ip']
                plugin.update_port(context.elevated(),
                                   port['id'],
                                   {'port': port})
                return True
    if ports:
        # append subnet to first port
        port = ports[0]
        port['fixed_ips'].append({'subnet_id': subnet['id'],
                                  'ip_address': subnet['gateway_ip']})
        plugin.update_port(context.elevated(),
                           port['id'],
                           {'port': port})
        return True


def _add_ipv6_subnet(context, network):

    plugin = manager.QuantumManager.get_plugin()

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
                'network_id': network['id'],
                'name': '',
                'cidr': str(candidate_cidr),
                'ip_version': candidate_cidr.version,
                'enable_dhcp': False,
                'gateway_ip': attributes.ATTR_NOT_SPECIFIED,
                'dns_nameservers': attributes.ATTR_NOT_SPECIFIED,
                'host_routes': attributes.ATTR_NOT_SPECIFIED,
                'allocation_pools': attributes.ATTR_NOT_SPECIFIED
            }
            plugin.create_subnet(context, {'subnet': create_args})
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


def _wrap_generate_mac(f):
    """ Adds mac_address to context object instead of patch Quantum.

    Annotating the object requires a less invasive change until upstream
    can be fixed in Havana.  This version works in concert with
    _generate_ip below to make IPv6 stateless addresses correctly.
    """

    @staticmethod
    def wrapper(context, network_id):
        mac_addr = f(context, network_id)
        context.mac_address = mac_addr
        return mac_addr
    return wrapper


def _wrap_generate_ip(cls, f):
    """Generate an IP address.

    The IP address will be generated from one of the subnets defined on
    the network.
    """

    @staticmethod
    def wrapper(context, subnets):
        if hasattr(context, 'mac_address'):
            for subnet in subnets:
                if subnet['ip_version'] != 6:
                    continue
                elif netaddr.IPNetwork(subnet['cidr']).prefixlen <= 64:
                    network_id = subnet['network_id']
                    subnet_id = subnet['id']
                    candidate = _generate_ipv6_address(
                        subnet['cidr'],
                        context.mac_address
                    )

                    if cls._check_unique_ip(context, network_id, subnet_id,
                                            candidate):
                        cls._allocate_specific_ip(
                            context,
                            subnet_id,
                            candidate
                        )
                        return {
                            'ip_address': candidate,
                            'subnet_id': subnet_id
                        }

        # otherwise fallback to built-in versio
        return f(context, subnets)
    return wrapper


def _generate_ipv6_address(cidr, mac_address):
    network = netaddr.IPNetwork(cidr)
    tokens = ['%02x' % int(t, 16) for t in mac_address.split(':')]
    eui64 = int(''.join(tokens[0:3] + ['ff', 'fe'] + tokens[3:6]), 16)

    # the bit inversion is required by the RFC
    return str(netaddr.IPAddress(network.value + (eui64 ^ 0x0200000000000000)))
