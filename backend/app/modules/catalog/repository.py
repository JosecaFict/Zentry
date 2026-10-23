from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import Select, and_, asc, desc, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Ciudad, Sucursal
from app.modules.catalog.models import (
    Categoria,
    Coleccion,
    Color,
    HistorialPrecio,
    ImagenProducto,
    InventarioSucursal,
    Marca,
    MedidaTallaProducto,
    Producto,
    ProductoColeccion,
    ProductoTemporada,
    Talla,
    Temporada,
    VarianteProducto,
)

ModelT = TypeVar("ModelT")


@dataclass(frozen=True)
class ProductCore:
    product: Producto
    category: str
    brand: str
    current_price: Decimal | None


@dataclass(frozen=True)
class VariantRecord:
    variant: VarianteProducto
    size: str
    color: str
    hex_code: str | None
    available_stock: int | None
    minimum_stock: int | None


@dataclass(frozen=True)
class VariantOptionRecord:
    variant: VarianteProducto
    product_name: str
    size: str
    color: str


@dataclass(frozen=True)
class MeasurementRecord:
    measurement: MedidaTallaProducto
    size: str


@dataclass(frozen=True)
class BranchRecord:
    branch: Sucursal
    city: Ciudad


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_active_products(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Producto.id_producto)).where(Producto.activo.is_(True))
            )
            or 0
        )

    async def list_entities(self, model: type[ModelT], order_by: Any) -> list[ModelT]:
        return list((await self.session.scalars(select(model).order_by(order_by))).all())

    async def get_entity(
        self,
        model: type[ModelT],
        identity: int,
    ) -> ModelT | None:
        return await self.session.get(model, identity)

    async def find_by_name(
        self,
        model: type[ModelT],
        name_column: Any,
        name: str,
        *,
        exclude_id_column: Any | None = None,
        exclude_id: int | None = None,
    ) -> ModelT | None:
        statement = select(model).where(func.lower(name_column) == name.strip().lower())
        if exclude_id_column is not None and exclude_id is not None:
            statement = statement.where(exclude_id_column != exclude_id)
        return await self.session.scalar(statement)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def flush(self) -> None:
        await self.session.flush()

    async def list_active_branches(self) -> list[Sucursal]:
        statement = select(Sucursal).where(Sucursal.activo.is_(True)).order_by(Sucursal.nombre)
        return list((await self.session.scalars(statement)).all())

    async def list_active_cities(self) -> list[Ciudad]:
        statement = (
            select(Ciudad)
            .where(Ciudad.activo.is_(True))
            .order_by(Ciudad.departamento, Ciudad.nombre)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_branch_records(self) -> list[BranchRecord]:
        statement = (
            select(Sucursal, Ciudad)
            .join(Ciudad, Ciudad.id_ciudad == Sucursal.id_ciudad)
            .order_by(Sucursal.nombre)
        )
        return [BranchRecord(*row) for row in (await self.session.execute(statement)).all()]

    async def get_branch_record(self, branch_id: int) -> BranchRecord | None:
        statement = (
            select(Sucursal, Ciudad)
            .join(Ciudad, Ciudad.id_ciudad == Sucursal.id_ciudad)
            .where(Sucursal.id_sucursal == branch_id)
        )
        row = (await self.session.execute(statement)).one_or_none()
        return BranchRecord(*row) if row else None

    async def find_branch_by_city_and_name(
        self,
        city_id: int,
        name: str,
        *,
        exclude_branch_id: int | None = None,
    ) -> Sucursal | None:
        statement = select(Sucursal).where(
            Sucursal.id_ciudad == city_id,
            func.lower(Sucursal.nombre) == name.strip().lower(),
        )
        if exclude_branch_id is not None:
            statement = statement.where(Sucursal.id_sucursal != exclude_branch_id)
        return await self.session.scalar(statement)

    async def list_active_variant_options(self) -> list[VariantOptionRecord]:
        statement = (
            select(VarianteProducto, Producto.nombre, Talla.codigo, Color.nombre)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .where(VarianteProducto.activo.is_(True), Producto.activo.is_(True))
            .order_by(Producto.nombre, Talla.orden, Color.nombre)
        )
        rows = (await self.session.execute(statement)).all()
        return [VariantOptionRecord(*row) for row in rows]

    @staticmethod
    def _product_core_statement() -> Select[tuple[Producto, str, str, Decimal | None]]:
        return (
            select(
                Producto,
                Categoria.nombre,
                Marca.nombre,
                HistorialPrecio.precio,
            )
            .join(Categoria, Categoria.id_categoria == Producto.id_categoria)
            .join(Marca, Marca.id_marca == Producto.id_marca)
            .outerjoin(
                HistorialPrecio,
                and_(
                    HistorialPrecio.id_producto == Producto.id_producto,
                    HistorialPrecio.fecha_fin.is_(None),
                ),
            )
        )

    async def get_product(self, product_id: int) -> ProductCore | None:
        row = (
            await self.session.execute(
                self._product_core_statement().where(Producto.id_producto == product_id)
            )
        ).one_or_none()
        return ProductCore(*row) if row else None

    async def list_products(
        self,
        *,
        category: str | None,
        target: str | None,
        brand: str | None,
        size: str | None,
        color: str | None,
        season: str | None,
        branch_id: int | None,
        fitting_room: bool | None,
        active: bool | None,
        page: int,
        page_size: int,
        sort: str,
    ) -> tuple[list[ProductCore], int]:
        filters: list[Any] = []
        if category:
            filters.append(func.lower(Categoria.nombre) == category.strip().lower())
        if target:
            filters.append(Producto.publico_objetivo == target)
        if brand:
            filters.append(func.lower(Marca.nombre) == brand.strip().lower())
        if fitting_room is not None:
            filters.append(Producto.permite_vestidor == fitting_room)
        if active is not None:
            filters.append(Producto.activo == active)
        if size:
            filters.append(
                exists(
                    select(1)
                    .select_from(VarianteProducto)
                    .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
                    .where(
                        VarianteProducto.id_producto == Producto.id_producto,
                        VarianteProducto.activo.is_(True),
                        func.lower(Talla.codigo) == size.strip().lower(),
                    )
                )
            )
        if color:
            filters.append(
                exists(
                    select(1)
                    .select_from(VarianteProducto)
                    .join(Color, Color.id_color == VarianteProducto.id_color)
                    .where(
                        VarianteProducto.id_producto == Producto.id_producto,
                        VarianteProducto.activo.is_(True),
                        func.lower(Color.nombre) == color.strip().lower(),
                    )
                )
            )
        if season:
            filters.append(
                exists(
                    select(1)
                    .select_from(ProductoTemporada)
                    .join(Temporada, Temporada.id_temporada == ProductoTemporada.id_temporada)
                    .where(
                        ProductoTemporada.id_producto == Producto.id_producto,
                        func.lower(Temporada.nombre) == season.strip().lower(),
                    )
                )
            )
        if branch_id is not None:
            filters.append(
                exists(
                    select(1)
                    .select_from(VarianteProducto)
                    .join(
                        InventarioSucursal,
                        InventarioSucursal.id_variante == VarianteProducto.id_variante,
                    )
                    .where(
                        VarianteProducto.id_producto == Producto.id_producto,
                        InventarioSucursal.id_sucursal == branch_id,
                    )
                )
            )

        price_sort = func.coalesce(HistorialPrecio.precio, 0)
        sort_map = {
            "nombre": asc(Producto.nombre),
            "-nombre": desc(Producto.nombre),
            "precio": asc(price_sort),
            "-precio": desc(price_sort),
            "created_at": asc(Producto.created_at),
            "-created_at": desc(Producto.created_at),
        }
        statement = self._product_core_statement().where(*filters)
        total_statement = (
            select(func.count(Producto.id_producto))
            .select_from(Producto)
            .join(Categoria, Categoria.id_categoria == Producto.id_categoria)
            .join(Marca, Marca.id_marca == Producto.id_marca)
            .where(*filters)
        )
        total = int(await self.session.scalar(total_statement) or 0)
        rows = (
            await self.session.execute(
                statement.order_by(sort_map[sort], Producto.id_producto)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [ProductCore(*row) for row in rows], total

    async def list_variants(
        self,
        product_id: int,
        branch_id: int | None = None,
        *,
        active_only: bool = False,
    ) -> list[VariantRecord]:
        available = None
        minimum = None
        statement = (
            select(VarianteProducto, Talla.codigo, Color.nombre, Color.codigo_hex)
            .join(Talla, Talla.id_talla == VarianteProducto.id_talla)
            .join(Color, Color.id_color == VarianteProducto.id_color)
            .where(VarianteProducto.id_producto == product_id)
        )
        if branch_id is not None:
            available = InventarioSucursal.stock_fisico - InventarioSucursal.stock_reservado
            minimum = InventarioSucursal.stock_minimo
            statement = statement.add_columns(available, minimum).outerjoin(
                InventarioSucursal,
                and_(
                    InventarioSucursal.id_variante == VarianteProducto.id_variante,
                    InventarioSucursal.id_sucursal == branch_id,
                ),
            )
        if active_only:
            statement = statement.where(VarianteProducto.activo.is_(True))
        rows = (await self.session.execute(statement.order_by(Talla.orden, Color.nombre))).all()
        return [
            VariantRecord(
                variant=row[0],
                size=row[1],
                color=row[2],
                hex_code=row[3],
                available_stock=row[4] if branch_id is not None else available,
                minimum_stock=row[5] if branch_id is not None else minimum,
            )
            for row in rows
        ]

    async def get_variant(self, variant_id: int) -> VarianteProducto | None:
        return await self.get_entity(VarianteProducto, variant_id)

    async def variant_conflict(
        self,
        *,
        product_id: int,
        size_id: int,
        color_id: int,
        sku: str,
        barcode: str | None,
        exclude_variant_id: int | None = None,
    ) -> bool:
        conditions = [
            and_(
                VarianteProducto.id_producto == product_id,
                VarianteProducto.id_talla == size_id,
                VarianteProducto.id_color == color_id,
            ),
            func.lower(VarianteProducto.sku) == sku.strip().lower(),
        ]
        if barcode:
            conditions.append(VarianteProducto.codigo_barras == barcode)
        statement = select(VarianteProducto.id_variante).where(or_(*conditions))
        if exclude_variant_id is not None:
            statement = statement.where(VarianteProducto.id_variante != exclude_variant_id)
        return await self.session.scalar(statement) is not None

    async def list_measurements(self, product_id: int) -> list[MeasurementRecord]:
        rows = (
            await self.session.execute(
                select(MedidaTallaProducto, Talla.codigo)
                .join(Talla, Talla.id_talla == MedidaTallaProducto.id_talla)
                .where(MedidaTallaProducto.id_producto == product_id)
                .order_by(Talla.orden)
            )
        ).all()
        return [MeasurementRecord(*row) for row in rows]

    async def get_measurement(self, product_id: int, size_id: int) -> MedidaTallaProducto | None:
        return await self.session.scalar(
            select(MedidaTallaProducto).where(
                MedidaTallaProducto.id_producto == product_id,
                MedidaTallaProducto.id_talla == size_id,
            )
        )

    async def list_images(self, product_id: int) -> list[ImagenProducto]:
        return list(
            (
                await self.session.scalars(
                    select(ImagenProducto)
                    .where(ImagenProducto.id_producto == product_id)
                    .order_by(ImagenProducto.es_principal.desc(), ImagenProducto.orden)
                )
            ).all()
        )

    async def clear_principal_image(
        self, product_id: int, color_id: int | None, except_id: int | None = None
    ) -> None:
        statement = update(ImagenProducto).where(
            ImagenProducto.id_producto == product_id,
            ImagenProducto.es_principal.is_(True),
        )
        if color_id is None:
            statement = statement.where(ImagenProducto.id_color.is_(None))
        else:
            statement = statement.where(ImagenProducto.id_color == color_id)
        if except_id is not None:
            statement = statement.where(ImagenProducto.id_imagen != except_id)
        await self.session.execute(statement.values(es_principal=False))

    async def product_has_color(self, product_id: int, color_id: int) -> bool:
        return (
            await self.session.scalar(
                select(VarianteProducto.id_variante).where(
                    VarianteProducto.id_producto == product_id,
                    VarianteProducto.id_color == color_id,
                    VarianteProducto.activo.is_(True),
                )
            )
            is not None
        )

    async def get_current_price(self, product_id: int) -> HistorialPrecio | None:
        return await self.session.scalar(
            select(HistorialPrecio).where(
                HistorialPrecio.id_producto == product_id,
                HistorialPrecio.fecha_fin.is_(None),
            )
        )

    async def list_price_history(self, product_id: int) -> list[HistorialPrecio]:
        return list(
            (
                await self.session.scalars(
                    select(HistorialPrecio)
                    .where(HistorialPrecio.id_producto == product_id)
                    .order_by(HistorialPrecio.fecha_inicio.desc())
                )
            ).all()
        )

    async def replace_current_price(
        self,
        *,
        product_id: int,
        price: Decimal,
        actor_id: int,
    ) -> HistorialPrecio:
        current = await self.get_current_price(product_id)
        now = datetime.now(UTC)
        if current is not None:
            current.fecha_fin = now
            await self.session.flush()
        new_price = HistorialPrecio(
            id_producto=product_id,
            precio=price,
            fecha_inicio=now,
            creado_por=actor_id,
        )
        return await self.add(new_price)

    async def list_product_seasons(self, product_id: int) -> list[Temporada]:
        return list(
            (
                await self.session.scalars(
                    select(Temporada)
                    .join(
                        ProductoTemporada, ProductoTemporada.id_temporada == Temporada.id_temporada
                    )
                    .where(ProductoTemporada.id_producto == product_id)
                    .order_by(Temporada.nombre)
                )
            ).all()
        )

    async def get_product_season_link(
        self, product_id: int, season_id: int
    ) -> ProductoTemporada | None:
        return await self.session.scalar(
            select(ProductoTemporada).where(
                ProductoTemporada.id_producto == product_id,
                ProductoTemporada.id_temporada == season_id,
            )
        )

    async def list_product_collections(self, product_id: int) -> list[Coleccion]:
        return list(
            (
                await self.session.scalars(
                    select(Coleccion)
                    .join(
                        ProductoColeccion, ProductoColeccion.id_coleccion == Coleccion.id_coleccion
                    )
                    .where(ProductoColeccion.id_producto == product_id)
                    .order_by(Coleccion.nombre)
                )
            ).all()
        )

    async def get_product_collection_link(
        self, product_id: int, collection_id: int
    ) -> ProductoColeccion | None:
        return await self.session.scalar(
            select(ProductoColeccion).where(
                ProductoColeccion.id_producto == product_id,
                ProductoColeccion.id_coleccion == collection_id,
            )
        )

    async def remove(self, entity: object) -> None:
        await self.session.delete(entity)
        await self.session.flush()
