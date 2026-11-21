"""invitation_codes_and_onboarding

Revision ID: e5b8d9f0a123
Revises: d4a7c8e9f012
Create Date: 2026-11-21 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b8d9f0a123'
down_revision: Union[str, Sequence[str], None] = 'd4a7c8e9f012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update users table: make organization_id and role nullable
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('organization_id', existing_type=sa.String(length=36), nullable=True)
        batch_op.alter_column('role', existing_type=sa.String(length=50), nullable=True)

    # 2. Update organizations table: add description and logo_url
    with op.batch_alter_table('organizations') as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column('logo_url', sa.String(length=500), nullable=True))

    # 3. Update organization_invitations table: add invitation_code, max_uses, use_count, requires_approval, allowed_roles
    with op.batch_alter_table('organization_invitations') as batch_op:
        batch_op.add_column(sa.Column('invitation_code', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('max_uses', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))
        batch_op.add_column(sa.Column('allowed_roles', sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f('ix_organization_invitations_invitation_code'), ['invitation_code'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('organization_invitations') as batch_op:
        batch_op.drop_index(batch_op.f('ix_organization_invitations_invitation_code'))
        batch_op.drop_column('allowed_roles')
        batch_op.drop_column('requires_approval')
        batch_op.drop_column('use_count')
        batch_op.drop_column('max_uses')
        batch_op.drop_column('invitation_code')

    with op.batch_alter_table('organizations') as batch_op:
        batch_op.drop_column('logo_url')
        batch_op.drop_column('description')

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('role', existing_type=sa.String(length=50), nullable=False)
        batch_op.alter_column('organization_id', existing_type=sa.String(length=36), nullable=False)
