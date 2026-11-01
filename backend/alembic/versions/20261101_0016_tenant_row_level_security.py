"""Enforce tenant isolation with PostgreSQL row-level security.

Revision ID: 20261101_0016
Revises: 20261029_0015
"""

from alembic import op

revision = "20261101_0016"
down_revision = "20261029_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION capricho.fn_rls_tenant_id()
        RETURNS BIGINT
        LANGUAGE sql
        STABLE
        SET search_path = pg_catalog, pg_temp
        AS $$
          SELECT NULLIF(current_setting('app.tenant_id', TRUE), '')::BIGINT
        $$;

        CREATE OR REPLACE FUNCTION capricho.fn_rls_scope()
        RETURNS TEXT
        LANGUAGE sql
        STABLE
        SET search_path = pg_catalog, pg_temp
        AS $$
          SELECT COALESCE(
            NULLIF(current_setting('app.rls_scope', TRUE), ''),
            'restricted'
          )
        $$;
        """
    )
    op.execute(
        """
        DO $rls$
        DECLARE
          target RECORD;
        BEGIN
          FOR target IN
            SELECT DISTINCT c.relname AS table_name
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = 'capricho'
              AND c.relkind IN ('r', 'p')
              AND a.attname = 'id_tenant'
              AND NOT a.attisdropped
              AND c.relname <> 'tenant'
          LOOP
            EXECUTE format(
              'ALTER TABLE capricho.%I ENABLE ROW LEVEL SECURITY',
              target.table_name
            );
            EXECUTE format(
              'ALTER TABLE capricho.%I FORCE ROW LEVEL SECURITY',
              target.table_name
            );
            EXECUTE format(
              'DROP POLICY IF EXISTS tenant_isolation ON capricho.%I',
              target.table_name
            );
            EXECUTE format(
              'CREATE POLICY tenant_isolation ON capricho.%I '
              'FOR ALL USING ('
              'capricho.fn_rls_scope() = ''global'' OR '
              'id_tenant = capricho.fn_rls_tenant_id() OR '
              '(capricho.fn_rls_scope() = ''identity'' AND id_tenant IS NULL)'
              ') WITH CHECK ('
              'capricho.fn_rls_scope() = ''global'' OR '
              'id_tenant = capricho.fn_rls_tenant_id() OR '
              '(capricho.fn_rls_scope() = ''identity'' AND id_tenant IS NULL)'
              ')',
              target.table_name
            );
          END LOOP;
        END
        $rls$;
        """
    )
    op.execute(
        """
        ALTER TABLE capricho.tenant ENABLE ROW LEVEL SECURITY;
        ALTER TABLE capricho.tenant FORCE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS tenant_public_read ON capricho.tenant;
        DROP POLICY IF EXISTS tenant_global_insert ON capricho.tenant;
        DROP POLICY IF EXISTS tenant_scoped_update ON capricho.tenant;
        DROP POLICY IF EXISTS tenant_global_delete ON capricho.tenant;

        CREATE POLICY tenant_public_read ON capricho.tenant
          FOR SELECT USING (
            estado = 'ACTIVO'
            OR capricho.fn_rls_scope() = 'global'
            OR id_tenant = capricho.fn_rls_tenant_id()
          );

        CREATE POLICY tenant_global_insert ON capricho.tenant
          FOR INSERT WITH CHECK (capricho.fn_rls_scope() = 'global');

        CREATE POLICY tenant_scoped_update ON capricho.tenant
          FOR UPDATE USING (
            capricho.fn_rls_scope() = 'global'
            OR id_tenant = capricho.fn_rls_tenant_id()
          ) WITH CHECK (
            capricho.fn_rls_scope() = 'global'
            OR id_tenant = capricho.fn_rls_tenant_id()
          );

        CREATE POLICY tenant_global_delete ON capricho.tenant
          FOR DELETE USING (capricho.fn_rls_scope() = 'global');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $rls$
        DECLARE
          target RECORD;
        BEGIN
          FOR target IN
            SELECT DISTINCT c.relname AS table_name
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = 'capricho'
              AND c.relkind IN ('r', 'p')
              AND a.attname = 'id_tenant'
              AND NOT a.attisdropped
          LOOP
            EXECUTE format(
              'DROP POLICY IF EXISTS tenant_isolation ON capricho.%I',
              target.table_name
            );
            EXECUTE format(
              'ALTER TABLE capricho.%I NO FORCE ROW LEVEL SECURITY',
              target.table_name
            );
            EXECUTE format(
              'ALTER TABLE capricho.%I DISABLE ROW LEVEL SECURITY',
              target.table_name
            );
          END LOOP;
        END
        $rls$;

        DROP POLICY IF EXISTS tenant_public_read ON capricho.tenant;
        DROP POLICY IF EXISTS tenant_global_insert ON capricho.tenant;
        DROP POLICY IF EXISTS tenant_scoped_update ON capricho.tenant;
        DROP POLICY IF EXISTS tenant_global_delete ON capricho.tenant;
        DROP FUNCTION IF EXISTS capricho.fn_rls_scope();
        DROP FUNCTION IF EXISTS capricho.fn_rls_tenant_id();
        """
    )
