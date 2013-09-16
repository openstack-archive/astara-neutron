# Copyright 2012 New Dream Network, LLC (DreamHost)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# DreamHost Neutron Extensions
# @author: Murali Raju, New Dream Network, LLC (DreamHost)
# @author: Mark Mcclain, New Dream Network, LLC (DreamHost)

import abc

from neutron import quota
from neutron.api.v2 import base
from neutron.api.v2 import resource as api_resource
from neutron.common import exceptions as q_exc
from neutron.common.config import cfg


class ResourcePlugin(object):
    """
    This is a class does some of what the Neutron plugin does, managing
    resources in a way very similar to what Neutron does. It differ from
    Neutron is that this provides a base plugin infrastructure, and doesn't
    manage any resources.

    Neutron doesn't split infrastructure and implementation.
    """
    JOINS = ()

    def __init__(self, delegate):
        # synthesize the hooks because Neutron's base class uses the
        # resource name as part of the method name
        setattr(self, 'get_%s' % delegate.collection_name,
                self._get_collection)
        setattr(self, 'get_%s' % delegate.resource_name, self._get_item)
        setattr(self, 'update_%s' % delegate.resource_name, self._update_item)
        setattr(self, 'create_%s' % delegate.resource_name, self._create_item)
        setattr(self, 'delete_%s' % delegate.resource_name, self._delete_item)
        self.delegate = delegate

    def _get_tenant_id_for_create(self, context, resource):
        if context.is_admin and 'tenant_id' in resource:
            tenant_id = resource['tenant_id']
        elif ('tenant_id' in resource and
              resource['tenant_id'] != context.tenant_id):
            reason = 'Cannot create resource for another tenant'
            raise q_exc.AdminRequired(reason=reason)
        else:
            tenant_id = context.tenant_id
        return tenant_id

    def _model_query(self, context):
        query = context.session.query(self.delegate.model)

    # NOTE(jkoelker) non-admin queries are scoped to their tenant_id
        if not context.is_admin and hasattr(self.delegate.model, 'tenant_id'):
            query = query.filter(
                self.delegate.model.tenant_id == context.tenant_id)
        return query

    def _apply_filters_to_query(self, query, model, filters):
        if filters:
            for key, value in filters.iteritems():
                column = getattr(model, key, None)
                if column:
                    query = query.filter(column.in_(value))
        return query

    def _get_collection(self, context, filters=None, fields=None):
        collection = self._model_query(context)
        collection = self._apply_filters_to_query(collection,
                                                  self.delegate.model,
                                                  filters)
        return [self._fields(self.delegate.make_dict(c), fields) for c in
                collection.all()]

    def _get_by_id(self, context, id):
        query = self._model_query(context)
        return query.filter_by(id=id).one()

    def _get_item(self, context, id, fields=None):
        obj = self._get_by_id(context, id)
        return self._fields(self.delegate.make_dict(obj), fields)

    def _update_item(self, context, id, **kwargs):
        key = self.delegate.resource_name
        resource_dict = kwargs[key][key]
        obj = self._get_by_id(context, id)
        return self.delegate.update(context, obj, resource_dict)

    def _create_item(self, context, **kwargs):
        key = self.delegate.resource_name
        resource_dict = kwargs[key][key]
        tenant_id = self._get_tenant_id_for_create(context, resource_dict)
        return self.delegate.create(context, tenant_id, resource_dict)

    def _delete_item(self, context, id):
        obj = self._get_by_id(context, id)
        with context.session.begin():
            self.delegate.before_delete(obj)
            context.session.delete(obj)

    def _fields(self, resource, fields):
        if fields:
            return dict([(key, item) for key, item in resource.iteritems()
                        if key in fields])
        return resource


class ResourceDelegateInterface(object):
    """
    An abstract marker class defines the interface of RESTful resources.
    """
    __metaclass__ = abc.ABCMeta

    def before_delete(self, resource):
        pass

    @abc.abstractproperty
    def model(self):
        pass

    @abc.abstractproperty
    def resource_name(self):
        pass

    @abc.abstractproperty
    def collection_name(self):
        pass

    @property
    def joins(self):
        return ()

    @abc.abstractmethod
    def update(self, context, resource, body):
        pass

    @abc.abstractmethod
    def create(self, context, tenant_id, body):
        pass

    @abc.abstractmethod
    def make_dict(self, obj):
        pass


class ResourceDelegate(ResourceDelegateInterface):
    """
    This class partially implemnts the ResourceDelegateInterface, providing
    common code for use by child classes that inherit from it.
    """
    def create(self, context, tenant_id, body):
        with context.session.begin(subtransactions=True):
            item = self.model(**body)
            context.session.add(item)
        return self.make_dict(item)

    def update(self, context, resource, resource_dict):
        with context.session.begin(subtransactions=True):
            resource.update(resource_dict)
            context.session.add(resource)
        return self.make_dict(resource)


def create_extension(delegate):
    """
    """
    return api_resource.Resource(base.Controller(ResourcePlugin(delegate),
                                                 delegate.collection_name,
                                                 delegate.resource_name,
                                                 delegate.ATTRIBUTE_MAP))


def register_quota(resource_name, config_key_name, default=-1):
    """
    """
    quota_opt = cfg.IntOpt(config_key_name,
                           default=default,
                           help=('number of %s allowed per tenant, -1 for '
                                 'unlimited' % resource_name))
    cfg.CONF.register_opts([quota_opt], 'QUOTAS')
    quota.QUOTAS.register_resource(
        quota.CountableResource(resource_name,
                                quota._count_resource,
                                config_key_name))
