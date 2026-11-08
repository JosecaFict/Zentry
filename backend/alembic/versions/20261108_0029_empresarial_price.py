"""Set the monthly and annual prices for the Empresarial plan."""

from alembic import op

revision = "20261108_0029"
down_revision = "20261108_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE capricho.plan
        SET precio_mensual = 1500, precio_anual = 18000
        WHERE codigo = 'EMPRESARIAL'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE capricho.plan
        SET precio_mensual = 1200, precio_anual = 14400
        WHERE codigo = 'EMPRESARIAL'
    """)
