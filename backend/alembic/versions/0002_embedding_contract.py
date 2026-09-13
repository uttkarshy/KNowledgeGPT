"""Validate the 1536-dimensional contract without discarding existing vectors.

Revision ID: 0002_embedding_contract
Revises: 0001_initial_schema
"""
from alembic import op

revision = "0002_embedding_contract"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    # An empty legacy 3072 table is safe to resize. Populated embeddings must
    # be regenerated from saved chunk text, never blindly truncated or deleted.
    op.execute("""
    DO $$
    DECLARE actual_type text;
    BEGIN
      SELECT format_type(atttypid, atttypmod) INTO actual_type
      FROM pg_attribute WHERE attrelid = 'document_chunks'::regclass
      AND attname = 'embedding';
      IF actual_type <> 'vector(1536)' THEN
        IF EXISTS (SELECT 1 FROM document_chunks LIMIT 1) THEN
          RAISE EXCEPTION 'Embedding schema mismatch: back up and re-embed saved chunk text into vector(1536) before upgrading';
        END IF;
        DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;
        ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536);
      END IF;
    END $$;
    """)
    op.execute("""CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)""")


def downgrade():
    # Validation adds no data or irreversible transformation to the 1536 schema.
    pass
