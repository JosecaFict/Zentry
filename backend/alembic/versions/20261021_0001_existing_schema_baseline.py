"""Adopt the restored Capricho Store schema without recreating it.

Revision ID: 20261021_0001
Revises:
"""

import sqlalchemy as sa

from alembic import op

revision = "20261021_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    required = {"usuario", "rol", "sucursal", "producto", "venta", "reserva"}
    present = set(
        connection.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'capricho' AND table_type = 'BASE TABLE'"
            )
        ).scalars()
    )
    missing = required - present
    if missing:
        raise RuntimeError(f"Existing capricho schema is incomplete: {sorted(missing)}")


def downgrade() -> None:
    # The baseline owns no pre-existing objects.
    pass
