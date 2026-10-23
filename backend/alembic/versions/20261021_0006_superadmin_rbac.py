"""Create global Superadmin role and platform permissions.

Revision ID: 20261021_0006
Revises: 20261021_0005
"""

from alembic import op

revision = "20261021_0006"
down_revision = "20261021_0005"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("platform.overview.ver", "Ver resumen de plataforma"),
    ("platform.tenants.ver", "Ver empresas"),
    ("platform.tenants.gestionar", "Gestionar empresas"),
    ("platform.subscriptions.gestionar", "Gestionar suscripciones"),
    ("platform.plans.ver", "Ver planes"),
    ("platform.audit.ver", "Ver auditoría de plataforma"),
)


def upgrade() -> None:
    values = ", ".join(
        f"('{code}', '{name}', 'PLATAFORMA')" for code, name in PERMISSIONS
    )
    op.execute(
        f"""
        INSERT INTO capricho.permiso(codigo, nombre, modulo)
        VALUES {values}
        ON CONFLICT (codigo) DO UPDATE
        SET nombre = EXCLUDED.nombre, modulo = EXCLUDED.modulo, activo = true
        """
    )
    op.execute(
        """
        INSERT INTO capricho.rol(id_tenant, alcance, nombre, descripcion, activo)
        VALUES (NULL, 'GLOBAL', 'SUPERADMIN', 'Administrador global de Zentry', true)
        ON CONFLICT (nombre) DO UPDATE
        SET id_tenant = NULL, alcance = 'GLOBAL', activo = true
        """
    )
    op.execute(
        """
        INSERT INTO capricho.rol_permiso(id_rol, id_permiso)
        SELECT role.id_rol, permission.id_permiso
        FROM capricho.rol role
        CROSS JOIN capricho.permiso permission
        WHERE role.nombre = 'SUPERADMIN'
          AND permission.codigo LIKE 'platform.%'
        ON CONFLICT (id_rol, id_permiso) DO NOTHING
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Superadmin RBAC downgrade can revoke access; restore a verified backup instead"
    )
