====================================================================
 Akanda User-facing API implemented as a Neutron Resource Extension
====================================================================

Provides
========

Portforward
-----------

portfoward.py implemented under neutron/extensions allows the ability
to create portforwarding rules.

Filterrule
----------

filterrule.py implemented under neutron/extensions allows the ability
to create firewall rules that eventually gets implemented as OpenBSD
PF rules within the Akanda appliance.

AddressBook
-----------

addressbook.py implemented under neutron/extensions allows the ability
to administratively manage IP Address groups that can be used in filter
rules.

Info
----

This is the home for the REST API that users will be calling directly with
their preferred REST tool (curl, Python wrapper, etc.).

This code could eventually become part of OpenStack Neutron or act as a source
or inspiration that will. As such, this API should be constructed entirely with
standard OpenStack tools.


Authz
-----

The resource extensions are implemented with the ability to leverage AuthZ.
In order to use AuthZ, update Neutron's policy file for the extension to work
with the following::

    "create_portforward": [],
    "get_portforward": [["rule:admin_or_owner"]],
    "update_portforward": [["rule:admin_or_owner"]],
    "delete_portforward": [["rule:admin_or_owner"]]


To use quotas, add to the QUOTAS section of neutron.conf::

    quota_portforward = 10


Installation - DevStack (single node setup)
===========================================

Preliminary Steps
-----------------

1. Create a localrc file under the devstack directory with the following::

    MYSQL_PASSWORD=openstack
    RABBIT_PASSWORD=openstack
    SERVICE_TOKEN=openstack
    SERVICE_PASSWORD=openstack
    ADMIN_PASSWORD=openstack
    enable_service q-svc
    enable_service q-agt
    enable_service q-dhcp
    enable_service neutron
    enable_service q-l3
    LIBVIRT_FIREWALL_DRIVER=nova.virt.firewall.NoopFirewallDriver
    Q_PLUGIN=openvswitch
    NOVA_USE_NEUTRON_API=v2

2. Run ./stack.sh until the stack account and /opt/stack directory gets created.
3. Run ./unstack.sh

Neutron Extensions install
--------------------------

<workdir> = https://github.com/dreamhost/akanda/tree/master/userapi_extensions/akanda/neutron

1. Clone neutron to /opt/stack using ``git clone https://github.com/openstack/neutron.git``
2. Change to the ``userapi_extensions`` dir within the Akanda project
3. Run ``python setup.py develop``
4. Return to devstack directory and replace the following lines::

    -        Q_PLUGIN_CLASS="neutron.plugins.openvswitch.ovs_neutron_plugin.OVSNeutronPluginV2"
    +        Q_PLUGIN_CLASS="akanda.neutron.plugins.ovs_neutron_plugin.OVSNeutronPluginV2"

5. Add the following line to load the extension right above Q_AUTH_STRATEGY::

    +    iniset $Q_CONF_FILE DEFAULT api_extensions_path "extensions:/opt/stack/akanda/userapi_extensions/akanda/neutron/extensions"

6. Run ./stack.sh again to generate the required DB migrations and start the required services.

7. You should see for example (dhaddressbook in this case), something
   similar to the following to indicate a successful load of an
   extension, however it is not complete without quotas::

    2012-09-11 09:17:04     INFO [neutron.api.extensions] Initializing extension manager.
    2012-09-11 09:17:04     INFO [neutron.api.extensions] Loading extension file: _authzbase.py
    2012-09-11 09:17:04     INFO [neutron.api.extensions] Loading extension file: addressbook.py
    2012-09-11 09:17:04    DEBUG [neutron.api.extensions] Ext name: addressbook
    2012-09-11 09:17:04    DEBUG [neutron.api.extensions] Ext alias: dhaddressbook
    2012-09-11 09:17:04    DEBUG [neutron.api.extensions] Ext description: An addressbook extension
    2012-09-11 09:17:04    DEBUG [neutron.api.extensions] Ext namespace: http://docs.dreamcompute.com/api/ext/v1.0

8. Switch to q-svc screen and press Ctrl-C

9. To enable Quote Support

   Stop q-svc as add the following to [QUOTA] section of
   ``/etc/neutron/neutron.conf``::

       quota_portforward = 10
       quota_filterrule = 100
       quota_addressbook = 5
       quota_addressbookgroup = 50
       quota_addressbookentry = 250

10. Add the follow to /etc/neutron/policy.json to enable policies::

    "create_filerrule": [],
    "get_filterrule": [["rule:admin_or_owner"]],
    "update_filterrule": [["rule:admin_or_owner"]],
    "delete_filterrule": [["rule:admin_or_owner"]],
    "create_addressbook": [],
    "get_addressbook": [["rule:admin_or_owner"]],
    "update_addressbook": [["rule:admin_or_owner"]],
    "delete_addressbook": [["rule:admin_or_owner"]],
    "create_addressbookgroup": [],
    "get_addressbookgroup": [["rule:admin_or_owner"]],
    "update_addressbookgroup": [["rule:admin_or_owner"]],
    "delete_addressbookgroup": [["rule:admin_or_owner"]],
    "create_addressbookentry": [],
    "get_addressbookentry": [["rule:admin_or_owner"]],
    "update_addressbookentry": [["rule:admin_or_owner"]],
    "delete_addressbookentry": [["rule:admin_or_owner"]],
    "update_routerstatus": [["rule:admin_only"]]

11. Restart q-svc by using up arrow to retrieve the command from the history.


Appendix
--------

To manually start and stop Neutron Services under DevStack:

1. Run 'screen -x'. To show a list of screens, use Ctrl+A+" (double quote char)
2. Select q-svc. In most cases - Ctrl+A+1 should work.
3. Run the following to start Neutron or Ctrl+C to stop::

    $ need-command-here


Gotchas
=======

1. There is no Neutron Model validation for source and destination
   protocols in FilterRule. I.e., you can create forward rules between
   UDP and TCP or anything else. Currently validation happens only in
   Horizon. If you use the API directly, you are on your own!
