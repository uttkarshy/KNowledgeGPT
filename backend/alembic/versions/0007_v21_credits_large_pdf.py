"""V2.1 credit accounting and large-document progress; preserves all data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0007_v21_credits_large_pdf"
down_revision = "0006_citation_order"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("plan_code", sa.String(32), nullable=False, server_default="starter"))
    op.add_column("users", sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="100"))
    op.create_check_constraint("ck_users_credit_balance_nonnegative", "users", "credit_balance >= 0")
    op.add_column("documents", sa.Column("processed_page_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("estimated_credits", sa.Integer(), nullable=True))
    op.add_column("api_usage_logs", sa.Column("operation", sa.String(64), nullable=True))
    op.add_column("api_usage_logs", sa.Column("credits_delta", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("api_usage_logs", sa.Column("idempotency_key", sa.String(255), nullable=True))
    op.add_column("api_usage_logs", sa.Column("usage_metadata", pg.JSONB(), nullable=True))
    op.create_index("ix_api_usage_logs_operation", "api_usage_logs", ["operation"])
    op.create_unique_constraint("uq_api_usage_idempotency_key", "api_usage_logs", ["idempotency_key"])
    op.create_table(
        "credit_purchases",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pack_code", sa.String(64), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("provider_order_id", sa.String(128), nullable=True),
        sa.Column("provider_payment_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider_order_id", name="uq_credit_purchase_provider_order"),
        sa.UniqueConstraint("provider_payment_id", name="uq_credit_purchase_provider_payment"),
    )
    op.create_index("ix_credit_purchases_user_id", "credit_purchases", ["user_id"])


def downgrade():
    op.drop_table("credit_purchases")
    op.drop_constraint("uq_api_usage_idempotency_key", "api_usage_logs", type_="unique")
    op.drop_index("ix_api_usage_logs_operation", table_name="api_usage_logs")
    for name in ("usage_metadata", "idempotency_key", "credits_delta", "operation"):
        op.drop_column("api_usage_logs", name)
    for name in ("estimated_credits", "processed_page_count"):
        op.drop_column("documents", name)
    op.drop_constraint("ck_users_credit_balance_nonnegative", "users", type_="check")
    op.drop_column("users", "credit_balance")
    op.drop_column("users", "plan_code")
