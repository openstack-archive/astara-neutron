# Copyright 2014 DreamHost, LLC
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

from neutron.api import extensions
from neutron.api.v2 import attributes as attr

from astara_neutron.extensions import _authzbase
from astara_neutron.db.models import models

import oslo_db.exception as db_exc
import webob.exc


class ByonfResource(_authzbase.ResourceDelegate):
    """This resource is intended as a private API that allows the rug to chan
    the supporting network function.
    """
    model = models.Byonf
    resource_name = 'byonf'
    collection_name = 'byonfs'

    ATTRIBUTE_MAP = {
        'tenant_id': {
            'allow_post': True,
            'allow_put': True,
            'is_visible': True,
            'validate': {'type:string': attr.TENANT_ID_MAX_LEN},
        }, 'id': {
            'allow_post': False,
            'allow_put': False,
            'is_visible': True
        },
        'image_id': {
            'allow_post': True,
            'allow_put': True,
            'is_visible': True,
            'enforce_policy': True,
            'required_by_policy': True,
            'validate': {'type:uuid': None}
        },
        'function_type': {
            'allow_post': True,
            'allow_put': True,
            'is_visible': True,
            'enforce_policy': True,
            'required_by_policy': True
        },
        'driver': {
            'allow_post': True,
            'allow_put': True,
            'is_visible': True,
            'enforce_policy': True,
            'required_by_policy': True
        }
    }

    def create(self, context, tenant_id, resource_dict):
        try:
            return super(ByonfResource, self).create(
                context, tenant_id, resource_dict)
        except db_exc.DBDuplicateEntry as:
            raise webob.exc.HTTPConflict(
                'Tenant %s already has driver associatation for function: %s' %
                (resource_dict['tenant_id'], resource_dict['function_type']))

    def make_dict(self, byo):
        """
        Convert a Byo model object to a dictionary.
        """
        return {
            'tenant_id': byo['tenant_id'],
            'image_id': byo['image_id'],
            'function_type': byo['function_type'],
            'driver': byo['driver'],
            'id': byo['id']
        }


class Byonf(extensions.ExtensionDescriptor):
    """
    """
    def get_name(self):
        return "byonf"

    def get_alias(self):
        return "byonf"

    def get_description(self):
        return "A byonf extension"

    def get_namespace(self):
        return 'http://docs.openstack.org/api/ext/v1.0'

    def get_updated(self):
        return "2015-12-07T09:14:43-05:00"

    def get_resources(self):
        return [extensions.ResourceExtension(
            'byonf',
            _authzbase.create_extension(ByonfResource()))]

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []
