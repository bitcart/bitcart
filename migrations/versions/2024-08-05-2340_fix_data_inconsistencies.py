"""Fix data inconsistencies

Revision ID: c8dc03c2cf76
Revises: 1c45e078409d
Create Date: 2024-08-05 23:40:17.366979

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8dc03c2cf76"
down_revision: str | None = "1c45e078409d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE products SET templates='{}' where templates IS NULL")
    op.execute("UPDATE products SET image='' where image IS NULL")
    op.execute("UPDATE invoices SET promocode='' where promocode IS NULL")
    op.execute("UPDATE invoices SET shipping_address='' where shipping_address IS NULL")
    op.execute("UPDATE invoices SET notes='' where notes IS NULL")
    op.execute("UPDATE invoices SET redirect_url='' where redirect_url IS NULL")
    op.execute("UPDATE invoices SET notification_url='' where notification_url IS NULL")
    op.execute("UPDATE invoices SET buyer_email='' where buyer_email IS NULL")
    op.execute("UPDATE wallets SET hint='' where hint IS NULL")
    op.execute("UPDATE notifications SET provider='Telegram' where provider='telegram'")


def downgrade() -> None:
    pass
