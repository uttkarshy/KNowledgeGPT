"""Preserve new citation numbering after reload; no guesses for historical order."""
import sqlalchemy as sa
from alembic import op

revision = "0006_citation_order"
down_revision = "0005_row_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_citations", sa.Column("source_index", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("chat_citations", "source_index")
