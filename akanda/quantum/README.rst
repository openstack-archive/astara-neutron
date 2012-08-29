Akanda User-facing API implemented as a Quantum Extension
==========================================================

Portforward
-----------

portfoward.py implemented under quantum/extensions allows... 

Firewall
----------

firewall.py implemented under quantum/extensions allows...

AddressBook
---------
addressbook.py implemented under quantum/extensions allows...

Info
----

This is the home for the REST API that users will be calling directly with
their preferred REST tool (curl, Python wrapper, etc.).

This code will eventually become part of OpenStack or act as a source or
inspiration that will. As such, this API should be constructed entirely with
standard OpenStack tools.


Exploratory Dev Work
--------------------

You also have to update Quantum's policy file for the extension to work with
authZ.

    "create_portforward": [],
    "get_portforward": [["rule:admin_or_owner"]],
    "update_portforward": [["rule:admin_or_owner"]],
    "delete_portforward": [["rule:admin_or_owner"]]


If you want to use quotas:

add to the QUOTAS section of quantum.conf

quota_portforward = 10

=======

