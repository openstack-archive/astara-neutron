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


class FilterRuleResource(_authzbase.ResourceDelegate):
    """
    """
    model = models.FilterRule
    resource_name = 'filterrule'
    collection_name = 'filterrules'

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

    def make_dict(self, filterrule):
        """
        Convert a filterrule model object to a dictionary.
        """
        res = {'id': filterrule['id'],
               'action': filterrule['action'],
               'protocol': filterrule['protocol'],
               'source_alias': filterrule['source_alias'],
               'source_port': filterrule['source_port'],
               'destination_alias': filterrule['destination_alias'],
               'destination_port': filterrule['destination_port'],
               'created_at': filterrule['created_at']}
        return res


_authzbase.register_quota('filterrule', 'quota_filterrule')


class FilterRule(object):
    """
    """
    def get_name(self):
        return "filter rule"

    def get_alias(self):
        return "dhfilterrule"

    def get_description(self):
        return "A filter rule extension"

    def get_namespace(self):
        return 'http://docs.dreamcompute.com/api/ext/v1.0'

    def get_updated(self):
        return "2012-08-02T16:00:00-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'dhfilterrule',
            _authzbase.create_extension(filterruleResource()))]
            #_authzbase.ResourceController(FilterRuleResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
