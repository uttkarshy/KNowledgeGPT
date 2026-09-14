"""Add session epochs for password-reset revocation without deleting data."""
from alembic import op
import sqlalchemy as sa

revision = "0003_token_version"
down_revision = "0002_embedding_contract"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("users", "refresh_tokens"):
        op.add_column(table, sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    for table in ("refresh_tokens", "users"):
        op.drop_column(table, "token_version")
