import math
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit_context import AuditContext, apply_audit_context
from app.modules.auth.models import Ciudad, Sucursal
from app.modules.catalog.exceptions import (
    CatalogConflictError,
    CatalogNotFoundError,
    InvalidCatalogDataError,
)
from app.modules.catalog.models import (
    Categoria,
    Coleccion,
    Color,
    ImagenProducto,
    Marca,
    MedidaTallaProducto,
    Producto,
    ProductoColeccion,
    ProductoTemporada,
    Talla,
    Temporada,
    VarianteProducto,
)
from app.modules.catalog.repository import (
    BranchRecord,
    CatalogRepository,
    MeasurementRecord,
    ProductCore,
    VariantRecord,
)
from app.modules.catalog.schemas import (
    BranchCreate,
    BranchOption,
    BranchResponse,
    BranchUpdate,
    BrandCreate,
    BrandUpdate,
    CategoryCreate,
    CategoryUpdate,
    CityOption,
    CollectionCreate,
    CollectionUpdate,
    ColorCreate,
    ColorUpdate,
    MeasurementResponse,
    MeasurementUpsert,
    PriceCreate,
    PriceResponse,
    ProductCreate,
    ProductImageCreate,
    ProductImageResponse,
    ProductImageUpdate,
    ProductPage,
    ProductResponse,
    ProductUpdate,
    SeasonCreate,
    SeasonUpdate,
    VariantBatchCreate,
    VariantCreate,
    VariantOption,
    VariantResponse,
    VariantUpdate,
)

EntityT = TypeVar("EntityT")


class CatalogService:
    def __init__(self, session: AsyncSession, repository: CatalogRepository) -> None:
        self.session = session
        self.repository = repository

    async def list_branches(self) -> list[BranchOption]:
        branches = await self.repository.list_active_branches()
        return [BranchOption.model_validate(branch, from_attributes=True) for branch in branches]

    async def list_cities(self) -> list[CityOption]:
        cities = await self.repository.list_active_cities()
        return [CityOption.model_validate(city, from_attributes=True) for city in cities]

    async def list_branches_admin(self) -> list[BranchResponse]:
        records = await self.repository.list_branch_records()
        return [self._branch_response(record) for record in records]

    async def get_branch_admin(self, branch_id: int) -> BranchResponse:
        record = await self.repository.get_branch_record(branch_id)
        if record is None:
            raise CatalogNotFoundError("Sucursal no encontrada")
        return self._branch_response(record)

    async def create_branch(
        self,
        payload: BranchCreate,
        audit_context: AuditContext,
        max_active_branches: int | None = None,
    ) -> BranchResponse:
        if payload.activo and max_active_branches is not None:
            active_count = len(await self.repository.list_active_branches())
            if active_count >= max_active_branches:
                raise InvalidCatalogDataError(
                    f"El plan permite hasta {max_active_branches} sucursales activas"
                )
        city = await self._require_active(Ciudad, payload.id_ciudad, "Ciudad")
        if await self.repository.find_branch_by_city_and_name(payload.id_ciudad, payload.nombre):
            raise CatalogConflictError("Ya existe una sucursal con ese nombre en la ciudad")
        branch = Sucursal(**payload.model_dump())
        await self._mutate(audit_context, self.repository.add(branch), result=branch)
        return self._branch_response(BranchRecord(branch=branch, city=city))

    async def update_branch(
        self,
        branch_id: int,
        payload: BranchUpdate,
        audit_context: AuditContext,
        max_active_branches: int | None = None,
    ) -> BranchResponse:
        record = await self.repository.get_branch_record(branch_id)
        if record is None:
            raise CatalogNotFoundError("Sucursal no encontrada")
        values = payload.model_dump(exclude_unset=True)
        if (
            values.get("activo") is True
            and not record.branch.activo
            and max_active_branches is not None
        ):
            active_count = len(await self.repository.list_active_branches())
            if active_count >= max_active_branches:
                raise InvalidCatalogDataError(
                    f"El plan permite hasta {max_active_branches} sucursales activas"
                )
        city_id = values.get("id_ciudad", record.branch.id_ciudad)
        city = record.city
        if city_id != record.branch.id_ciudad:
            city = await self._require_active(Ciudad, city_id, "Ciudad")
        name = values.get("nombre", record.branch.nombre)
        if await self.repository.find_branch_by_city_and_name(
            city_id, name, exclude_branch_id=branch_id
        ):
            raise CatalogConflictError("Ya existe una sucursal con ese nombre en la ciudad")
        opening = values.get("hora_apertura", record.branch.hora_apertura)
        closing = values.get("hora_cierre", record.branch.hora_cierre)
        if bool(opening) != bool(closing):
            raise InvalidCatalogDataError("Debes completar ambas horas o dejar las dos vacías")
        if opening and closing and closing <= opening:
            raise InvalidCatalogDataError(
                "La hora de cierre debe ser posterior a la hora de apertura"
            )
        for key, value in values.items():
            setattr(record.branch, key, value)
        await self._mutate(audit_context, self.repository.flush(), result=record.branch)
        return self._branch_response(BranchRecord(branch=record.branch, city=city))

    async def list_variant_options(self) -> list[VariantOption]:
        records = await self.repository.list_active_variant_options()
        return [
            VariantOption(
                id_variante=record.variant.id_variante,
                id_producto=record.variant.id_producto,
                producto=record.product_name,
                sku=record.variant.sku,
                talla=record.size,
                color=record.color,
            )
            for record in records
        ]

    async def list_categories(self) -> list[Categoria]:
        return await self.repository.list_entities(Categoria, Categoria.nombre)

    async def get_category(self, category_id: int) -> Categoria:
        return await self._require(Categoria, category_id, "Category")

    async def create_category(
        self, payload: CategoryCreate, audit_context: AuditContext
    ) -> Categoria:
        return await self._create_named(
            Categoria, Categoria.nombre, payload, audit_context, "Category"
        )

    async def update_category(
        self, category_id: int, payload: CategoryUpdate, audit_context: AuditContext
    ) -> Categoria:
        return await self._update_named(
            Categoria,
            Categoria.id_categoria,
            Categoria.nombre,
            category_id,
            payload,
            audit_context,
            "Category",
        )

    async def list_brands(self) -> list[Marca]:
        return await self.repository.list_entities(Marca, Marca.nombre)

    async def get_brand(self, brand_id: int) -> Marca:
        return await self._require(Marca, brand_id, "Brand")

    async def create_brand(self, payload: BrandCreate, audit_context: AuditContext) -> Marca:
        return await self._create_named(Marca, Marca.nombre, payload, audit_context, "Brand")

    async def update_brand(
        self, brand_id: int, payload: BrandUpdate, audit_context: AuditContext
    ) -> Marca:
        return await self._update_named(
            Marca,
            Marca.id_marca,
            Marca.nombre,
            brand_id,
            payload,
            audit_context,
            "Brand",
        )

    async def list_sizes(self) -> list[Talla]:
        return await self.repository.list_entities(Talla, Talla.orden)

    async def list_colors(self) -> list[Color]:
        return await self.repository.list_entities(Color, Color.nombre)

    async def create_color(self, payload: ColorCreate, audit_context: AuditContext) -> Color:
        return await self._create_named(Color, Color.nombre, payload, audit_context, "Color")

    async def update_color(
        self, color_id: int, payload: ColorUpdate, audit_context: AuditContext
    ) -> Color:
        return await self._update_named(
            Color,
            Color.id_color,
            Color.nombre,
            color_id,
            payload,
            audit_context,
            "Color",
        )

    async def list_seasons(self) -> list[Temporada]:
        return await self.repository.list_entities(Temporada, Temporada.nombre)

    async def get_season(self, season_id: int) -> Temporada:
        return await self._require(Temporada, season_id, "Season")

    async def create_season(self, payload: SeasonCreate, audit_context: AuditContext) -> Temporada:
        return await self._create_named(
            Temporada, Temporada.nombre, payload, audit_context, "Season"
        )

    async def update_season(
        self, season_id: int, payload: SeasonUpdate, audit_context: AuditContext
    ) -> Temporada:
        season = await self.get_season(season_id)
        values = payload.model_dump(exclude_unset=True)
        start = values.get("fecha_inicio", season.fecha_inicio)
        end = values.get("fecha_fin", season.fecha_fin)
        if start and end and end < start:
            raise InvalidCatalogDataError("fecha_fin cannot be before fecha_inicio")
        return await self._update_named(
            Temporada,
            Temporada.id_temporada,
            Temporada.nombre,
            season_id,
            payload,
            audit_context,
            "Season",
            entity=season,
        )

    async def list_collections(self) -> list[Coleccion]:
        return await self.repository.list_entities(Coleccion, Coleccion.nombre)

    async def get_collection(self, collection_id: int) -> Coleccion:
        return await self._require(Coleccion, collection_id, "Collection")

    async def create_collection(
        self, payload: CollectionCreate, audit_context: AuditContext
    ) -> Coleccion:
        if payload.id_temporada is not None:
            await self._require_active(Temporada, payload.id_temporada, "Season")
        return await self._create_named(
            Coleccion, Coleccion.nombre, payload, audit_context, "Collection"
        )

    async def update_collection(
        self, collection_id: int, payload: CollectionUpdate, audit_context: AuditContext
    ) -> Coleccion:
        if "id_temporada" in payload.model_fields_set and payload.id_temporada is not None:
            await self._require_active(Temporada, payload.id_temporada, "Season")
        return await self._update_named(
            Coleccion,
            Coleccion.id_coleccion,
            Coleccion.nombre,
            collection_id,
            payload,
            audit_context,
            "Collection",
        )

    async def list_products(self, **filters: Any) -> ProductPage:
        records, total = await self.repository.list_products(**filters)
        product_ids = [record.product.id_producto for record in records]
        discounts: dict[int, tuple[Decimal, int, str]] = {}
        try:
            from app.modules.commerce.repository import CommerceRepository

            commerce_repo = CommerceRepository(self.session)
            discounts = await commerce_repo.get_active_discounts_for_products(product_ids)
        except Exception:
            discounts = {}

        items = [
            await self._product_response(
                record,
                branch_id=filters.get("branch_id"),
                discount=discounts.get(record.product.id_producto),
            )
            for record in records
        ]
        return ProductPage(
            items=items,
            page=filters["page"],
            page_size=filters["page_size"],
            total=total,
            pages=math.ceil(total / filters["page_size"]) if total else 0,
        )

    async def get_product(self, product_id: int, branch_id: int | None = None) -> ProductResponse:
        discount: tuple[Decimal, int, str] | None = None
        try:
            from app.modules.commerce.repository import CommerceRepository

            commerce_repo = CommerceRepository(self.session)
            discounts = await commerce_repo.get_active_discounts_for_products([product_id])
            discount = discounts.get(product_id)
        except Exception:
            discount = None

        return await self._product_response(
            await self._require_product(product_id),
            branch_id=branch_id,
            discount=discount,
        )

    async def create_product(
        self,
        payload: ProductCreate,
        audit_context: AuditContext,
        max_active_products: int | None = None,
    ) -> ProductResponse:
        if max_active_products is not None:
            active_count = await self.repository.count_active_products()
            if active_count >= max_active_products:
                raise InvalidCatalogDataError(
                    f"El plan permite hasta {max_active_products} productos activos"
                )
        category = await self._require_active(Categoria, payload.id_categoria, "Category")
        await self._require_active(Marca, payload.id_marca, "Brand")
        self.validate_catalog_rule(category.nombre, payload.publico_objetivo)
        product = Producto(**payload.model_dump())
        await self._mutate(audit_context, self.repository.add(product))
        return await self.get_product(product.id_producto)

    async def update_product(
        self, product_id: int, payload: ProductUpdate, audit_context: AuditContext
    ) -> ProductResponse:
        record = await self._require_product(product_id)
        product = record.product
        category_id = payload.id_categoria or product.id_categoria
        brand_id = payload.id_marca or product.id_marca
        category = await self._require_active(Categoria, category_id, "Category")
        await self._require_active(Marca, brand_id, "Brand")
        target = payload.publico_objetivo or product.publico_objetivo
        self.validate_catalog_rule(category.nombre, target)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(product, key, value)
        await self._mutate(audit_context, self.repository.flush())
        return await self.get_product(product_id)

    async def list_variants(
        self, product_id: int, branch_id: int | None = None
    ) -> list[VariantResponse]:
        await self._require_product(product_id)
        records = await self.repository.list_variants(product_id, branch_id)
        return [self._variant_response(record) for record in records]

    async def create_variant(
        self, product_id: int, payload: VariantCreate, audit_context: AuditContext
    ) -> VariantResponse:
        product = await self._require_product(product_id)
        if not product.product.activo:
            raise InvalidCatalogDataError("Product is inactive")
        await self._validate_variant_references(payload.id_talla, payload.id_color)
        await self._ensure_variant_unique(
            product_id, payload.id_talla, payload.id_color, payload.sku, payload.codigo_barras
        )
        variant = VarianteProducto(id_producto=product_id, **payload.model_dump())
        await self._mutate(audit_context, self.repository.add(variant))
        return await self._variant_by_id(variant.id_variante)

    async def create_variants_batch(
        self, product_id: int, payload: VariantBatchCreate, audit_context: AuditContext
    ) -> list[VariantResponse]:
        product = await self._require_product(product_id)
        if not product.product.activo:
            raise InvalidCatalogDataError("Product is inactive")
        await self._require_active(Color, payload.id_color, "Color")
        sizes: list[Talla] = []
        sku_base = payload.sku_base.strip().upper().rstrip("-")
        for size_id in payload.id_tallas:
            size = await self._require_active(Talla, size_id, "Size")
            sku = f"{sku_base}-{size.codigo}"
            await self._ensure_variant_unique(product_id, size_id, payload.id_color, sku, None)
            sizes.append(size)
        variants = [
            VarianteProducto(
                id_producto=product_id,
                id_talla=size.id_talla,
                id_color=payload.id_color,
                sku=f"{sku_base}-{size.codigo}",
                codigo_barras=None,
                activo=True,
            )
            for size in sizes
        ]
        try:
            await apply_audit_context(self.session, audit_context)
            self.session.add_all(variants)
            await self.session.flush()
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise CatalogConflictError(
                "One of the selected variants, SKUs or barcodes is already registered"
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
        return [await self._variant_by_id(variant.id_variante) for variant in variants]

    async def update_variant(
        self, variant_id: int, payload: VariantUpdate, audit_context: AuditContext
    ) -> VariantResponse:
        variant = await self.repository.get_variant(variant_id)
        if variant is None:
            raise CatalogNotFoundError("Variant not found")
        product = await self._require_product(variant.id_producto)
        if not product.product.activo:
            raise InvalidCatalogDataError("Product is inactive")
        size_id = variant.id_talla
        color_id = variant.id_color
        sku = payload.sku or variant.sku
        barcode = (
            payload.codigo_barras
            if "codigo_barras" in payload.model_fields_set
            else variant.codigo_barras
        )
        await self._validate_variant_references(size_id, color_id)
        await self._ensure_variant_unique(
            variant.id_producto,
            size_id,
            color_id,
            sku,
            barcode,
            exclude_variant_id=variant_id,
        )
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(variant, key, value)
        await self._mutate(audit_context, self.repository.flush())
        return await self._variant_by_id(variant_id)

    async def list_measurements(self, product_id: int) -> list[MeasurementResponse]:
        await self._require_product(product_id)
        rows = await self.repository.list_measurements(product_id)
        return [self._measurement_response(row) for row in rows]

    async def upsert_measurement(
        self,
        product_id: int,
        size_id: int,
        payload: MeasurementUpsert,
        audit_context: AuditContext,
    ) -> MeasurementResponse:
        await self._require_product(product_id)
        size = await self._require_active(Talla, size_id, "Size")
        measurement = await self.repository.get_measurement(product_id, size_id)
        if measurement is None:
            measurement = MedidaTallaProducto(
                id_producto=product_id, id_talla=size_id, **payload.model_dump()
            )
            await self._mutate(audit_context, self.repository.add(measurement))
        else:
            for key, value in payload.model_dump().items():
                setattr(measurement, key, value)
            await self._mutate(audit_context, self.repository.flush())
        return self._measurement_response(MeasurementRecord(measurement, size.codigo))

    async def get_current_price(self, product_id: int) -> PriceResponse:
        await self._require_product(product_id)
        price = await self.repository.get_current_price(product_id)
        if price is None:
            raise CatalogNotFoundError("Current price not found")
        return PriceResponse.model_validate(price)

    async def list_price_history(self, product_id: int) -> list[PriceResponse]:
        await self._require_product(product_id)
        return [
            PriceResponse.model_validate(item)
            for item in await self.repository.list_price_history(product_id)
        ]

    async def set_price(
        self,
        product_id: int,
        payload: PriceCreate,
        actor_id: int,
        audit_context: AuditContext,
    ) -> PriceResponse:
        await self._require_product(product_id)
        price = await self._mutate(
            audit_context,
            self.repository.replace_current_price(
                product_id=product_id, price=payload.precio, actor_id=actor_id
            ),
        )
        return PriceResponse.model_validate(price)

    async def list_images(self, product_id: int) -> list[ProductImageResponse]:
        await self._require_product(product_id)
        images = await self.repository.list_images(product_id)
        return [self._image_response(image) for image in images]

    async def get_image(self, image_id: int) -> ProductImageResponse:
        image = await self.repository.get_entity(ImagenProducto, image_id)
        if image is None:
            raise CatalogNotFoundError("Product image not found")
        return self._image_response(image)

    async def create_image(
        self, product_id: int, payload: ProductImageCreate, audit_context: AuditContext
    ) -> ProductImageResponse:
        await self._require_product(product_id)
        if payload.id_color is not None:
            await self._require_active(Color, payload.id_color, "Color")
            if not await self.repository.product_has_color(product_id, payload.id_color):
                raise InvalidCatalogDataError(
                    "The selected color does not have an active variant for this product"
                )
        values = payload.model_dump()
        values["secure_url"] = str(payload.secure_url)
        image = ImagenProducto(id_producto=product_id, **values)
        try:
            await apply_audit_context(self.session, audit_context)
            if image.es_principal:
                await self.repository.clear_principal_image(product_id, image.id_color)
            await self.repository.add(image)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise CatalogConflictError("Image public_id is already registered") from exc
        except Exception:
            await self.session.rollback()
            raise
        return self._image_response(image)

    async def update_image(
        self, image_id: int, payload: ProductImageUpdate, audit_context: AuditContext
    ) -> ProductImageResponse:
        image = await self.repository.get_entity(ImagenProducto, image_id)
        if image is None:
            raise CatalogNotFoundError("Product image not found")
        target_color_id = (
            payload.id_color if "id_color" in payload.model_fields_set else image.id_color
        )
        if target_color_id is not None:
            await self._require_active(Color, target_color_id, "Color")
            if not await self.repository.product_has_color(image.id_producto, target_color_id):
                raise InvalidCatalogDataError(
                    "The selected color does not have an active variant for this product"
                )
        try:
            await apply_audit_context(self.session, audit_context)
            if payload.es_principal or (
                image.es_principal and "id_color" in payload.model_fields_set
            ):
                await self.repository.clear_principal_image(
                    image.id_producto, target_color_id, image.id_imagen
                )
            values = payload.model_dump(exclude_unset=True)
            if payload.secure_url is not None:
                values["secure_url"] = str(payload.secure_url)
            for key, value in values.items():
                setattr(image, key, value)
            await self.repository.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return self._image_response(image)

    async def delete_image(self, image_id: int, audit_context: AuditContext) -> str:
        image = await self.repository.get_entity(ImagenProducto, image_id)
        if image is None:
            raise CatalogNotFoundError("Product image not found")
        public_id = image.public_id
        await self._mutate(audit_context, self.repository.remove(image))
        return public_id

    async def list_product_seasons(self, product_id: int) -> list[Temporada]:
        await self._require_product(product_id)
        return await self.repository.list_product_seasons(product_id)

    async def add_product_season(
        self, product_id: int, season_id: int, audit_context: AuditContext
    ) -> Temporada:
        await self._require_product(product_id)
        season = await self._require_active(Temporada, season_id, "Season")
        if await self.repository.get_product_season_link(product_id, season_id):
            raise CatalogConflictError("Product is already assigned to this season")
        await self._mutate(
            audit_context,
            self.repository.add(ProductoTemporada(id_producto=product_id, id_temporada=season_id)),
        )
        return season

    async def remove_product_season(
        self, product_id: int, season_id: int, audit_context: AuditContext
    ) -> None:
        link = await self.repository.get_product_season_link(product_id, season_id)
        if link is None:
            raise CatalogNotFoundError("Product-season relation not found")
        await self._mutate(audit_context, self.repository.remove(link))

    async def list_product_collections(self, product_id: int) -> list[Coleccion]:
        await self._require_product(product_id)
        return await self.repository.list_product_collections(product_id)

    async def add_product_collection(
        self, product_id: int, collection_id: int, audit_context: AuditContext
    ) -> Coleccion:
        await self._require_product(product_id)
        collection = await self._require_active(Coleccion, collection_id, "Collection")
        if await self.repository.get_product_collection_link(product_id, collection_id):
            raise CatalogConflictError("Product is already assigned to this collection")
        await self._mutate(
            audit_context,
            self.repository.add(
                ProductoColeccion(id_producto=product_id, id_coleccion=collection_id)
            ),
        )
        return collection

    async def remove_product_collection(
        self, product_id: int, collection_id: int, audit_context: AuditContext
    ) -> None:
        link = await self.repository.get_product_collection_link(product_id, collection_id)
        if link is None:
            raise CatalogNotFoundError("Product-collection relation not found")
        await self._mutate(audit_context, self.repository.remove(link))

    @staticmethod
    def validate_catalog_rule(category_name: str, target: str) -> None:
        category = category_name.strip().upper()
        if category not in {"POLERA", "CAMISA", "POLO", "BLUSA"}:
            raise InvalidCatalogDataError("Category is not part of the official catalog")
        if category == "BLUSA" and target != "MUJER":
            raise InvalidCatalogDataError("BLUSA products are only valid for MUJER")

    # Alias conservado para llamadas existentes y compatibilidad interna.
    validate_blouse_rule = validate_catalog_rule

    @staticmethod
    def stock_state(available: int, minimum: int) -> str:
        if available == 0:
            return "AGOTADO"
        if available <= minimum:
            return "STOCK_BAJO"
        return "DISPONIBLE"

    async def _create_named(
        self,
        model: type[EntityT],
        name_column: Any,
        payload: Any,
        audit_context: AuditContext,
        label: str,
    ) -> EntityT:
        if await self.repository.find_by_name(model, name_column, payload.nombre):
            raise CatalogConflictError(f"{label} name is already registered")
        entity = model(**payload.model_dump())
        return await self._mutate(audit_context, self.repository.add(entity))

    async def _update_named(
        self,
        model: type[EntityT],
        id_column: Any,
        name_column: Any,
        identity: int,
        payload: Any,
        audit_context: AuditContext,
        label: str,
        *,
        entity: EntityT | None = None,
    ) -> EntityT:
        entity = entity or await self._require(model, identity, label)
        values = payload.model_dump(exclude_unset=True)
        if "nombre" in values and await self.repository.find_by_name(
            model,
            name_column,
            values["nombre"],
            exclude_id_column=id_column,
            exclude_id=identity,
        ):
            raise CatalogConflictError(f"{label} name is already registered")
        for key, value in values.items():
            setattr(entity, key, value)
        return await self._mutate(audit_context, self.repository.flush(), result=entity)

    async def _require(self, model: type[EntityT], identity: int, label: str) -> EntityT:
        entity = await self.repository.get_entity(model, identity)
        if entity is None:
            raise CatalogNotFoundError(f"{label} not found")
        return entity

    async def _require_active(self, model: type[EntityT], identity: int, label: str) -> EntityT:
        entity = await self._require(model, identity, label)
        if not getattr(entity, "activo", False):
            raise InvalidCatalogDataError(f"{label} is inactive")
        return entity

    async def _require_product(self, product_id: int) -> ProductCore:
        product = await self.repository.get_product(product_id)
        if product is None:
            raise CatalogNotFoundError("Product not found")
        return product

    async def _validate_variant_references(self, size_id: int, color_id: int) -> None:
        await self._require_active(Talla, size_id, "Size")
        await self._require_active(Color, color_id, "Color")

    async def _ensure_variant_unique(
        self,
        product_id: int,
        size_id: int,
        color_id: int,
        sku: str,
        barcode: str | None,
        exclude_variant_id: int | None = None,
    ) -> None:
        if await self.repository.variant_conflict(
            product_id=product_id,
            size_id=size_id,
            color_id=color_id,
            sku=sku,
            barcode=barcode,
            exclude_variant_id=exclude_variant_id,
        ):
            raise CatalogConflictError("Variant combination, SKU or barcode is already registered")

    async def _variant_by_id(self, variant_id: int) -> VariantResponse:
        variant = await self.repository.get_variant(variant_id)
        if variant is None:
            raise CatalogNotFoundError("Variant not found")
        size = await self._require(Talla, variant.id_talla, "Size")
        color = await self._require(Color, variant.id_color, "Color")
        return self._variant_response(
            VariantRecord(variant, size.codigo, color.nombre, color.codigo_hex, None, None)
        )

    async def _product_response(
        self,
        record: ProductCore,
        branch_id: int | None,
        discount: tuple[Decimal, int, str] | None = None,
    ) -> ProductResponse:
        variants = [
            self._variant_response(item)
            for item in await self.repository.list_variants(
                record.product.id_producto, branch_id, active_only=True
            )
        ]
        images = await self.repository.list_images(record.product.id_producto)
        principal = next((image for image in images if image.es_principal), None)

        descuento_porcentaje = None
        precio_promocional = None
        id_promocion = None
        promocion_nombre = None

        if discount and record.current_price is not None:
            porcentaje, id_promo, promo_nombre = discount
            descuento_porcentaje = porcentaje
            id_promocion = id_promo
            promocion_nombre = promo_nombre
            factor = Decimal("1.00") - (porcentaje / Decimal("100"))
            precio_promocional = (record.current_price * factor).quantize(Decimal("0.01"))

        return ProductResponse(
            id_producto=record.product.id_producto,
            id_categoria=record.product.id_categoria,
            categoria=record.category,
            id_marca=record.product.id_marca,
            marca=record.brand,
            nombre=record.product.nombre,
            descripcion=record.product.descripcion,
            publico_objetivo=record.product.publico_objetivo,
            permite_vestidor=record.product.permite_vestidor,
            activo=record.product.activo,
            precio_actual=record.current_price,
            descuento_porcentaje=descuento_porcentaje,
            precio_promocional=precio_promocional,
            id_promocion=id_promocion,
            promocion_nombre=promocion_nombre,
            imagen_principal=self._image_response(principal) if principal else None,
            variantes=variants,
            tallas_disponibles=sorted({variant.talla for variant in variants}),
            colores_disponibles=sorted({variant.color for variant in variants}),
            created_at=record.product.created_at,
            updated_at=record.product.updated_at,
        )

    @classmethod
    def _variant_response(cls, record: VariantRecord) -> VariantResponse:
        state = None
        if record.available_stock is not None and record.minimum_stock is not None:
            state = cls.stock_state(record.available_stock, record.minimum_stock)
        return VariantResponse(
            id_variante=record.variant.id_variante,
            id_producto=record.variant.id_producto,
            id_talla=record.variant.id_talla,
            talla=record.size,
            id_color=record.variant.id_color,
            color=record.color,
            codigo_hex=record.hex_code,
            sku=record.variant.sku,
            codigo_barras=record.variant.codigo_barras,
            activo=record.variant.activo,
            stock_disponible=record.available_stock,
            estado_stock=state,
        )

    @staticmethod
    def _measurement_response(record: MeasurementRecord) -> MeasurementResponse:
        item = record.measurement
        return MeasurementResponse(
            id_medida=item.id_medida,
            id_producto=item.id_producto,
            id_talla=item.id_talla,
            talla=record.size,
            ancho_hombros_cm=item.ancho_hombros_cm,
            ancho_pecho_cm=item.ancho_pecho_cm,
            largo_prenda_cm=item.largo_prenda_cm,
            largo_manga_cm=item.largo_manga_cm,
        )

    @staticmethod
    def _image_response(image: ImagenProducto) -> ProductImageResponse:
        return ProductImageResponse(
            id_imagen=image.id_imagen,
            id_producto=image.id_producto,
            id_color=image.id_color,
            proveedor_storage=image.proveedor_storage,
            public_id=image.public_id,
            secure_url=image.secure_url,
            tipo=image.tipo,
            orden=image.orden,
            es_principal=image.es_principal,
            formato=image.formato,
            ancho_px=image.ancho_px,
            alto_px=image.alto_px,
            created_at=image.created_at,
        )

    @staticmethod
    def _branch_response(record: BranchRecord) -> BranchResponse:
        branch = record.branch
        return BranchResponse(
            id_sucursal=branch.id_sucursal,
            id_ciudad=branch.id_ciudad,
            ciudad=record.city.nombre,
            departamento=record.city.departamento,
            pais=record.city.pais,
            nombre=branch.nombre,
            direccion=branch.direccion,
            telefono=branch.telefono,
            latitud=branch.latitud,
            longitud=branch.longitud,
            place_id=branch.place_id,
            hora_apertura=branch.hora_apertura,
            hora_cierre=branch.hora_cierre,
            activo=branch.activo,
            created_at=branch.created_at,
            updated_at=branch.updated_at,
        )

    async def _mutate(
        self,
        audit_context: AuditContext,
        operation: Any,
        *,
        result: EntityT | None = None,
    ) -> Any:
        try:
            await apply_audit_context(self.session, audit_context)
            operation_result = await operation
            await self.session.commit()
            return result if result is not None else operation_result
        except IntegrityError as exc:
            await self.session.rollback()
            raise CatalogConflictError("Catalog data conflicts with an existing record") from exc
        except Exception:
            await self.session.rollback()
            raise
