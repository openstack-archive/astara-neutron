import functools
import logging
import random

import netaddr
from quantum.api.v2 import attributes
from quantum.common.config import cfg
from quantum.common import exceptions as q_exc
from quantum.db import db_base_plugin_v2
from quantum.db import models_v2 as qmodels
from quantum.db import l3_db
from quantum import manager
from sqlalchemy.orm import exc

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

# Provide a list of the default port aliases to be
# created for a tenant.
# FIXME(dhellmann): This list should come from
# a configuration file somewhere.
DEFAULT_PORT_ALIASES = [
    ('tcp', 0, 'Any TCP'),
    ('udp', 0, 'Any UDP'),
    ('tcp', 22, 'ssh'),
    ('udp', 53, 'DNS'),
    ('tcp', 80, 'HTTP'),
    ('tcp', 443, 'HTTPS'),
]

# Provide a list of the default address entries
# to be created for a tenant.
# FIXME(dhellmann): This list should come from
# a configuration file somewhere.
DEFAULT_ADDRESS_GROUPS = [
    ('Any', [('Any', '0.0.0.0/0')]),
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
        _add_subnet_to_router(context, subnet)
        return subnet
    return wrapper


def sync_subnet_gateway_port(f):
    @functools.wraps(f)
    def wrapper(self, context, id, subnet):
        retval = f(self, context, id, subnet)
        _update_internal_gateway_port_ip(context, retval)
        return retval
    return wrapper


def auto_add_other_resources(f):
    @functools.wraps(f)
    def wrapper(self, context, *args, **kwargs):
        retval = f(self, context, *args, **kwargs)
        if not context.is_admin:
            _auto_add_port_aliases(context)
            _auto_add_address_groups(context)
        return retval
    return wrapper


def monkey_patch_ipv6_generator():
    cls = db_base_plugin_v2.QuantumDbPluginV2
    cls._generate_mac = _wrap_generate_mac(cls._generate_mac)
    cls._generate_ip = _wrap_generate_ip(cls, cls._generate_ip)


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

    if not _update_internal_gateway_port_ip(context, router['id'], subnet):
        plugin.add_router_interface(context.elevated(),
                                    router['id'],
                                    {'subnet_id': subnet['id']})


def _update_internal_gateway_port_ip(context, router_id, subnet):
    """Attempt to update internal gateway port if one already exists."""
    LOG.debug('setting gateway port IP for router %s on network %s for subnet %s',
              router_id, subnet['network_id'], subnet['id'])
    if not subnet.get('gateway_ip'):
        LOG.debug('no gateway set for subnet %s, skipping', subnet)
        return

    q = context.session.query(l3_db.RouterPort, qmodels.Port)
    q = q.filter(l3_db.RouterPort.router_id == router_id)
    q = q.filter(l3_db.RouterPort.port_type == l3_db.DEVICE_OWNER_ROUTER_INTF)
    q = q.filter(qmodels.Port.network_id == subnet['network_id'])
    routerport, port = q.first() or (None, None)

    if not routerport:
        LOG.exception('Unable to find router for port %s on network %s.'
                      % (router_id, subnet['network_id']))
        return

    fixed_ips = [
        {'subnet_id': ip["subnet_id"], 'ip_address': ip["ip_address"]}
        for ip in port["fixed_ips"]
    ]

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
        fixed_ips.append(
            {'subnet_id': subnet['id'], 'ip_address': subnet['gateway_ip']}
        )

    # we call into the plugin vs updating the db directly because of l3 hooks
    # baked into the plugins.
    plugin = manager.QuantumManager.get_plugin()
    port_dict = {'fixed_ips': fixed_ips}
    plugin.update_port(context.elevated(), port['id'], {'port': port_dict})
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


def _wrap_generate_mac(f):
    """ Adds mac_address to context object instead of patch Quantum.

    Annotating the object requires a less invasive change until upstream
    can be fixed in Havana.  This version works in concert with
    _generate_ip below to make IPv6 stateless addresses correctly.
    """

    @staticmethod
    @functools.wraps(f)
    def wrapper(context, network_id):
        mac_addr = f(context, network_id)
        context.mac_address = mac_addr
        return mac_addr
    return wrapper


def _wrap_generate_ip(cls, f):
    """Generate an IP address.

    The IP address will be generated from one of the subnets defined on
    the network.

    NOTE: This method is intended to patch a private method on the
    Quantum base plugin.  The method prefers to generate an IP from large IPv6
    subnets.  If a suitable subnet cannot be found, the method will fallback
    to the original implementation.
    """

    @staticmethod
    @functools.wraps(f)
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


def _auto_add_address_groups(context):
    """Create default address groups if the tenant does not have them. """
    for ag_name, entries in DEFAULT_ADDRESS_GROUPS:
        ag_q = context.session.query(akmodels.AddressGroup)
        ag_q = ag_q.filter_by(
            tenant_id=context.tenant_id,
            name=ag_name,
        )
        try:
            address_group = ag_q.one()
        except exc.NoResultFound:
            with context.session.begin(subtransactions=True):
                address_group = akmodels.AddressGroup(
                    name=ag_name,
                    tenant_id=context.tenant_id,
                )
                context.session.add(address_group)
                LOG.debug('Created default address group %s',
                          address_group.name)

        for entry_name, cidr in entries:
            entry_q = context.session.query(akmodels.AddressEntry)
            entry_q = entry_q.filter_by(
                group=address_group,
                name=entry_name,
                cidr=cidr,
            )
            try:
                entry_q.one()
            except exc.NoResultFound:
                with context.session.begin(subtransactions=True):
                    entry = akmodels.AddressEntry(
                        name=entry_name,
                        group=address_group,
                        cidr=cidr,
                        tenant_id=context.tenant_id,
                    )
                    context.session.add(entry)
                    LOG.debug(
                        'Created default entry for %s in address group %s',
                        cidr, address_group.name)


def _auto_add_port_aliases(context):
    """Create the default port aliases for the current tenant, if
    they don't already exist.
    """
    for protocol, port, name in DEFAULT_PORT_ALIASES:
        pa_q = context.session.query(akmodels.PortAlias)
        pa_q = pa_q.filter_by(
            tenant_id=context.tenant_id,
            port=port,
            protocol=protocol,
        )
        try:
            pa_q.one()
        except exc.NoResultFound:
            with context.session.begin(subtransactions=True):
                alias = akmodels.PortAlias(
                    name=name,
                    protocol=protocol,
                    port=port,
                    tenant_id=context.tenant_id,
                )
                context.session.add(alias)
                LOG.debug('Created default port alias %s', alias.name)
