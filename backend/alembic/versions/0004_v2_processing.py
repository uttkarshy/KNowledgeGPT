"""Durable retry state and unique chunk checkpoints; no existing rows deleted."""

import sqlalchemy as sa
from alembic import op

revision = "0004_v2_processing"
down_revision = "0003_token_version"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("automatic_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_rate_limit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("documents", column)
    op.execute("UPDATE documents SET confirmed_at=created_at WHERE status::text <> 'pending'")
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM document_chunks GROUP BY document_id,chunk_index HAVING count(*)>1) THEN
            RAISE EXCEPTION 'Duplicate chunk indices require operator review; migration deletes no rows.';
        END IF;
    END $$""")
    op.create_unique_constraint("uq_document_chunk_index", "document_chunks", ["document_id", "chunk_index"])


def downgrade():
    op.drop_constraint("uq_document_chunk_index", "document_chunks", type_="unique")
    for name in (
        "error_code",
        "retryable",
        "confirmed_at",
        "next_retry_at",
        "automatic_retries",
        "provider_rate_limit_count",
        "last_error_code",
        "last_error_at",
    ):
        op.drop_column("documents", name)
