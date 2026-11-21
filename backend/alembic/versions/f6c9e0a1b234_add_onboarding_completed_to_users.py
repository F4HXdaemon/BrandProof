"""add_onboarding_completed_to_users

Revision ID: f6c9e0a1b234
Revises: e5b8d9f0a123
Create Date: 2026-11-21 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6c9e0a1b234'
down_revision: Union[str, Sequence[str], None] = 'e5b8d9f0a123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column(
                'onboarding_completed',
                sa.Boolean(),
                nullable=False,
                server_default=sa.sql.expression.false()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('onboarding_completed')
