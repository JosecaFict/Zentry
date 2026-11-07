"""Copy Capricho Store seasons and collections into the ten demo tenants."""

import sqlalchemy as sa

from alembic import op

revision = "20261107_0022"
down_revision = "20261107_0021"
branch_labels = None
depends_on = None

DEMO_SLUGS = (
    "casa-elena",
    "nova-moda",
    "urban-style",
    "bella-boutique",
    "andina-fashion",
    "prisma-store",
    "elite-moda",
    "vertice",
    "magnolia",
    "altura-comercial",
)


def upgrade() -> None:
    connection = op.get_bind()
    source_id = connection.execute(
        sa.text("SELECT id_tenant FROM capricho.tenant WHERE slug = 'capricho-store'")
    ).scalar_one_or_none()
    if source_id is None:
        raise RuntimeError("No existe Capricho Store para copiar temporadas y colecciones")
    source_seasons = connection.execute(
        sa.text("SELECT count(*) FROM capricho.temporada WHERE id_tenant = :source"),
        {"source": source_id},
    ).scalar_one()
    if source_seasons == 0:
        raise RuntimeError("Capricho Store no tiene temporadas para copiar")
    source_collections = connection.execute(
        sa.text("SELECT count(*) FROM capricho.coleccion WHERE id_tenant = :source"),
        {"source": source_id},
    ).scalar_one()
    if source_collections == 0:
        raise RuntimeError("Capricho Store no tiene colecciones para copiar")

    targets = (
        connection.execute(
            sa.text("SELECT id_tenant FROM capricho.tenant WHERE slug IN :slugs").bindparams(
                sa.bindparam("slugs", expanding=True)
            ),
            {"slugs": DEMO_SLUGS},
        )
        .scalars()
        .all()
    )
    if targets and len(targets) != len(DEMO_SLUGS):
        raise RuntimeError("No se encontraron las diez empresas demo para completar la copia")
    for tenant_id in targets:
        connection.execute(
            sa.text("""
                INSERT INTO capricho.temporada
                    (id_tenant, nombre, anio, fecha_inicio, fecha_fin, activo)
                SELECT :target, source.nombre, source.anio,
                       source.fecha_inicio, source.fecha_fin, source.activo
                  FROM capricho.temporada source
                 WHERE source.id_tenant = :source
                   AND NOT EXISTS (
                       SELECT 1 FROM capricho.temporada existing
                        WHERE existing.id_tenant = :target
                          AND existing.nombre = source.nombre
                          AND existing.anio IS NOT DISTINCT FROM source.anio
                   )
            """),
            {"source": source_id, "target": tenant_id},
        )
        connection.execute(
            sa.text("""
                INSERT INTO capricho.coleccion
                    (id_tenant, id_temporada, nombre, descripcion, activo)
                SELECT :target, target_season.id_temporada,
                       source.nombre, source.descripcion, source.activo
                  FROM capricho.coleccion source
                  LEFT JOIN capricho.temporada source_season
                    ON source_season.id_temporada = source.id_temporada
                   AND source_season.id_tenant = :source
                  LEFT JOIN LATERAL (
                      SELECT candidate.id_temporada
                        FROM capricho.temporada candidate
                       WHERE candidate.id_tenant = :target
                         AND candidate.nombre = source_season.nombre
                         AND candidate.anio IS NOT DISTINCT FROM source_season.anio
                       ORDER BY candidate.id_temporada LIMIT 1
                  ) target_season ON TRUE
                 WHERE source.id_tenant = :source
                   AND NOT EXISTS (
                       SELECT 1 FROM capricho.coleccion existing
                        WHERE existing.id_tenant = :target
                          AND existing.nombre = source.nombre
                   )
            """),
            {"source": source_id, "target": tenant_id},
        )


def downgrade() -> None:
    raise RuntimeError("No se eliminan datos de catálogo de empresas al revertir la migración")
