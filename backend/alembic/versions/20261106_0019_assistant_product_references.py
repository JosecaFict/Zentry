"""Keep verified product references alongside assistant messages."""

from alembic import op

revision = "20261106_0019"
down_revision = "20261106_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE capricho.asistente_mensaje
        ADD COLUMN producto_ids BIGINT[] NOT NULL DEFAULT ARRAY[]::BIGINT[];
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE capricho.asistente_mensaje DROP COLUMN producto_ids")
