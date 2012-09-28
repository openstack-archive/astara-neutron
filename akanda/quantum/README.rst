Akanda User-facing API implemented as a Quantum Resource Extension
==========================================================

Portforward
-----------

portfoward.py implemented under quantum/extensions allows the ability
to create portforwarding rules. 

Filterrule
----------

filterrule.py implemented under quantum/extensions allows the ability
to create firewall rules that eventually gets implemented as OpenBSD
PF rules within the Akanda appliance.

AddressBook
---------
addressbook.py implemented under quantum/extensions allows the ability
to administratively manage IP Address groups that can be used in filter
rules.

Info
----

This is the home for the REST API that users will be calling directly with
their preferred REST tool (curl, Python wrapper, etc.).

This code could eventually become part of OpenStack Quantum or act as a source or
inspiration that will. As such, this API should be constructed entirely with
standard OpenStack tools.


Exploratory Dev Work
--------------------

The resource extensions are implemented with the ability to leverage AuthZ.
In order to use AuthZ, update Quantum's policy file for the extension to work 
with the following:

    "create_portforward": [],
    "get_portforward": [["rule:admin_or_owner"]],
    "update_portforward": [["rule:admin_or_owner"]],
    "delete_portforward": [["rule:admin_or_owner"]]


To use quotas:

add to the QUOTAS section of quantum.conf

quota_portforward = 10

=======

Installation - DevStack (single node setup)
------------

Preliminary steps:

1. Run ./stack.sh until the stack account and /opt/stack directory gets created.
2. Hit Ctrl+C
3. Create a localrc file under the devstack directory with the following:

MYSQL_PASSWORD=openstack
RABBIT_PASSWORD=openstack
SERVICE_TOKEN=openstack
SERVICE_PASSWORD=openstack
ADMIN_PASSWORD=openstack
enable_service q-svc
enable_service q-agt
enable_service q-dhcp
enable_service quantum
LIBVIRT_FIREWALL_DRIVER=nova.virt.firewall.NoopFirewallDriver
Q_PLUGIN=openvswitch 
NOVA_USE_QUANTUM_API=v2


Quantum Extensions install:

<workdir> = https://github.com/dreamhost/akanda/tree/master/userapi_extensions/akanda/quantum

1. Clone quantum to /opt/stack using git clone https://github.com/openstack/quantum.git
2. Overwrite models_v2.py from <workdir/db> to quantum/db/models_v2.py
3. Copy _authzbase.py <workdir> to quantum/extensions/
4. Copy portfoward.py <workdir> to quantum/extensions/
5. Copy filterrule.py <workdir> to quantum/extensions/
6. Copy addressbook.py <workdir> to quantum/extensions/
7. Copy portalias.py <workdir> to quantum/extensions/
8. Modify the plugin to allow the extension. In this case, the OVS plugin needs to allow
   dhportforward, dhaddressbook, dhfilterrule:

    vi quantum/plugins/openvswitch/ovs_quantum_plugin.py

    Edit supported_extension_aliases to allow the extension

    supported_extension_aliases = ["provider", "router", "dhportforward", "dhfilterrule", "dhaddressbook", "dhportalias"]

9. Run ./stack.sh again to generate the required DB migrations and start the required services.

10. You should see for example (dhaddressbook in this case), something similar to the following 
    to indicate a successful load of an extension, however it is not complete without quotas:

2012-09-11 09:17:04     INFO [quantum.api.extensions] Initializing extension manager.
2012-09-11 09:17:04     INFO [quantum.api.extensions] Loading extension file: _authzbase.py
2012-09-11 09:17:04     INFO [quantum.api.extensions] Loading extension file: addressbook.py
2012-09-11 09:17:04    DEBUG [quantum.api.extensions] Ext name: addressbook
2012-09-11 09:17:04    DEBUG [quantum.api.extensions] Ext alias: dhaddressbook
2012-09-11 09:17:04    DEBUG [quantum.api.extensions] Ext description: An addressbook extension
2012-09-11 09:17:04    DEBUG [quantum.api.extensions] Ext namespace: http://docs.dreamcompute.com
/api/ext/v1.0

11. Hit Ctrl+C and edit /etc/quantum/quantum.conf to enable the quota driver:

    [QUOTAS]

    quota_driver = quantum.extensions._quotav2_driver.DbQuotaDriver

12. Run the following to start Quantum again:

cd /opt/stack/quantum && python /opt/stack/quantum/bin/quantum-server
--config-file /etc/quantum/quantum.conf
--config-file /etc/quantum/plugins/openvswitch/ovs_quantum_plugin.ini

With quotas enabled, the output should look like the following:

2012-09-12 15:00:37  WARNING [quantum.api.extensions] Loaded extension: quotas
2012-09-12 15:00:37    DEBUG [routes.middleware] Initialized with method overriding = True, and path info altering = True
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: extensions
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: dhportforward
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: dhaddressbook
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: quotas
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: dhfilterrule
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: routers
2012-09-12 15:00:37    DEBUG [quantum.api.extensions] Extended resource: floatingips
2012-09-12 15:00:37    DEBUG [routes.middleware] Initialized with method overriding = True, and path info altering = True

Appendix:

To manually start and stop Quantum Services under DevStack:

1. Run 'screen -x'. To show a list of screens, use Ctrl+A+"
2. Select q-svc. In most cases - Ctrl+A+1 should work.
3. Run the following to start Quantum or Ctrl+C to stop:


Gotchas:

1. There is no Quantum Model validation for source and destination protocols in FilterRule. i.e you can create forward rules between UDP and TCP or anything else. Currently validation happens only in Horizon. If you use the API directly, you are on your own!

