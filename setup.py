# Copyright 2014 DreamHost, LLC
# Copyright 2015 Akanda, Inc
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


from setuptools import setup, find_packages


setup(
#    name='akanda-neutron',
#    version='2015.1',
#    description='OpenStack L3 User-Facing REST API for Neutron',
#    author='OpenStack',
#    author_email='openstack-dev@lists.openstack.org',
#    url='http://github.com/stackforge/akanda-neutron',
#    license='Apache2',
    install_requires=[],
    namespace_packages=['akanda'],
    packages=find_packages(exclude=['test', 'smoke']),
    include_package_data=True,
    zip_safe=False,
)
