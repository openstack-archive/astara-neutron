import os

from setuptools import setup, find_packages


setup(
    name='Akanda Horizon Dashboard Plugin',
    version='0.1.0',
    description='OpenStack Horizon dashboards for manipulating L3 extensions',
    author='DreamHost',
    author_email='dev-community@dreamhost.com',
    url='http://github.com/dreamhost/akanda',
    license='BSD',
    install_requires=[
    ],
    namespace_packages=['akanda'],
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
