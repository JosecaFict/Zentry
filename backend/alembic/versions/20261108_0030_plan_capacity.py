"""Serialize active capacity changes with subscription updates."""

from alembic import op

revision = "20261108_0030"
down_revision = "20261108_0029"
branch_labels = None
depends_on = None

RESOURCES = (
    ("sucursal", "activo", "TRUE", "max_sucursales_activas", "sucursales activas"),
    ("empleado", "estado_laboral", "ACTIVO", "max_usuarios_internos", "usuarios internos activos"),
    ("producto", "activo", "TRUE", "max_productos_activos", "productos activos"),
)


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION capricho.fn_check_plan_capacity() RETURNS trigger
        LANGUAGE plpgsql VOLATILE
        SET search_path = pg_catalog, pg_temp
        AS $$
        DECLARE
            plan_id bigint;
            max_active integer;
            active_count bigint;
        BEGIN
            -- The plan editor locks this same row before counting resources.
            SELECT s.id_plan INTO plan_id
            FROM capricho.subscription s
            WHERE s.id_tenant = NEW.id_tenant
                AND s.estado IN ('ACTIVA', 'POR_VENCER', 'GRACIA', 'SUSPENDIDA')
            FOR UPDATE;

            IF NOT FOUND THEN
                RETURN NEW;
            END IF;

            EXECUTE format('SELECT %I FROM capricho.plan WHERE id_plan = $1', TG_ARGV[0])
                INTO max_active USING plan_id;

            -- Run separately after locking to see changes committed while waiting.
            EXECUTE format(
                'SELECT count(*) FROM capricho.%I WHERE id_tenant = $1 AND %I = %L',
                TG_TABLE_NAME, TG_ARGV[1], TG_ARGV[2]
            ) INTO active_count USING NEW.id_tenant;

            IF active_count >= max_active THEN
                RAISE EXCEPTION USING
                    ERRCODE = 'PZ001',
                    MESSAGE = format('El plan permite hasta %s %s.', max_active, TG_ARGV[3]);
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    for table, field, active_value, limit, label in RESOURCES:
        active = f"'{active_value}'"
        function = (
            f"capricho.fn_check_plan_capacity('{limit}', '{field}', "
            f"'{active_value}', '{label}')"
        )
        op.execute(f"""
            CREATE TRIGGER check_plan_capacity_insert
            BEFORE INSERT ON capricho.{table}
            FOR EACH ROW WHEN (NEW.{field} = {active})
            EXECUTE FUNCTION {function};
        """)
        op.execute(f"""
            CREATE TRIGGER check_plan_capacity_update
            BEFORE UPDATE OF {field}, id_tenant ON capricho.{table}
            FOR EACH ROW WHEN (
                NEW.{field} = {active} AND (
                    OLD.{field} IS DISTINCT FROM NEW.{field}
                    OR OLD.id_tenant IS DISTINCT FROM NEW.id_tenant
                )
            )
            EXECUTE FUNCTION {function};
        """)


def downgrade() -> None:
    for table, *_ in RESOURCES:
        op.execute(f"DROP TRIGGER check_plan_capacity_update ON capricho.{table}")
        op.execute(f"DROP TRIGGER check_plan_capacity_insert ON capricho.{table}")
    op.execute("DROP FUNCTION capricho.fn_check_plan_capacity()")
