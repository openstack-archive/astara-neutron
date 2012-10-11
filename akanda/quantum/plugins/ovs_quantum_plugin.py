import logging
import random

import netaddr
from quantum.api.v2 import attributes
from quantum.common import exceptions as q_exc
from quantum.db import models_v2 as qmodels
from quantum.db import l3_db
from quantum.openstack.common import cfg
from quantum.plugins.openvswitch import ovs_quantum_plugin
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
    cfg.ListOpt('akanda_allowed_cidr_ranges',
        default=['10.0.0.8/8', '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7'],
        help='List of allowed subnet cidrs for non-admin users')
]

cfg.CONF.register_opts(akanda_opts)



class OVSQuantumPluginV2(ovs_quantum_plugin.OVSQuantumPluginV2):
    supported_extension_aliases = (
        ovs_quantum_plugin.OVSQuantumPluginV2.supported_extension_aliases +
        ["dhportforward", "dhaddressgroup", "dhaddressentry",
         "dhfilterrule", "dhportalias"])


    def create_network(self, context, network):
        retval = super(OVSQuantumPluginV2, self).create_network(context,
                                                                network)
        # auto create IPv6 network
        self._akanda_add_ipv6_subnet(context, retval)
        return retval

    def update_network(self, context, id, network):
        retval = super(OVSQuantumPluginV2, self).update_network(context,
                                                                id,
                                                                network)
        # TODO: need to remove ports from router when state is down?
        return retval

    def create_subnet(self, context, subnet):
        # ensure cidr is allowed v4:RFC1918 v6:ULA for non-admins
        if not context.is_admin:
            net = netaddr.IPNetwork(subnet['subnet']['cidr'])

            for allowed_cidr in cfg.CONF.akanda_allowed_cidr_ranges:
                if net in netaddr.IPNetwork(allowed_cidr):
                    break
            else:
                reason = _('Cannot create a subnet that is not within the '
                           'allowed address ranges [%s].' %
                           cfg.CONF.akanda_allowed_cidr_ranges)
                raise q_exc.AdminRequired(reason=reason)

        retval = super(OVSQuantumPluginV2, self).create_subnet(context, subnet)

        self._akanda_auto_add_subnet_to_router(context, retval)

        return retval

    def update_subnet(self, context, id, subnet):
        old_gateway = self._get_subnet(context, id)['gateway_ip']
        retval = super(OVSQuantumPluginV2, self).update_subnet(context,
                                                               id,
                                                               subnet)
        # update router ports to make sure gateway matches
        if old_gateway != retval['gateway_ip']:
            self._akanda_update_internal_gateway_port_ip(context, retval)
        return retval

    def delete_subnet(self, context, id):
        # remove port from router first

        return super(OVSQuantumPluginV2, self).delete_subnet(context, id)

    def _akanda_auto_add_subnet_to_router(self, context, subnet):
        if context.is_admin:
            # admins can manually add their own interfaces
            return

        if not subnet.get('gateway_ip'):
            return

        router_q = context.session.query(l3_db.Router)
        router_q = router_q.filter_by(tenant_id=context.tenant_id)

        try:
            router = router_q.one()
        except exc.NoResultFound:
            router_args = {'tenant_id': context.tenant_id,
                           'name': 'ak-%s' % context.tenant_id,
                           'admin_state_up': True}
            router = self.create_router(context, {'router': router_args})

        if not self._akanda_update_internal_gateway_port_ip(context, subnet):
            self.add_router_interface(context.elevated(),
                                      router['id'],
                                      {'subnet_id': subnet['id']})

    def _akanda_update_internal_gateway_port_ip(self, context, subnet):
        if not subnet.get('gateway_ip'):
            return

        filters = {
            'device_owner': [l3_db.DEVICE_OWNER_ROUTER_INTF],
            'network_id': [subnet['network_id']]
        }
        ports = self.get_ports(context, filters=filters)

        for port in ports:
            for fixed_ip in port['fixed_ips']:
                if fixed_ip['subnet_id'] == subnet['id']:
                    fixed_ip['ip_address'] = subnet['gateway_ip']
                    break
            else:
                port['fixed_ips'].append({'subnet_id': subnet['id'],
                                          'ip_address': subnet['gateway_ip']})

            self.update_port(context.elevated(),
                             port['id'],
                             {'port': port})
        return True

    def _akanda_add_ipv6_subnet(self, context, network):

        try:
            subnet_generator = _ipv6_subnet_generator(
                cfg.CONF.akanda_ipv6_tenant_range,
                cfg.CONF.akanda_ipv6_prefix_length)
        except:
            LOG.exception('Unable able to add tenant IPv6 subnet.')
            return

        remaining = IPV6_ASSIGNMENT_ATTEMPTS

        while remaining:
            remaining -=1

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
                           'allocation_pools': attributes.ATTR_NOT_SPECIFIED}
                self.create_subnet(context, {'subnet': create_args})
                break
        else:
            LOG.error('Unable to generate a unique tenant subnet cidr')

def _ip6_subnet_generator(network_range, prefixlen):
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
    max_range = 2**(prefixlen - net.prefixlen)

    while True:
        rand_bits = rand.randint(0, max_range)

        candidate_cidr = netaddr.IPNetwork(
                netaddr.IPAddress(net.value + (rand_bits << prefixlen)))
        candidate_cidr.prefixlen = prefixlen

        yield candidate_cidr
