"""Add payment method required confirmations

Revision ID: 28a96effc3c0
Revises: 362b6679dc29
Create Date: 2026-11-04 23:50:08.623084

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "28a96effc3c0"
down_revision = "362b6679dc29"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    op.add_column("paymentmethods", sa.Column("required_confirmations", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE paymentmethods AS method
        SET required_confirmations = CASE
            WHEN method.lightning THEN 0
            ELSE COALESCE(
                (SELECT wallet.transaction_speed FROM wallets AS wallet WHERE wallet.id = method.wallet_id),
                (
                    SELECT (store.checkout_settings ->> 'transaction_speed')::integer
                    FROM invoices AS invoice
                    JOIN stores AS store ON store.id = invoice.store_id
                    WHERE invoice.id = method.invoice_id
                ),
                0
            )
        END
        """
    )
    op.alter_column("paymentmethods", "required_confirmations", nullable=False)


def downgrade() -> None:
    op.drop_column("paymentmethods", "required_confirmations")
