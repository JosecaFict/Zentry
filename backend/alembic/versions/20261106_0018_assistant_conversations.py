"""Persist tenant and user isolated assistant conversations."""

from alembic import op

revision = "20261106_0018"
down_revision = "20261106_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE capricho.usuario ADD CONSTRAINT uq_usuario_tenant_id UNIQUE (id_tenant, id_usuario)")
    op.execute("""
        CREATE TABLE capricho.asistente_conversacion (
            id_conversacion UUID PRIMARY KEY,
            id_tenant BIGINT NOT NULL REFERENCES capricho.tenant(id_tenant),
            id_usuario BIGINT NOT NULL,
            modo VARCHAR(10) NOT NULL CHECK (modo IN ('EMPRESA', 'CLIENTE')),
            proveedor VARCHAR(20) NOT NULL CHECK (proveedor IN ('GROQ', 'GEMINI')),
            modelo VARCHAR(100) NOT NULL,
            estado VARCHAR(12) NOT NULL DEFAULT 'ACTIVA' CHECK (estado IN ('ACTIVA', 'ARCHIVADA')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_asistente_usuario_tenant FOREIGN KEY (id_tenant, id_usuario)
                REFERENCES capricho.usuario (id_tenant, id_usuario) ON DELETE CASCADE,
            CONSTRAINT uq_asistente_conversacion_tenant_usuario UNIQUE (id_conversacion, id_tenant, id_usuario),
            CONSTRAINT ck_asistente_modo_proveedor CHECK (
                (modo = 'EMPRESA' AND proveedor = 'GROQ') OR
                (modo = 'CLIENTE' AND proveedor = 'GEMINI')
            )
        )
    """)
    op.execute("""
        CREATE TABLE capricho.asistente_mensaje (
            id_mensaje BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            id_conversacion UUID NOT NULL,
            id_tenant BIGINT NOT NULL,
            id_usuario BIGINT NOT NULL,
            rol VARCHAR(12) NOT NULL CHECK (rol IN ('USUARIO', 'ASISTENTE')),
            contenido TEXT NOT NULL CHECK (length(contenido) BETWEEN 1 AND 12000),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_asistente_mensaje_conversacion FOREIGN KEY
                (id_conversacion, id_tenant, id_usuario) REFERENCES capricho.asistente_conversacion
                (id_conversacion, id_tenant, id_usuario) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX ix_asistente_conversacion_usuario ON capricho.asistente_conversacion (id_tenant, id_usuario, modo, updated_at DESC)")
    op.execute("CREATE INDEX ix_asistente_mensaje_conversacion ON capricho.asistente_mensaje (id_conversacion, created_at, id_mensaje)")
    for table in ("asistente_conversacion", "asistente_mensaje"):
        op.execute(f"ALTER TABLE capricho.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE capricho.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY assistant_owner ON capricho.{table} FOR ALL
            USING (id_tenant = capricho.fn_rls_tenant_id()
               AND id_usuario = NULLIF(current_setting('app.usuario_id', true), '')::BIGINT)
            WITH CHECK (id_tenant = capricho.fn_rls_tenant_id()
               AND id_usuario = NULLIF(current_setting('app.usuario_id', true), '')::BIGINT)
        """)
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zentry_app') THEN
                GRANT SELECT, INSERT, UPDATE ON capricho.asistente_conversacion TO zentry_app;
                GRANT SELECT, INSERT ON capricho.asistente_mensaje TO zentry_app;
                GRANT USAGE, SELECT ON SEQUENCE capricho.asistente_mensaje_id_mensaje_seq TO zentry_app;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE capricho.asistente_mensaje")
    op.execute("DROP TABLE capricho.asistente_conversacion")
    op.execute("ALTER TABLE capricho.usuario DROP CONSTRAINT uq_usuario_tenant_id")
