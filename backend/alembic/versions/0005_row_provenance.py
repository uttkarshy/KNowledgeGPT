"""Optional table/row provenance; existing vectors and documents remain valid."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_row_provenance"
down_revision = "0004_v2_processing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_chunks", sa.Column("structure", JSONB(), nullable=True))


def downgrade():
    op.drop_column("document_chunks", "structure")
