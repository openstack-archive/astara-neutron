

from neutron_lbaas.services.loadbalancer import plugin


class LoadBalancerPluginv2(plugin.LoadBalancerPluginv2):
    # XXX: TODO
    # This doens't seem to work. Inheriting here and loading this instead of
    # the in-tree plugin fails with:
    # ExtensionsNotFound: Extensions not found: ['lbaasv2', 'lbaas_agent_schedulerv2']
    # Instead I'm manually adding the akloadbalancerstatus extension to supported_extension_aliases
    # in neutron_lbaas.services.loadbalancer.plugin:LoadBalancerPluginv2
    supported_extension_aliases = (
        plugin.LoadBalancerPluginv2.supported_extension_aliases +
        ['akloadbalancerstatus']
    )
