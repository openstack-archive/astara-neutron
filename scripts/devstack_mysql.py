# -*- coding: utf-8 -*-
import uuid

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy import MetaData


try:
    engine = create_engine('mysql://root:openstack@localhost')
    metadata = MetaData(bind=engine)
except Exception, e:
    raise e


def create_dummy_ipallocations_id():
    """
    [murraju] This is a quick hack to generate an ipallocations id
    that can be used by fixed_id in port forwards to allow successful
    POST requests. This is only for devstack or development purposes.
    """
    engine.execute("USE ovs_quantum")
    subnets = engine.execute('select * from subnets limit 1')
    engine.execute("USE ovs_quantum")
    networks = engine.execute('select * from networks limit 1')

    for row in subnets:
        print "using subnet id: ", row['id']
        subnet_id = row['id']

    for row in networks:
        print "using network id: ", row['id']
        network_id = row['id']

    ipallocations_id = uuid.uuid1()
    ipallocations_table = sqlalchemy.Table("ipallocations",
                                           metadata, autoload=True)
    insert_sql = ipallocations_table.insert()
    insert_sql.execute(id=ipallocations_id, port_id=None,
                       subnet_id=subnet_id, network_id=network_id,
                       ip_address='172.16.20.1')

    print ''
    print "Created ipallocations id: ", ipallocations_id
    print ''
    print "Use %s as the fixed_id field for portforward" % ipallocations_id
    print ''

create_dummy_ipallocations_id()
