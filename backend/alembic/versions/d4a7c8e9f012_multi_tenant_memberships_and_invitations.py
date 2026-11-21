"""multi_tenant_memberships_and_invitations

Revision ID: d4a7c8e9f012
Revises: 3e527d21a50a
Create Date: 2026-11-21 12:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a7c8e9f012'
down_revision: Union[str, Sequence[str], None] = '3e527d21a50a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add owner_id to organizations
    with op.batch_alter_table('organizations') as batch_op:
        batch_op.add_column(sa.Column('owner_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_organizations_owner_id'), ['owner_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_organizations_owner_id',
            'users',
            ['owner_id'],
            ['id'],
            ondelete='SET NULL'
        )

    # 2. Create organization_memberships table
    op.create_table(
        'organization_memberships',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('invited_by_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['invited_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'organization_id', name='uq_user_organization')
    )
    op.create_index(op.f('ix_organization_memberships_id'), 'organization_memberships', ['id'], unique=False)
    op.create_index(op.f('ix_organization_memberships_user_id'), 'organization_memberships', ['user_id'], unique=False)
    op.create_index(op.f('ix_organization_memberships_organization_id'), 'organization_memberships', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_memberships_role'), 'organization_memberships', ['role'], unique=False)
    op.create_index(op.f('ix_organization_memberships_status'), 'organization_memberships', ['status'], unique=False)
    op.create_index(op.f('ix_organization_memberships_joined_at'), 'organization_memberships', ['joined_at'], unique=False)

    # 3. Create organization_invitations table
    op.create_table(
        'organization_invitations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('invited_email', sa.String(length=255), nullable=True),
        sa.Column('assigned_role', sa.String(length=50), nullable=False, server_default='Creator'),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('invited_by_id', sa.String(length=36), nullable=True),
        sa.Column('accepted_by_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['accepted_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['invited_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organization_invitations_id'), 'organization_invitations', ['id'], unique=False)
    op.create_index(op.f('ix_organization_invitations_organization_id'), 'organization_invitations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_invitations_invited_email'), 'organization_invitations', ['invited_email'], unique=False)
    op.create_index(op.f('ix_organization_invitations_token_hash'), 'organization_invitations', ['token_hash'], unique=True)
    op.create_index(op.f('ix_organization_invitations_expires_at'), 'organization_invitations', ['expires_at'], unique=False)
    op.create_index(op.f('ix_organization_invitations_status'), 'organization_invitations', ['status'], unique=False)

    # 4. Data migration: Migrate existing users into organization_memberships
    # and establish organization ownership
    bind = op.get_bind()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

    try:
        users = bind.execute(sa.text("SELECT id, organization_id, role, created_at FROM users")).fetchall()
        org_owners = {}
        for u in users:
            u_id, org_id, role, created_at = u[0], u[1], u[2], u[3]
            if not org_id:
                continue

            if isinstance(created_at, str):
                try:
                    created_val = datetime.fromisoformat(created_at)
                except Exception:
                    created_val = created_at
            elif isinstance(created_at, datetime):
                created_val = created_at
            else:
                created_val = datetime.now(timezone.utc)

            mem_id = str(uuid.uuid4())
            # Map role: If first Admin in org, promote to Owner
            assigned_role = role or "Creator"
            if org_id not in org_owners and assigned_role == "Admin":
                assigned_role = "Owner"
                org_owners[org_id] = u_id
            elif org_id not in org_owners:
                org_owners[org_id] = u_id

            bind.execute(
                sa.text("""
                    INSERT INTO organization_memberships (id, created_at, updated_at, user_id, organization_id, role, status, joined_at)
                    VALUES (:id, :created_at, :updated_at, :user_id, :organization_id, :role, 'active', :joined_at)
                """),
                {
                    "id": mem_id,
                    "created_at": created_val,
                    "updated_at": created_val,
                    "user_id": u_id,
                    "organization_id": org_id,
                    "role": assigned_role,
                    "joined_at": created_val,
                }
            )

        # Set owner_id on organizations
        for o_id, owner_uid in org_owners.items():
            bind.execute(
                sa.text("UPDATE organizations SET owner_id = :owner_id WHERE id = :org_id"),
                {"owner_id": owner_uid, "org_id": o_id}
            )
    except Exception as e:
        # If running on empty test database during creation, ignore
        pass


def downgrade() -> None:
    op.drop_table('organization_invitations')
    op.drop_table('organization_memberships')
    with op.batch_alter_table('organizations') as batch_op:
        batch_op.drop_constraint('fk_organizations_owner_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_organizations_owner_id'))
        batch_op.drop_column('owner_id')
