from neutron.api.v2 import attributes
from neutron.common import exceptions as q_exc
from neutron.db.l3_db import DEVICE_OWNER_FLOATINGIP, FloatingIP
from neutron.openstack.common import uuidutils
from neutron.openstack.common import log

from oslo.config import cfg


LOG = log.getLogger(__name__)

explicit_floating_ip_opts = [
    cfg.MultiStrOpt(
        'floatingip_subnet',
        default=[],
        help='UUID(s) of subnet(s) from which floating IPs can be allocated',
        required=True,
    ),
]


class ExplicitFloatingIPAllocationMixin(object):
    """Overrides methods for managing floating ips

    Should be mixed in before inheriting from
    neutron.db.l3_db.L3_NAT_db_mixin.

    """

    def _allocate_floatingip_from_configured_subnets(self, context):
        cfg.CONF.register_opts(explicit_floating_ip_opts, group='akanda')
        # NOTE(dhellmann): There may be a better way to do this, but
        # the "filter" argument to get_subnets() is not documented so
        # who knows.
        e_context = context.elevated()
        subnets = [
            self._get_subnet(e_context, unicode(s))
            for s in cfg.CONF.akanda.floatingip_subnet
        ]
        if not subnets:
            LOG.error('config setting akanda.floatingip_subnet missing')
            raise q_exc.IpAddressGenerationFailure(net_id='UNKNOWN')
        # The base class method _generate_ip() handles the allocation
        # ranges and going from one subnet to the next when a network
        # is exhausted.
        return self._generate_ip(context, subnets)

    def create_floatingip(self, context, floatingip):
        LOG.debug('create_floatingip %s', (floatingip,))
        fip = floatingip['floatingip']
        tenant_id = self._get_tenant_id_for_create(context, fip)
        fip_id = uuidutils.generate_uuid()

        f_net_id = fip['floating_network_id']
        if not self._core_plugin._network_is_external(context, f_net_id):
            msg = _("Network %s is not a valid external network") % f_net_id
            raise q_exc.BadRequest(resource='floatingip', msg=msg)

        # NOTE(dhellmann): Custom
        #
        # FIXME(dhellmann): This should probably verify that the subnet
        # being used is on the network the user requested.
        ip_to_use = self._allocate_floatingip_from_configured_subnets(context)

        with context.session.begin(subtransactions=True):
            # This external port is never exposed to the tenant.
            # it is used purely for internal system and admin use when
            # managing floating IPs.
            external_port = self._core_plugin.create_port(context.elevated(), {
                'port':
                {'tenant_id': '',  # tenant intentionally not set
                 'network_id': f_net_id,
                 'mac_address': attributes.ATTR_NOT_SPECIFIED,
                 # NOTE(dhellmann): Custom
                 'fixed_ips': [ip_to_use],
                 'admin_state_up': True,
                 'device_id': fip_id,
                 'device_owner': DEVICE_OWNER_FLOATINGIP,
                 'name': ''}})
            # Ensure IP addresses are allocated on external port
            if not external_port['fixed_ips']:
                raise q_exc.ExternalIpAddressExhausted(net_id=f_net_id)

            floating_fixed_ip = external_port['fixed_ips'][0]
            floating_ip_address = floating_fixed_ip['ip_address']
            floatingip_db = FloatingIP(
                id=fip_id,
                tenant_id=tenant_id,
                floating_network_id=fip['floating_network_id'],
                floating_ip_address=floating_ip_address,
                floating_port_id=external_port['id'])
            fip['tenant_id'] = tenant_id
            # Update association with internal port
            # and define external IP address
            self._update_fip_assoc(context, fip,
                                   floatingip_db, external_port)
            context.session.add(floatingip_db)

        router_id = floatingip_db['router_id']
        if router_id:
            self.l3_rpc_notifier.routers_updated(
                context, [router_id],
                'create_floatingip')
        return self._make_floatingip_dict(floatingip_db)
