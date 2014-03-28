from neutron.common import exceptions as q_exc
from neutron.openstack.common import uuidutils
from neutron.api.v2 import attributes
from neutron.db.l3_db import DEVICE_OWNER_FLOATINGIP, FloatingIP


class ExplicitFloatingIPAllocationMixin(object):
    """Overrides methods for managing floating ips

    Should be mixed in before inheriting from
    neutron.db.l3_db.L3_NAT_db_mixin.

    """

    def create_floatingip(self, context, floatingip):
        fip = floatingip['floatingip']
        tenant_id = self._get_tenant_id_for_create(context, fip)
        fip_id = uuidutils.generate_uuid()

        f_net_id = fip['floating_network_id']
        if not self._core_plugin._network_is_external(context, f_net_id):
            msg = _("Network %s is not a valid external network") % f_net_id
            raise q_exc.BadRequest(resource='floatingip', msg=msg)

        with context.session.begin(subtransactions=True):
            # This external port is never exposed to the tenant.
            # it is used purely for internal system and admin use when
            # managing floating IPs.
            external_port = self._core_plugin.create_port(context.elevated(), {
                'port':
                {'tenant_id': '',  # tenant intentionally not set
                 'network_id': f_net_id,
                 'mac_address': attributes.ATTR_NOT_SPECIFIED,
                 'fixed_ips': attributes.ATTR_NOT_SPECIFIED,
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
