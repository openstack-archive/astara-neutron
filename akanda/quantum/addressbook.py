from quantum.api.v2 import attributes
from quantum.db import models_v2
from quantum.extensions import extensions


from quantum.extensions import _authzbase
from quantum.db import models


# XXX: I used Network as an existing model for testing.  Need to change to
# use an actual PortForward model.
#
# Duncan: cool, we'll get a PortForward model in place ASAP, so that this code
# can be updated to use it.


class AddressbookResource(_authzbase.ResourceDelegate):
    """
    """
    model = models.AddressBook
    resource_name = 'addressbook'
    collection_name = 'addressbookgroups'

    ATTRIBUTE_MAP = {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:regex': attributes.UUID_PATTERN},
               'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'default': '', 'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'required_by_policy': True,
                      'is_visible': True},
    }

    def make_dict(self, addressbook):
        """
        Convert a addressbook model object to a dictionary.
        """
        res = {'id': addressbook['id'],
               'name': addressbook['name'],
               'groups': [group['id']
                           for group in addressbook['groups']]}
        return res


_authzbase.register_quota('addressbook', 'quota_addressbook')


class Addressbook(object):
    """
    """
    def get_name(self):
        return "addressbook"

    def get_alias(self):
        return "dhaddressbook"

    def get_description(self):
        return "An addressbook extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhaddressbook',
            _authzbase.create_extension(AddressbookResource()))]
            #_authzbase.ResourceController(AddressBookResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
