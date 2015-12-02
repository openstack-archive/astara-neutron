# Copyright (c) 2015 Akanda, Inc. All Rights Reserved.
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

from neutron_lbaas.services.loadbalancer import plugin


class LoadBalancerPluginv2(plugin.LoadBalancerPluginv2):
    """
    This is allows loadbalancer status to be updated from Akanda.
    To enable, add the full python path to this class to the service_plugin
    list in neutron.conf  Ensure both the path to astara_neutron/extensions
    has been added to api_extensions_path *as well as* the path to
    neutron-lbaas/neutron_lbaas/extensions.
    """
    supported_extension_aliases = (
        plugin.LoadBalancerPluginv2.supported_extension_aliases +
        ['akloadbalancerstatus']
    )
