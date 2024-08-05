"""Fix data inconsistencies

Revision ID: c8dc03c2cf76
Revises: 1c45e078409d
Create Date: 2024-08-05 23:40:17.366979

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c8dc03c2cf76"
down_revision = "1c45e078409d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE products SET templates='{}' where templates IS NULL")
    op.execute("UPDATE products SET image='' where image IS NULL")
    op.execute("UPDATE invoices SET promocode='' where promocode IS NULL")


def downgrade():
    pass
