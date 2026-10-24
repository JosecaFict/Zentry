"""Allow audit entries produced by global platform accounts.

Revision ID: 20261024_0013
Revises: 20261022_0012
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261024_0013"
down_revision: str | None = "20261022_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION capricho.fn_bitacora_generica()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        SET search_path = capricho, pg_temp
        AS $$
        DECLARE
          v_tenant BIGINT;
          v_usuario BIGINT;
          v_ip INET;
          v_origen VARCHAR(10);
          v_id TEXT;
          v_old JSONB;
          v_new JSONB;
        BEGIN
          BEGIN
            v_usuario := NULLIF(current_setting('app.usuario_id', TRUE), '')::BIGINT;
          EXCEPTION WHEN OTHERS THEN
            v_usuario := NULL;
          END;

          BEGIN
            v_ip := NULLIF(current_setting('app.ip', TRUE), '')::INET;
          EXCEPTION WHEN OTHERS THEN
            v_ip := NULL;
          END;

          v_origen := NULLIF(current_setting('app.origen', TRUE), '');

          IF TG_OP <> 'INSERT' THEN
            v_old := to_jsonb(OLD);
          END IF;
          IF TG_OP <> 'DELETE' THEN
            v_new := to_jsonb(NEW);
          END IF;

          IF TG_TABLE_NAME = 'usuario' THEN
            v_old := v_old - 'password_hash';
            v_new := v_new - 'password_hash';
          END IF;

          BEGIN
            v_tenant := COALESCE(
              NULLIF(v_new ->> 'id_tenant', '')::BIGINT,
              NULLIF(v_old ->> 'id_tenant', '')::BIGINT,
              NULLIF(current_setting('app.tenant_id', TRUE), '')::BIGINT
            );
          EXCEPTION WHEN OTHERS THEN
            v_tenant := NULL;
          END;

          IF TG_OP = 'INSERT' THEN
            v_id := COALESCE(v_new ->> TG_ARGV[1], '');
            INSERT INTO capricho.bitacora(
              id_tenant, id_usuario, id_sesion, accion, modulo, entidad,
              id_registro, datos_nuevos, direccion_ip, user_agent, origen,
              request_id
            ) VALUES (
              v_tenant, v_usuario,
              NULLIF(current_setting('app.sesion_id', TRUE), ''),
              TG_OP, TG_ARGV[0], TG_TABLE_NAME, v_id, v_new, v_ip,
              NULLIF(current_setting('app.user_agent', TRUE), ''),
              COALESCE(v_origen, 'SISTEMA'),
              NULLIF(current_setting('app.request_id', TRUE), '')
            );
            RETURN NEW;
          ELSIF TG_OP = 'UPDATE' THEN
            v_id := COALESCE(v_new ->> TG_ARGV[1], '');
            INSERT INTO capricho.bitacora(
              id_tenant, id_usuario, id_sesion, accion, modulo, entidad,
              id_registro, datos_anteriores, datos_nuevos, direccion_ip,
              user_agent, origen, request_id
            ) VALUES (
              v_tenant, v_usuario,
              NULLIF(current_setting('app.sesion_id', TRUE), ''),
              TG_OP, TG_ARGV[0], TG_TABLE_NAME, v_id, v_old, v_new, v_ip,
              NULLIF(current_setting('app.user_agent', TRUE), ''),
              COALESCE(v_origen, 'SISTEMA'),
              NULLIF(current_setting('app.request_id', TRUE), '')
            );
            RETURN NEW;
          ELSE
            v_id := COALESCE(v_old ->> TG_ARGV[1], '');
            INSERT INTO capricho.bitacora(
              id_tenant, id_usuario, id_sesion, accion, modulo, entidad,
              id_registro, datos_anteriores, direccion_ip, user_agent, origen,
              request_id
            ) VALUES (
              v_tenant, v_usuario,
              NULLIF(current_setting('app.sesion_id', TRUE), ''),
              TG_OP, TG_ARGV[0], TG_TABLE_NAME, v_id, v_old, v_ip,
              NULLIF(current_setting('app.user_agent', TRUE), ''),
              COALESCE(v_origen, 'SISTEMA'),
              NULLIF(current_setting('app.request_id', TRUE), '')
            );
            RETURN OLD;
          END IF;
        END;
        $$
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Global audit compatibility downgrade would break platform accounts; "
        "restore a backup instead"
    )
