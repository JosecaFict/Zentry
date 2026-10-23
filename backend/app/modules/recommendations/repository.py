from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Cliente
from app.modules.catalog.models import (
    Categoria,
    HistorialPrecio,
    ImagenProducto,
    Marca,
    Producto,
    ProductoTemporada,
    Temporada,
    VarianteProducto,
)
from app.modules.recommendations.models import (
    ConfiguracionRecomendador,
    InteraccionProducto,
    Recomendacion,
)
from app.modules.recommendations.schemas import RecommendationConfigUpdate

INTERACTION_WEIGHTS = {
    "COMPRAR": 10.0,
    "AGREGAR_CARRITO": 5.0,
    "USAR_VESTIDOR": 3.0,
    "VER_PRODUCTO": 1.0,
    "QUITAR_CARRITO": -2.0,
}


class RecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_config(self) -> ConfiguracionRecomendador:
        statement = select(ConfiguracionRecomendador).where(
            ConfiguracionRecomendador.activo.is_(True)
        )
        config = await self.session.scalar(statement)
        if config is None:
            config = ConfiguracionRecomendador(
                peso_categoria=Decimal("40.00"),
                peso_marca=Decimal("20.00"),
                peso_color=Decimal("15.00"),
                peso_talla=Decimal("10.00"),
                peso_temporada=Decimal("10.00"),
                peso_promocion=Decimal("5.00"),
                activo=True,
            )
            self.session.add(config)
            await self.session.flush()
        return config

    async def update_active_config(
        self, payload: RecommendationConfigUpdate
    ) -> ConfiguracionRecomendador:
        config = await self.get_active_config()
        config.peso_categoria = payload.peso_categoria
        config.peso_marca = payload.peso_marca
        config.peso_color = payload.peso_color
        config.peso_talla = payload.peso_talla
        config.peso_temporada = payload.peso_temporada
        config.peso_promocion = payload.peso_promocion
        await self.session.flush()
        return config

    async def record_interaction(
        self,
        client_id: int,
        product_id: int,
        variant_id: int | None = None,
        interaction_type: str = "VER_PRODUCTO",
    ) -> InteraccionProducto:
        interaction = InteraccionProducto(
            id_cliente=client_id,
            id_producto=product_id,
            id_variante=variant_id,
            tipo_interaccion=interaction_type,
        )
        self.session.add(interaction)
        await self.session.flush()
        return interaction

    async def get_client_by_user_id(self, user_id: int) -> Cliente | None:
        statement = select(Cliente).where(Cliente.id_usuario == user_id)
        return await self.session.scalar(statement)

    async def get_client_preference_profile(
        self, client_id: int
    ) -> dict[str, dict[int, float]]:
        """
        Builds an aggregated affinity profile for the client based on interaction weights.
        Returns:
            {
                "categories": { id_categoria: score, ... },
                "brands": { id_marca: score, ... },
                "colors": { id_color: score, ... },
                "sizes": { id_talla: score, ... }
            }
        """
        statement = (
            select(
                InteraccionProducto.tipo_interaccion,
                Producto.id_categoria,
                Producto.id_marca,
                VarianteProducto.id_color,
                VarianteProducto.id_talla,
            )
            .join(Producto, Producto.id_producto == InteraccionProducto.id_producto)
            .outerjoin(
                VarianteProducto,
                VarianteProducto.id_variante == InteraccionProducto.id_variante,
            )
            .where(InteraccionProducto.id_cliente == client_id)
            .order_by(InteraccionProducto.fecha_hora.desc())
            .limit(200)
        )
        rows = (await self.session.execute(statement)).all()

        cat_affinity: dict[int, float] = {}
        brand_affinity: dict[int, float] = {}
        color_affinity: dict[int, float] = {}
        size_affinity: dict[int, float] = {}

        for row in rows:
            tipo, cat_id, brand_id, color_id, size_id = row
            w = INTERACTION_WEIGHTS.get(tipo, 1.0)
            if cat_id:
                cat_affinity[cat_id] = cat_affinity.get(cat_id, 0.0) + w
            if brand_id:
                brand_affinity[brand_id] = brand_affinity.get(brand_id, 0.0) + w
            if color_id:
                color_affinity[color_id] = color_affinity.get(color_id, 0.0) + w
            if size_id:
                size_affinity[size_id] = size_affinity.get(size_id, 0.0) + w

        return {
            "categories": cat_affinity,
            "brands": brand_affinity,
            "colors": color_affinity,
            "sizes": size_affinity,
        }

    async def get_catalog_products_for_scoring(
        self, limit: int = 100
    ) -> list[dict]:
        """
        Fetches active catalog products with their associated metadata for score calculation.
        """
        price_subq = (
            select(HistorialPrecio.precio)
            .where(
                HistorialPrecio.id_producto == Producto.id_producto,
                HistorialPrecio.fecha_fin.is_(None),
            )
            .order_by(HistorialPrecio.fecha_inicio.desc())
            .limit(1)
            .scalar_subquery()
        )
        image_subq = (
            select(ImagenProducto.secure_url)
            .where(
                ImagenProducto.id_producto == Producto.id_producto,
                ImagenProducto.es_principal.is_(True),
            )
            .order_by(ImagenProducto.orden)
            .limit(1)
            .scalar_subquery()
        )

        statement = (
            select(
                Producto.id_producto,
                Producto.nombre,
                Producto.id_categoria,
                Categoria.nombre.label("categoria_nombre"),
                Producto.id_marca,
                Marca.nombre.label("marca_nombre"),
                price_subq.label("precio_actual"),
                image_subq.label("imagen_url"),
            )
            .join(Categoria, Categoria.id_categoria == Producto.id_categoria)
            .join(Marca, Marca.id_marca == Producto.id_marca)
            .where(Producto.activo.is_(True))
            .limit(limit)
        )
        products = (await self.session.execute(statement)).mappings().all()
        results: list[dict] = []

        for p in products:
            pid = p["id_producto"]
            variants_stmt = select(
                VarianteProducto.id_color, VarianteProducto.id_talla
            ).where(VarianteProducto.id_producto == pid, VarianteProducto.activo.is_(True))
            v_rows = (await self.session.execute(variants_stmt)).all()
            color_ids = {r[0] for r in v_rows if r[0] is not None}
            size_ids = {r[1] for r in v_rows if r[1] is not None}

            temp_stmt = select(ProductoTemporada.id_temporada).where(
                ProductoTemporada.id_producto == pid
            )
            temp_ids = set((await self.session.scalars(temp_stmt)).all())

            results.append(
                {
                    "id_producto": pid,
                    "nombre": p["nombre"],
                    "id_categoria": p["id_categoria"],
                    "categoria": p["categoria_nombre"],
                    "id_marca": p["id_marca"],
                    "marca": p["marca_nombre"],
                    "precio_actual": Decimal(str(p["precio_actual"])) if p["precio_actual"] is not None else None,
                    "imagen_url": p["imagen_url"],
                    "color_ids": color_ids,
                    "size_ids": size_ids,
                    "temporada_ids": temp_ids,
                }
            )
        return results

    async def get_active_season_ids(self) -> set[int]:
        now = datetime.now(UTC).date()
        statement = select(Temporada.id_temporada).where(
            Temporada.activo.is_(True),
            or_(
                Temporada.fecha_fin.is_(None),
                Temporada.fecha_fin >= now,
            ),
        )
        return set((await self.session.scalars(statement)).all())

    async def get_interaction_stats(self) -> dict:
        total = await self.session.scalar(select(func.count(InteraccionProducto.id_interaccion))) or 0
        statement = select(
            InteraccionProducto.tipo_interaccion,
            func.count(InteraccionProducto.id_interaccion),
        ).group_by(InteraccionProducto.tipo_interaccion)
        by_type_rows = (await self.session.execute(statement)).all()
        by_type = {row[0]: int(row[1]) for row in by_type_rows}

        unique_clients = (
            await self.session.scalar(
                select(func.count(func.distinct(InteraccionProducto.id_cliente)))
            )
            or 0
        )
        return {
            "total_interacciones": int(total),
            "interacciones_por_tipo": by_type,
            "clientes_con_interacciones": int(unique_clients),
        }

    async def save_recommendation_history(
        self, client_id: int, product_id: int, score: Decimal, reason: str
    ) -> None:
        rec = Recomendacion(
            id_cliente=client_id,
            id_producto=product_id,
            puntuacion=score,
            motivo=reason,
        )
        self.session.add(rec)
        await self.session.flush()
