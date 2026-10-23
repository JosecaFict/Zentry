from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status

from app.integrations.cloudinary import CloudinaryError, CloudinaryStorage
from app.modules.auth.dependencies import (
    CurrentPrincipal,
    build_request_audit_context,
    get_current_principal,
    require_permission,
)
from app.modules.catalog.dependencies import get_catalog_service, get_cloudinary_storage
from app.modules.catalog.exceptions import CatalogStorageError, InvalidCatalogDataError
from app.modules.catalog.schemas import (
    BranchCreate,
    BranchOption,
    BranchResponse,
    BranchUpdate,
    BrandCreate,
    BrandResponse,
    BrandUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    CityOption,
    CollectionCreate,
    CollectionRelationRequest,
    CollectionResponse,
    CollectionUpdate,
    ColorCreate,
    ColorResponse,
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
    SeasonRelationRequest,
    SeasonResponse,
    SeasonUpdate,
    SizeResponse,
    VariantBatchCreate,
    VariantCreate,
    VariantOption,
    VariantResponse,
    VariantUpdate,
)
from app.modules.catalog.service import CatalogService

router = APIRouter(tags=["catalog"])


def audit_context_for(request: Request, principal: CurrentPrincipal):
    return build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
        tenant_id=principal.id_tenant,
    )


@router.get("/branches", response_model=list[BranchOption])  # [CU-03] Listar sucursales públicas
async def list_branches(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.list_branches()


@router.get("/cities", response_model=list[CityOption])  # [CU-03] Listar ciudades públicas
async def list_cities(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.list_cities()


@router.get(
    "/branches/admin", response_model=list[BranchResponse]
)  # [CU-03] Listar sucursales admin
async def list_branches_admin(
    _: Annotated[CurrentPrincipal, Depends(require_permission("sucursales.ver"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.list_branches_admin()


@router.get(
    "/branches/{branch_id}", response_model=BranchResponse
)  # [CU-03] Ver detalle sucursal admin
async def get_branch_admin(
    branch_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("sucursales.ver"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.get_branch_admin(branch_id)


@router.post(
    "/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED
)  # [CU-03] Crear sucursal
async def create_branch(
    payload: BranchCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("sucursales.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_branch(
        payload,
        audit_context_for(request, principal),
        max_active_branches=principal.max_sucursales_activas,
    )


@router.patch("/branches/{branch_id}", response_model=BranchResponse)  # [CU-03] Editar sucursal
async def update_branch(
    branch_id: int,
    payload: BranchUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("sucursales.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_branch(
        branch_id,
        payload,
        audit_context_for(request, principal),
        max_active_branches=principal.max_sucursales_activas,
    )


@router.get(
    "/variants", response_model=list[VariantOption]
)  # [CU-05] Listar variantes para filtros
async def list_variant_options(
    _: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.list_variant_options()


@router.get("/categories", response_model=list[CategoryResponse])  # [CU-04] Listar categorías
async def list_categories(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.list_categories()


@router.get("/categories/{category_id}", response_model=CategoryResponse)  # [CU-04] Ver categoría
async def get_category(
    category_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.get_category(category_id)


@router.post(
    "/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)  # [CU-05] Crear categoría
async def create_category(
    payload: CategoryCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_category(payload, audit_context_for(request, principal))


@router.patch(
    "/categories/{category_id}", response_model=CategoryResponse
)  # [CU-05] Editar categoría
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_category(
        category_id, payload, audit_context_for(request, principal)
    )


@router.get("/brands", response_model=list[BrandResponse])  # [CU-04] Listar marcas
async def list_brands(service: Annotated[CatalogService, Depends(get_catalog_service)]):
    return await service.list_brands()


@router.get("/brands/{brand_id}", response_model=BrandResponse)  # [CU-04] Ver marca
async def get_brand(
    brand_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.get_brand(brand_id)


@router.post(
    "/brands", response_model=BrandResponse, status_code=status.HTTP_201_CREATED
)  # [CU-05] Crear marca
async def create_brand(
    payload: BrandCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_brand(payload, audit_context_for(request, principal))


@router.patch("/brands/{brand_id}", response_model=BrandResponse)  # [CU-05] Editar marca
async def update_brand(
    brand_id: int,
    payload: BrandUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_brand(brand_id, payload, audit_context_for(request, principal))


@router.get("/sizes", response_model=list[SizeResponse])  # [CU-04] Listar tallas
async def list_sizes(service: Annotated[CatalogService, Depends(get_catalog_service)]):
    return await service.list_sizes()


@router.get("/colors", response_model=list[ColorResponse])  # [CU-04] Listar colores
async def list_colors(service: Annotated[CatalogService, Depends(get_catalog_service)]):
    return await service.list_colors()


@router.post(
    "/colors", response_model=ColorResponse, status_code=status.HTTP_201_CREATED
)  # [CU-05] Crear color
async def create_color(
    payload: ColorCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_color(payload, audit_context_for(request, principal))


@router.patch("/colors/{color_id}", response_model=ColorResponse)  # [CU-05] Editar color
async def update_color(
    color_id: int,
    payload: ColorUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_color(color_id, payload, audit_context_for(request, principal))


@router.get("/seasons", response_model=list[SeasonResponse])  # [CU-04] Listar temporadas
async def list_seasons(service: Annotated[CatalogService, Depends(get_catalog_service)]):
    return await service.list_seasons()


@router.get("/seasons/{season_id}", response_model=SeasonResponse)  # [CU-04] Ver temporada
async def get_season(
    season_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.get_season(season_id)


@router.post(
    "/seasons", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED
)  # [CU-05] Crear temporada
async def create_season(
    payload: SeasonCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_season(payload, audit_context_for(request, principal))


@router.patch("/seasons/{season_id}", response_model=SeasonResponse)  # [CU-05] Editar temporada
async def update_season(
    season_id: int,
    payload: SeasonUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_season(season_id, payload, audit_context_for(request, principal))


@router.get("/collections", response_model=list[CollectionResponse])  # [CU-04] Listar colecciones
async def list_collections(service: Annotated[CatalogService, Depends(get_catalog_service)]):
    return await service.list_collections()


@router.get(
    "/collections/{collection_id}", response_model=CollectionResponse
)  # [CU-04] Ver colección
async def get_collection(
    collection_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.get_collection(collection_id)


@router.post(
    "/collections", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED
)  # [CU-05] Crear colección
async def create_collection(
    payload: CollectionCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_collection(payload, audit_context_for(request, principal))


@router.patch(
    "/collections/{collection_id}", response_model=CollectionResponse
)  # [CU-05] Editar colección
async def update_collection(
    collection_id: int,
    payload: CollectionUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_collection(
        collection_id, payload, audit_context_for(request, principal)
    )


@router.get("/products", response_model=ProductPage)  # [CU-04] Consultar catálogo de prendas
async def list_products(
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    categoria: str | None = None,
    publico_objetivo: Literal["HOMBRE", "MUJER"] | None = None,
    marca: str | None = None,
    talla: str | None = None,
    color: str | None = None,
    temporada: str | None = None,
    sucursal: int | None = Query(default=None, gt=0),
    permite_vestidor: bool | None = None,
    activo: bool | None = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: Literal["nombre", "-nombre", "precio", "-precio", "created_at", "-created_at"] = "nombre",
):
    return await service.list_products(
        category=categoria,
        target=publico_objetivo,
        brand=marca,
        size=talla,
        color=color,
        season=temporada,
        branch_id=sucursal,
        fitting_room=permite_vestidor,
        active=activo,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get(
    "/products/{product_id}", response_model=ProductResponse
)  # [CU-04] Ver detalle de prenda y variantes
async def get_product(
    product_id: int,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    sucursal: int | None = Query(default=None, gt=0),
):
    return await service.get_product(product_id, sucursal)


@router.post(
    "/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED
)  # [CU-05] Crear prenda/producto
async def create_product(
    payload: ProductCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_product(
        payload,
        audit_context_for(request, principal),
        max_active_products=principal.max_productos_activos,
    )


@router.patch(
    "/products/{product_id}", response_model=ProductResponse
)  # [CU-05] Actualizar prenda/producto
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_product(product_id, payload, audit_context_for(request, principal))


@router.get(
    "/products/{product_id}/variants", response_model=list[VariantResponse]
)  # [CU-04] Consultar variantes de prenda
async def list_variants(
    product_id: int,
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    sucursal: int | None = Query(default=None, gt=0),
):
    return await service.list_variants(product_id, sucursal)


@router.post(  # [CU-05] Crear variante de prenda (SKU)
    "/products/{product_id}/variants",
    response_model=VariantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_variant(
    product_id: int,
    payload: VariantCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_variant(product_id, payload, audit_context_for(request, principal))


@router.post(  # [CU-05] Crear variantes en lote (matriz)
    "/products/{product_id}/variants/batch",
    response_model=list[VariantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_variants_batch(
    product_id: int,
    payload: VariantBatchCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.crear"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_variants_batch(
        product_id, payload, audit_context_for(request, principal)
    )


@router.patch(
    "/variants/{variant_id}", response_model=VariantResponse
)  # [CU-05] Actualizar variante/código de barras
async def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_variant(variant_id, payload, audit_context_for(request, principal))


@router.get(
    "/products/{product_id}/measurements", response_model=list[MeasurementResponse]
)  # [CU-18] Medidas de patronaje AR
async def list_measurements(
    product_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.list_measurements(product_id)


@router.put(
    "/products/{product_id}/measurements/{size_id}", response_model=MeasurementResponse
)  # [CU-18] Guardar medidas de prenda AR
async def upsert_measurement(
    product_id: int,
    size_id: int,
    payload: MeasurementUpsert,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.upsert_measurement(
        product_id, size_id, payload, audit_context_for(request, principal)
    )


@router.get(
    "/products/{product_id}/price", response_model=PriceResponse
)  # [CU-05] Consultar precio vigente
async def get_current_price(
    product_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.get_current_price(product_id)


@router.post(  # [CU-05] Asignar nuevo precio
    "/products/{product_id}/price",
    response_model=PriceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def set_price(
    product_id: int,
    payload: PriceCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.set_price(
        product_id,
        payload,
        principal.user.id_usuario,
        audit_context_for(request, principal),
    )


@router.get(
    "/products/{product_id}/price-history", response_model=list[PriceResponse]
)  # [CU-05] Historial de precios
async def list_price_history(
    product_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.list_price_history(product_id)


@router.get(
    "/products/{product_id}/images", response_model=list[ProductImageResponse]
)  # [CU-04] Consultar imágenes de prenda
async def list_images(
    product_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.list_images(product_id)


@router.post(  # [CU-05] Registrar metadata de imagen
    "/products/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_image(
    product_id: int,
    payload: ProductImageCreate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.create_image(product_id, payload, audit_context_for(request, principal))


MAX_PRODUCT_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_PRODUCT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post(  # [CU-05 / CU-18] Subir imagen a Cloudinary (catálogo / asset AR)
    "/products/{product_id}/images/upload",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_image(
    product_id: int,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    storage: Annotated[CloudinaryStorage, Depends(get_cloudinary_storage)],
    file: Annotated[UploadFile, File()],
    tipo: Annotated[Literal["CATALOGO", "MINIATURA", "PROMOCIONAL"], Form()] = "CATALOGO",
    id_color: Annotated[int | None, Form(gt=0)] = None,
    orden: Annotated[int, Form(gt=0)] = 1,
    es_principal: Annotated[bool, Form()] = False,
):
    if file.content_type not in ALLOWED_PRODUCT_IMAGE_TYPES:
        raise InvalidCatalogDataError("Usa una imagen JPG, PNG o WebP")
    content = await file.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    await file.close()
    if not content:
        raise InvalidCatalogDataError("El archivo de imagen está vacío")
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        raise InvalidCatalogDataError("La imagen no debe superar 5 MB")
    try:
        uploaded = await storage.upload_product_image(
            product_id=product_id,
            content=content,
            filename=file.filename or "producto",
            content_type=file.content_type,
        )
    except CloudinaryError as exc:
        raise CatalogStorageError(str(exc)) from exc
    payload = ProductImageCreate(
        id_color=id_color,
        public_id=uploaded.public_id,
        secure_url=uploaded.secure_url,
        tipo=tipo,
        orden=orden,
        es_principal=es_principal,
        formato=uploaded.formato,
        ancho_px=uploaded.ancho_px,
        alto_px=uploaded.alto_px,
    )
    try:
        return await service.create_image(
            product_id, payload, audit_context_for(request, principal)
        )
    except Exception:
        await storage.destroy(uploaded.public_id)
        raise


@router.put(
    "/product-images/{image_id}/replace", response_model=ProductImageResponse
)  # [CU-05] Reemplazar imagen en Cloudinary
async def replace_image(
    image_id: int,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    storage: Annotated[CloudinaryStorage, Depends(get_cloudinary_storage)],
    file: Annotated[UploadFile, File()],
):
    if file.content_type not in ALLOWED_PRODUCT_IMAGE_TYPES:
        raise InvalidCatalogDataError("Usa una imagen JPG, PNG o WebP")
    content = await file.read(MAX_PRODUCT_IMAGE_BYTES + 1)
    await file.close()
    if not content:
        raise InvalidCatalogDataError("El archivo de imagen está vacío")
    if len(content) > MAX_PRODUCT_IMAGE_BYTES:
        raise InvalidCatalogDataError("La imagen no debe superar 5 MB")
    current = await service.get_image(image_id)
    try:
        uploaded = await storage.upload_product_image(
            product_id=current.id_producto,
            content=content,
            filename=file.filename or "producto",
            content_type=file.content_type,
        )
    except CloudinaryError as exc:
        raise CatalogStorageError(str(exc)) from exc
    try:
        replaced = await service.update_image(
            image_id,
            ProductImageUpdate(
                public_id=uploaded.public_id,
                secure_url=uploaded.secure_url,
                formato=uploaded.formato,
                ancho_px=uploaded.ancho_px,
                alto_px=uploaded.alto_px,
            ),
            audit_context_for(request, principal),
        )
    except Exception:
        await storage.destroy(uploaded.public_id)
        raise
    await storage.destroy(current.public_id)
    return replaced


@router.delete(
    "/product-images/{image_id}", status_code=status.HTTP_204_NO_CONTENT
)  # [CU-05] Eliminar imagen
async def delete_image(
    image_id: int,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
    storage: Annotated[CloudinaryStorage, Depends(get_cloudinary_storage)],
):
    public_id = await service.delete_image(image_id, audit_context_for(request, principal))
    await storage.destroy(public_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/product-images/{image_id}", response_model=ProductImageResponse
)  # [CU-05] Actualizar imagen/orden/principal
async def update_image(
    image_id: int,
    payload: ProductImageUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.update_image(image_id, payload, audit_context_for(request, principal))


@router.get(
    "/products/{product_id}/seasons", response_model=list[SeasonResponse]
)  # [CU-05] Ver temporadas del producto
async def list_product_seasons(
    product_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.list_product_seasons(product_id)


@router.post(
    "/products/{product_id}/seasons", response_model=SeasonResponse
)  # [CU-05] Asociar temporada
async def add_product_season(
    product_id: int,
    payload: SeasonRelationRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.add_product_season(
        product_id, payload.id_temporada, audit_context_for(request, principal)
    )


@router.delete(
    "/products/{product_id}/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT
)  # [CU-05] Desasociar temporada
async def remove_product_season(
    product_id: int,
    season_id: int,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    await service.remove_product_season(
        product_id, season_id, audit_context_for(request, principal)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/products/{product_id}/collections", response_model=list[CollectionResponse]
)  # [CU-05] Ver colecciones del producto
async def list_product_collections(
    product_id: int, service: Annotated[CatalogService, Depends(get_catalog_service)]
):
    return await service.list_product_collections(product_id)


@router.post(
    "/products/{product_id}/collections", response_model=CollectionResponse
)  # [CU-05] Asociar colección
async def add_product_collection(
    product_id: int,
    payload: CollectionRelationRequest,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    return await service.add_product_collection(
        product_id, payload.id_coleccion, audit_context_for(request, principal)
    )


@router.delete(  # [CU-05] Desasociar colección
    "/products/{product_id}/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_product_collection(
    product_id: int,
    collection_id: int,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("productos.editar"))],
    service: Annotated[CatalogService, Depends(get_catalog_service)],
):
    await service.remove_product_collection(
        product_id, collection_id, audit_context_for(request, principal)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
