"""Fix html templates rendering

Revision ID: 5bf0a0845afb
Revises: e027e56adb58
Create Date: 2021-01-03 21:45:14.779772

"""

import sqlalchemy as sa
from sqlalchemy.sql import expression

from alembic import op

# revision identifiers, used by Alembic.
revision = "5bf0a0845afb"
down_revision = "e027e56adb58"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("stores", sa.Column("use_html_templates", sa.Boolean(), nullable=True, server_default=expression.false()))
    op.alter_column("stores", "use_html_templates", server_default=None)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("stores", "use_html_templates")
    # ### end Alembic commands ###
