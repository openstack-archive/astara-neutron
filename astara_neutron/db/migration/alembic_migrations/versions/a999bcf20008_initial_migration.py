# Copyright 2016 <PUT YOUR NAME/COMPANY HERE>
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

from alembic import op
import sqlalchemy as sa


"""empty message

Revision ID: a999bcf20008
Revises: start_astara_neutron
Create Date: 2016-03-14 14:09:43.025886

"""

# revision identifiers, used by Alembic.
revision = 'a999bcf20008'
down_revision = 'start_astara_neutron'


def upgrade():
    op.create_table(
        'astara_byonf',
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('function_type', sa.String(length=255), nullable=False),
        sa.Column('driver', sa.String(length=36), nullable=False),
        sa.Column('image_id', sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'function_type',
                            name='uix_tenant_id_function'),
    )
