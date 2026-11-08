"""Store the precise variant requested for a size or color exchange."""

import sqlalchemy as sa
from alembic import op

revision = "20261107_0027"
down_revision = "20261107_0026"
branch_labels = None
depends_on = None

VALIDATION_SQL = '''
    CREATE OR REPLACE FUNCTION capricho.fn_validar_variante_solicitada() RETURNS trigger
    LANGUAGE plpgsql SET search_path=capricho,pg_temp AS $$
    BEGIN
      IF NEW.id_variante_solicitada IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM capricho.variante_producto v
        JOIN capricho.producto p ON p.id_producto=v.id_producto
        JOIN capricho.devolucion d ON d.id_devolucion=NEW.id_devolucion
        WHERE v.id_variante=NEW.id_variante_solicitada AND p.id_tenant=d.id_tenant
      ) THEN
        RAISE EXCEPTION 'La variante solicitada no pertenece a la empresa de la devolución';
      END IF;
      RETURN NEW;
    END; $$;
'''


def upgrade() -> None:
    op.add_column('detalle_devolucion', sa.Column('id_variante_solicitada', sa.BigInteger(), nullable=True), schema='capricho')
    op.create_foreign_key('fk_devolucion_variante_solicitada', 'detalle_devolucion', 'variante_producto',
                          ['id_variante_solicitada'], ['id_variante'], source_schema='capricho', referent_schema='capricho')
    op.execute(VALIDATION_SQL)
    op.execute('CREATE TRIGGER validar_variante_solicitada BEFORE INSERT OR UPDATE ON capricho.detalle_devolucion FOR EACH ROW EXECUTE FUNCTION capricho.fn_validar_variante_solicitada()')


def downgrade() -> None:
    op.execute('DROP TRIGGER validar_variante_solicitada ON capricho.detalle_devolucion')
    op.execute('DROP FUNCTION capricho.fn_validar_variante_solicitada()')
    op.drop_constraint('fk_devolucion_variante_solicitada', 'detalle_devolucion', schema='capricho', type_='foreignkey')
    op.drop_column('detalle_devolucion', 'id_variante_solicitada', schema='capricho')
