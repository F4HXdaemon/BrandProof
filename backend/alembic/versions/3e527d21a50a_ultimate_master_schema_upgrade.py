"""ultimate_master_schema_upgrade

Revision ID: 3e527d21a50a
Revises: bc1315ede22b
Create Date: 2026-11-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e527d21a50a'
down_revision: Union[str, Sequence[str], None] = 'bc1315ede22b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Guidelines
    with op.batch_alter_table('guidelines') as batch_op:
        batch_op.add_column(sa.Column('principle', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('do_examples', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('dont_examples', sa.JSON(), nullable=False, server_default='[]'))

    # 2. Approved Assets
    op.create_table(
        'approved_assets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('asset_type', sa.String(length=50), nullable=False, server_default='logo'),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('expected_width', sa.Float(), nullable=True),
        sa.Column('expected_height', sa.Float(), nullable=True),
        sa.Column('aspect_ratio', sa.Float(), nullable=True),
        sa.Column('allowed_ratio_deviation', sa.Float(), nullable=False, server_default='0.05'),
        sa.Column('source_reference', sa.String(length=500), nullable=True),
        sa.Column('product_scope', sa.String(length=100), nullable=False, server_default='All'),
        sa.Column('region_scope', sa.String(length=100), nullable=False, server_default='Global'),
        sa.Column('channel_scope', sa.String(length=100), nullable=False, server_default='All'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='Approved'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approved_assets_id'), 'approved_assets', ['id'], unique=False)
    op.create_index(op.f('ix_approved_assets_organization_id'), 'approved_assets', ['organization_id'], unique=False)

    # 3. Document Versions
    with op.batch_alter_table('document_versions') as batch_op:
        batch_op.add_column(sa.Column('parent_version_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('change_reason', sa.Text(), nullable=True))
        batch_op.create_foreign_key('fk_document_versions_parent_version_id', 'document_versions', ['parent_version_id'], ['id'], ondelete='SET NULL')

    # 4. Claims
    with op.batch_alter_table('claims') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('document_version_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('claim_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('normalized_claim', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('page_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('paragraph_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('claim_type', sa.String(length=50), nullable=False, server_default='Factual'))
        batch_op.add_column(sa.Column('matched_fact_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('reasoning', sa.Text(), nullable=True))
        batch_op.create_foreign_key('fk_claims_org', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_claims_doc_ver', 'document_versions', ['document_version_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_claims_fact', 'facts', ['matched_fact_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(op.f('ix_claims_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(op.f('ix_claims_document_version_id'), ['document_version_id'], unique=False)
        batch_op.create_index(op.f('ix_claims_matched_fact_id'), ['matched_fact_id'], unique=False)

    # 5. Findings
    with op.batch_alter_table('findings') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('document_version_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('finding_type', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('quoted_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('start_offset', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('end_offset', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('page_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('source_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('source_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('suggested_replacement', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('checker', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'))
        batch_op.add_column(sa.Column('dismissal_reason', sa.Text(), nullable=True))
        batch_op.create_foreign_key('fk_findings_org', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_findings_doc_ver', 'document_versions', ['document_version_id'], ['id'], ondelete='CASCADE')
        batch_op.create_index(op.f('ix_findings_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(op.f('ix_findings_document_version_id'), ['document_version_id'], unique=False)
        batch_op.create_index(op.f('ix_findings_finding_type'), ['finding_type'], unique=False)
        batch_op.create_index(op.f('ix_findings_source_id'), ['source_id'], unique=False)

    # 6. Approvals
    with op.batch_alter_table('approvals') as batch_op:
        batch_op.add_column(sa.Column('document_version_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('is_override', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()))
        batch_op.add_column(sa.Column('override_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('override_finding_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.create_foreign_key('fk_approvals_doc_ver', 'document_versions', ['document_version_id'], ['id'], ondelete='SET NULL')

    # 7. Comments
    op.create_table(
        'comments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('review_id', sa.String(length=36), nullable=False),
        sa.Column('finding_id', sa.String(length=36), nullable=True),
        sa.Column('author_id', sa.String(length=36), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.sql.expression.false()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['review_id'], ['reviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comments_id'), 'comments', ['id'], unique=False)
    op.create_index(op.f('ix_comments_organization_id'), 'comments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_comments_review_id'), 'comments', ['review_id'], unique=False)
    op.create_index(op.f('ix_comments_finding_id'), 'comments', ['finding_id'], unique=False)
    op.create_index(op.f('ix_comments_author_id'), 'comments', ['author_id'], unique=False)


def downgrade() -> None:
    op.drop_table('comments')
    with op.batch_alter_table('approvals') as batch_op:
        batch_op.drop_column('override_finding_ids')
        batch_op.drop_column('override_reason')
        batch_op.drop_column('is_override')
        batch_op.drop_column('document_version_id')

    with op.batch_alter_table('findings') as batch_op:
        batch_op.drop_column('dismissal_reason')
        batch_op.drop_column('confidence')
        batch_op.drop_column('checker')
        batch_op.drop_column('suggested_replacement')
        batch_op.drop_column('source_id')
        batch_op.drop_column('source_type')
        batch_op.drop_column('page_number')
        batch_op.drop_column('end_offset')
        batch_op.drop_column('start_offset')
        batch_op.drop_column('quoted_text')
        batch_op.drop_column('title')
        batch_op.drop_column('finding_type')
        batch_op.drop_column('document_version_id')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('claims') as batch_op:
        batch_op.drop_column('reasoning')
        batch_op.drop_column('matched_fact_id')
        batch_op.drop_column('claim_type')
        batch_op.drop_column('paragraph_number')
        batch_op.drop_column('page_number')
        batch_op.drop_column('normalized_claim')
        batch_op.drop_column('claim_text')
        batch_op.drop_column('document_version_id')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('document_versions') as batch_op:
        batch_op.drop_column('change_reason')
        batch_op.drop_column('parent_version_id')

    op.drop_table('approved_assets')

    with op.batch_alter_table('guidelines') as batch_op:
        batch_op.drop_column('dont_examples')
        batch_op.drop_column('do_examples')
        batch_op.drop_column('principle')
