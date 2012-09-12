# -*- coding: utf-8 -*-
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Column, Table, ForeignKey
from sqlalchemy import Integer, String


try:
    engine = sqlalchemy.create_engine('mysql://root:openstack@localhost')
    metadata = MetaData(bind=engine)
except Exception, e:
    raise e

engine.execute("USE ovs_quantum")
subnets = engine.execute('select * from subnets limit 1')
engine.execute("USE ovs_quantum")
networks = engine.execute('select * from networks limit 1')


def construct_sql():
    for row in subnets:
        print "subnet id: ", row['id']
        subnet_id = row['id']

    for row in networks:
        print "network id: ", row['id']
        network_id = row['id']

    ipallocations_table = sqlalchemy.Table("ipallocations",
                                           metadata, autoload=True)
    insert_sql = ipallocations_table.insert()
    insert_sql.execute(id='73ed9ee0-fd02-11e1-a21f-0800200c9a66',
                       subnet_id=subnet_id, network_id=network_id,
                       ip_address='172.16.20.1')


construct_sql()
