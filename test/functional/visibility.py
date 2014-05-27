# Copyright 2014 DreamHost, LLC 
#
# Author: DreamHost, LLC 
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


import unittest

from quantumclient.v2_0 import client


class AkandaClientWrapper(client.Client):
    """Add client support for Akanda Extensions. """
    addressgroup_path = '/dhaddressgroup'
    addressentry_path = '/dhaddressentry'
    filterrule_path = '/dhfilterrule'
    portalias_path = '/dhportalias'
    portforward_path = '/dhportforward'

    # portalias crud
    @client.APIParamsCall
    def list_portalias(self, **params):
        return self.get(self.portalias_path, params=params)

    @client.APIParamsCall
    def create_portalias(self, body=None):
        return self.post(self.portalias_path, body=body)

    @client.APIParamsCall
    def show_portalias(self, portforward, **params):
        return self.get('%s/%s' % (self.portalias_path, portforward),
                        params=params)

    @client.APIParamsCall
    def update_portalias(self, portforward, body=None):
        return self.put('%s/%s' % (self.portalias_path, portforward),
                        body=body)

    @client.APIParamsCall
    def delete_portalias(self, portforward):
        return self.delete('%s/%s' % (self.portalias_path, portforward))

    # portforward crud
    @client.APIParamsCall
    def list_portforwards(self, **params):
        return self.get(self.portforward_path, params=params)

    @client.APIParamsCall
    def create_portforward(self, body=None):
        return self.post(self.portforward_path, body=body)

    @client.APIParamsCall
    def show_portforward(self, portforward, **params):
        return self.get('%s/%s' % (self.portforward_path, portforward),
                        params=params)

    @client.APIParamsCall
    def update_portforward(self, portforward, body=None):
        return self.put('%s/%s' % (self.portforward_path, portforward),
                        body=body)

    @client.APIParamsCall
    def delete_portforward(self, portforward):
        return self.delete('%s/%s' % (self.portforward_path, portforward))

    # filterrule crud
    @client.APIParamsCall
    def list_filterrules(self, **params):
        return self.get(self.filterrule_path, params=params)

    @client.APIParamsCall
    def create_filterrule(self, body=None):
        return self.post(self.filterrule_path, body=body)

    @client.APIParamsCall
    def show_filterrule(self, filterrule, **params):
        return self.get('%s/%s' % (self.filterrule_path, filterrule),
                        params=params)

    @client.APIParamsCall
    def update_filterrule(self, filterrule, body=None):
        return self.put('%s/%s' % (self.filterrule_path, filterrule),
                        body=body)

    @client.APIParamsCall
    def delete_filterrule(self, filterrule):
        return self.delete('%s/%s' % (self.filterrule_path, filterrule))

    # addressbook group crud
    @client.APIParamsCall
    def list_addressgroups(self, **params):
        return self.get(self.addressgroup_path, params=params)

    @client.APIParamsCall
    def create_addressgroup(self, body=None):
        return self.post(self.addressgroup_path, body=body)

    @client.APIParamsCall
    def show_addressgroup(self, addressgroup, **params):
        return self.get('%s/%s' % (self.addressgroup_path,
                                   addressgroup),
                        params=params)

    @client.APIParamsCall
    def update_addressgroup(self, addressgroup, body=None):
        return self.put('%s/%s' % (self.addressgroup_path,
                                   addressgroup),
                        body=body)

    @client.APIParamsCall
    def delete_addressgroup(self, addressgroup, body=None):
        return self.delete('%s/%s' % (self.addressgroup_path,
                                      addressgroup))

    # addressbook entries crud
    @client.APIParamsCall
    def list_addressbookentries(self, **params):
        return self.get(self.addressentry_path, params=params)

    @client.APIParamsCall
    def create_addressentry(self, body=None):
        return self.post(self.addressentry_path, body=body)

    @client.APIParamsCall
    def show_addressentry(self, addressentry, **params):
        return self.get('%s/%s' % (self.addressentry_path,
                                   addressentry),
                        params=params)

    @client.APIParamsCall
    def update_addressentry(self, addressentry, body=None):
        return self.put('%s/%s' % (self.addressentry_path,
                                   addressentry),
                        body=body)

    @client.APIParamsCall
    def delete_addressentry(self, addressentry):
        return self.delete('%s/%s' % (self.addressentry_path,
                                      addressentry))


class VisibilityTest(unittest.TestCase):

    def setUp(self):

        ###
        import random

        c = AkandaClientWrapper(
            username='demo',
            password='secrete',
            tenant_name='demo',
            auth_url='http://localhost:5000/v2.0/',
            auth_strategy='keystone',
            auth_region='RegionOne')

        self.group = c.create_addressgroup(
            body={'addressgroup': {'name': 'group1'}})
        self.entry_args = dict(name='entry1',
                               group_id=self.group['addressgroup']['id'],
                               cidr='192.168.1.1/24')
        self.addr_entry = c.create_addressentry(
            body=dict(addressentry=self.entry_args))

        # port forward

        self.network = c.create_network(
            body=dict(network=dict(name='test_net')))

        subnet_args = dict(network_id=self.network['network']['id'],
                           ip_version=4,
                           cidr='10.%d.%d.0/24' % (random.randint(0, 255),
                                                   random.randint(0, 255)))
        self.subnet = c.create_subnet(body=dict(subnet=subnet_args))

        port_args = dict(network_id=self.network['network']['id'],
                         device_owner='test')
        self.port = c.create_port(body=dict(port=port_args))

        pf_args = dict(name='rule1',
                       protocol='udp',
                       public_port=53,
                       private_port=53,
                       port_id=self.port['port']['id'])
        self.forward = c.create_portforward(body=dict(portforward=pf_args))

        rule_args = dict(action='pass',
                         protocol='tcp',
                         destination_id=self.group['addressgroup']['id'],
                         destination_port=80)

        self.rule = c.create_filterrule(body=dict(filterrule=rule_args))

        alias_args = dict(name='ssh', protocol='tcp', port=22)
        self.port_alias = c.create_portalias(body=dict(portalias=alias_args))

    def tearDown(self):
        c = AkandaClientWrapper(
            username='demo',
            password='secrete',
            tenant_name='demo',
            auth_url='http://localhost:5000/v2.0/',
            auth_strategy='keystone',
            auth_region='RegionOne')
        c.delete_portalias(self.port_alias['portalias']['id'])
        c.delete_filterrule(self.rule['filterrule']['id'])
        c.delete_portforward(self.forward['portforward']['id'])
        c.delete_addressentry(self.addr_entry['addressentry']['id'])
        c.delete_addressgroup(self.group['addressgroup']['id'])
        c.delete_port(self.port['port']['id'])
        c.delete_subnet(self.subnet['subnet']['id'])
        c.delete_network(self.network['network']['id'])


class CanSeeTestCaseMixin(object):

    def test_addressgroup(self):
        ag = self.c.show_addressgroup(self.group['addressgroup']['id'])
        assert ag
        assert ag['addressgroup']['id'] == self.group['addressgroup']['id']

    def test_addressentry(self):
        ae = self.c.show_addressentry(self.addr_entry['addressentry']['id'])
        assert ae
        assert ae['addressentry']['id'] == \
            self.addr_entry['addressentry']['id']

    def test_portforward(self):
        pf = self.c.show_portforward(self.forward['portforward']['id'])
        assert pf
        assert pf['portforward']['id'] == self.forward['portforward']['id']

    def test_filterrule(self):
        fr = self.c.show_filterrule(self.rule['filterrule']['id'])
        assert fr
        assert fr['filterrule']['id'] == self.rule['filterrule']['id']

    def test_portalias(self):
        pa = self.c.show_portalias(self.port_alias['portalias']['id'])
        assert pa
        assert pa['portalias']['id'] == self.port_alias['portalias']['id']


class SameUserTest(VisibilityTest, CanSeeTestCaseMixin):

    def setUp(self):
        super(SameUserTest, self).setUp()
        # Re-connect as the same user and verify that the
        # objects are visible.
        self.c = AkandaClientWrapper(
            username='demo',
            password='secrete',
            tenant_name='demo',
            auth_url='http://localhost:5000/v2.0/',
            auth_strategy='keystone',
            auth_region='RegionOne',
        )


class DifferentUserSameTenantTest(VisibilityTest, CanSeeTestCaseMixin):

    def setUp(self):
        super(DifferentUserSameTenantTest, self).setUp()
        # Re-connect as another user in the same tenant and verify
        # that the objects are visible.
        self.c = AkandaClientWrapper(
            username='demo2',
            password='secrete',
            tenant_name='demo',
            auth_url='http://localhost:5000/v2.0/',
            auth_strategy='keystone',
            auth_region='RegionOne',
        )


class DifferentTenantTest(VisibilityTest):

    def setUp(self):
        super(DifferentTenantTest, self).setUp()
        # Re-connect as another user in the same tenant and verify
        # that the objects are visible.
        self.c = AkandaClientWrapper(
            username='alt1',
            password='secrete',
            tenant_name='alt',
            auth_url='http://localhost:5000/v2.0/',
            auth_strategy='keystone',
            auth_region='RegionOne',
        )

    def _check_one(self, one, lister):
        response = lister()
        objs = response.values()[0]
        ids = [o['id'] for o in objs]
        assert one not in ids

    def test_addressgroup(self):
        self._check_one(self.group['addressgroup']['id'],
                        self.c.list_addressgroups)

    def test_addressentry(self):
        self._check_one(self.addr_entry['addressentry']['id'],
                        self.c.list_addressbookentries)

    def test_portforward(self):
        self._check_one(self.forward['portforward']['id'],
                        self.c.list_portforwards)

    def test_filterrule(self):
        self._check_one(self.rule['filterrule']['id'],
                        self.c.list_filterrules)

    def test_portalias(self):
        self._check_one(self.port_alias['portalias']['id'],
                        self.c.list_portalias)

if __name__ == '__main__':
    unittest.main()
