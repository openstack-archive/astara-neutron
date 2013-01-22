from quantumclient.v2_0 import client
from quantumclient.common import exceptions


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


if __name__ == '__main__':

    # WARNING: This block will delete all object owned by the
    # specified user. It may do too much.

    c = AkandaClientWrapper(
        username='demo',
        password='secrete',
        tenant_name='demo',
        auth_url='http://localhost:5000/v2.0/',
        auth_strategy='keystone',
        auth_region='RegionOne')
    resources = [
        (c.list_portalias, c.delete_portalias, 'portalias'),
        (c.list_filterrules, c.delete_filterrule, 'filterrule'),
        (c.list_portforwards, c.delete_portforward, 'portforward'),
        (c.list_addressbookentries, c.delete_addressentry, 'addressentry'),
        (c.list_addressgroups, c.delete_addressgroup, 'addressgroup'),
        (c.list_ports, c.delete_port, 'port'),
        (c.list_subnets, c.delete_subnet, 'subnet'),
        (c.list_networks, c.delete_network, 'network')
    ]
    for lister, deleter, obj_type in resources:
        print obj_type
        response = lister()
        data = response[iter(response).next()]
        for o in data:
            print repr(o)
            try:
                deleter(o['id'])
            except exceptions.QuantumClientException as err:
                print 'ERROR:', err
