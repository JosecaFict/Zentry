from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.db.audit_context import AuditContext
from app.integrations.cloudinary import CloudinaryUpload
from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.catalog.dependencies import get_catalog_service, get_cloudinary_storage
from app.modules.catalog.exceptions import (
    CatalogConflictError,
    CatalogNotFoundError,
    InvalidCatalogDataError,
)
from app.modules.catalog.models import Color, HistorialPrecio, ImagenProducto, Producto
from app.modules.catalog.schemas import BranchCreate, PriceCreate, ProductImageCreate
from app.modules.catalog.service import CatalogService

NOW = "2026-08-30T21:00:00Z"
CATEGORY = {
    "id_categoria": 1,
    "nombre": "POLERA",
    "descripcion": "Prenda superior",
    "activo": True,
    "created_at": NOW,
    "updated_at": NOW,
}
BRAND = {
    "id_marca": 1,
    "nombre": "Capricho",
    "descripcion": None,
    "pais_origen": "Bolivia",
    "activo": True,
    "created_at": NOW,
    "updated_at": NOW,
}
SEASON = {
    "id_temporada": 1,
    "nombre": "Verano",
    "anio": 2026,
    "fecha_inicio": "2026-01-01",
    "fecha_fin": "2026-03-31",
    "activo": True,
    "created_at": NOW,
    "updated_at": NOW,
}
COLLECTION = {
    "id_coleccion": 1,
    "id_temporada": 1,
    "nombre": "Verano 2026",
    "descripcion": None,
    "activo": True,
    "created_at": NOW,
    "updated_at": NOW,
}
VARIANT = {
    "id_variante": 1,
    "id_producto": 1,
    "id_talla": 1,
    "talla": "S",
    "id_color": 1,
    "color": "Negro",
    "codigo_hex": "#000000",
    "sku": "POL-NEG-S",
    "codigo_barras": "10001",
    "activo": True,
    "stock_disponible": None,
    "estado_stock": None,
}
PRODUCT = {
    "id_producto": 1,
    "id_categoria": 1,
    "categoria": "POLERA",
    "id_marca": 1,
    "marca": "Capricho",
    "nombre": "Polera negra",
    "descripcion": None,
    "publico_objetivo": "HOMBRE",
    "permite_vestidor": True,
    "activo": True,
    "precio_actual": "99.90",
    "imagen_principal": None,
    "variantes": [VARIANT],
    "tallas_disponibles": ["S"],
    "colores_disponibles": ["Negro"],
    "created_at": NOW,
    "updated_at": NOW,
}
PRICE = {
    "id_historial_precio": 2,
    "id_producto": 1,
    "precio": "109.90",
    "fecha_inicio": NOW,
    "fecha_fin": None,
    "creado_por": 99,
}
IMAGE = {
    "id_imagen": 1,
    "id_producto": 1,
    "proveedor_storage": "CLOUDINARY",
    "public_id": "catalog/polera-negra",
    "secure_url": "https://example.com/image.jpg",
    "tipo": "CATALOGO",
    "orden": 1,
    "es_principal": True,
    "formato": "jpg",
    "ancho_px": 800,
    "alto_px": 1000,
    "created_at": NOW,
}
BRANCH = {
    "id_sucursal": 1,
    "id_ciudad": 1,
    "ciudad": "Santa Cruz de la Sierra",
    "departamento": "Santa Cruz",
    "pais": "Bolivia",
    "nombre": "Capricho Store Central",
    "direccion": "Av. Principal 123",
    "telefono": "70000000",
    "latitud": None,
    "longitud": None,
    "place_id": None,
    "hora_apertura": "09:00:00",
    "hora_cierre": "20:00:00",
    "activo": True,
    "created_at": NOW,
    "updated_at": NOW,
}


def make_principal(*permissions: str) -> CurrentPrincipal:
    user = Usuario(
        id_usuario=99,
        nombres="Admin",
        apellidos="Catalog",
        correo="admin@example.com",
        ci="ADMIN-99",
        password_hash="not-returned",
        estado="ACTIVO",
        created_at=datetime(2026, 8, 30, tzinfo=UTC),
        updated_at=datetime(2026, 8, 30, tzinfo=UTC),
    )
    return CurrentPrincipal(
        user=user,
        roles=frozenset({"ADMIN"}),
        permissions=frozenset(permissions),
        session_id="catalog-test-session",
    )


async def call_catalog(
    method: str,
    path: str,
    *,
    service: AsyncMock,
    principal: CurrentPrincipal | None = None,
    json: dict | None = None,
    storage: AsyncMock | None = None,
    data: dict | None = None,
    files: dict | None = None,
) -> Response:
    async def override_service() -> AsyncIterator[AsyncMock]:
        yield service

    app.dependency_overrides[get_catalog_service] = override_service
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    if storage is not None:
        app.dependency_overrides[get_cloudinary_storage] = lambda: storage
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, json=json, data=data, files=files)
    finally:
        app.dependency_overrides.clear()


async def test_list_categories() -> None:
    service = AsyncMock()
    service.list_categories.return_value = [CATEGORY]
    response = await call_catalog("GET", "/api/v1/categories", service=service)
    assert response.status_code == 200
    assert response.json()[0]["nombre"] == "POLERA"


async def test_list_branches_is_public() -> None:
    service = AsyncMock()
    service.list_branches.return_value = [
        {"id_sucursal": 1, "nombre": "Central", "direccion": "Av. Principal 123"}
    ]
    response = await call_catalog("GET", "/api/v1/branches", service=service)
    assert response.status_code == 200
    assert response.json()[0]["nombre"] == "Central"


async def test_list_branches_admin_requires_permission() -> None:
    service = AsyncMock()
    service.list_branches_admin.return_value = [BRANCH]
    response = await call_catalog(
        "GET",
        "/api/v1/branches/admin",
        service=service,
        principal=make_principal("sucursales.ver"),
    )
    assert response.status_code == 200
    assert response.json()[0]["ciudad"] == "Santa Cruz de la Sierra"


async def test_list_branches_admin_rejects_missing_permission() -> None:
    response = await call_catalog(
        "GET",
        "/api/v1/branches/admin",
        service=AsyncMock(),
        principal=make_principal(),
    )
    assert response.status_code == 403


async def test_create_branch_with_permission() -> None:
    service = AsyncMock()
    service.create_branch.return_value = BRANCH
    response = await call_catalog(
        "POST",
        "/api/v1/branches",
        service=service,
        principal=make_principal("sucursales.crear"),
        json={
            "id_ciudad": 1,
            "nombre": "Capricho Store Central",
            "direccion": "Av. Principal 123",
            "telefono": "",
            "hora_apertura": "09:00",
            "hora_cierre": "20:00",
        },
    )
    assert response.status_code == 201
    payload = service.create_branch.await_args.args[0]
    assert payload.telefono is None


async def test_create_branch_rejects_invalid_schedule() -> None:
    response = await call_catalog(
        "POST",
        "/api/v1/branches",
        service=AsyncMock(),
        principal=make_principal("sucursales.crear"),
        json={
            "id_ciudad": 1,
            "nombre": "Capricho Store Norte",
            "direccion": "Av. Norte 20",
            "hora_apertura": "20:00",
            "hora_cierre": "09:00",
        },
    )
    assert response.status_code == 422


async def test_basic_plan_rejects_third_active_branch() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    repository.list_active_branches.return_value = [SimpleNamespace(), SimpleNamespace()]
    service = CatalogService(session, repository)

    with pytest.raises(InvalidCatalogDataError, match="2 sucursales activas"):
        await service.create_branch(
            BranchCreate(
                id_ciudad=1,
                nombre="Sucursal Norte",
                direccion="Av. Norte 20",
            ),
            AuditContext(tenant_id=1, usuario_id=99),
            max_active_branches=2,
        )

    repository.add.assert_not_called()


async def test_create_category() -> None:
    service = AsyncMock()
    service.create_category.return_value = CATEGORY
    response = await call_catalog(
        "POST",
        "/api/v1/categories",
        service=service,
        principal=make_principal("productos.crear"),
        json={"nombre": "POLERA", "descripcion": "Prenda superior"},
    )
    assert response.status_code == 201


async def test_normalize_official_category_name() -> None:
    service = AsyncMock()
    service.create_category.return_value = CATEGORY
    response = await call_catalog(
        "POST",
        "/api/v1/categories",
        service=service,
        principal=make_principal("productos.crear"),
        json={"nombre": " polera ", "descripcion": "Prenda superior"},
    )
    assert response.status_code == 201
    assert service.create_category.await_args.args[0].nombre == "POLERA"


async def test_reject_category_outside_official_catalog() -> None:
    service = AsyncMock()
    response = await call_catalog(
        "POST",
        "/api/v1/categories",
        service=service,
        principal=make_principal("productos.crear"),
        json={"nombre": "PANTALON"},
    )
    assert response.status_code == 422
    service.create_category.assert_not_awaited()


async def test_update_category() -> None:
    service = AsyncMock()
    service.update_category.return_value = {**CATEGORY, "activo": False}
    response = await call_catalog(
        "PATCH",
        "/api/v1/categories/1",
        service=service,
        principal=make_principal("productos.editar"),
        json={"activo": False},
    )
    assert response.status_code == 200
    assert response.json()["activo"] is False


async def test_create_brand() -> None:
    service = AsyncMock()
    service.create_brand.return_value = BRAND
    response = await call_catalog(
        "POST",
        "/api/v1/brands",
        service=service,
        principal=make_principal("productos.crear"),
        json={"nombre": "Capricho", "pais_origen": "Bolivia"},
    )
    assert response.status_code == 201


async def test_create_valid_color() -> None:
    service = AsyncMock()
    service.create_color.return_value = {
        "id_color": 1,
        "nombre": "Negro",
        "codigo_hex": "#000000",
        "activo": True,
    }
    response = await call_catalog(
        "POST",
        "/api/v1/colors",
        service=service,
        principal=make_principal("productos.crear"),
        json={"nombre": "Negro", "codigo_hex": "#000000"},
    )
    assert response.status_code == 201


async def test_reject_invalid_color_hex() -> None:
    response = await call_catalog(
        "POST",
        "/api/v1/colors",
        service=AsyncMock(),
        principal=make_principal("productos.crear"),
        json={"nombre": "Negro", "codigo_hex": "000"},
    )
    assert response.status_code == 422


async def test_list_seasons() -> None:
    service = AsyncMock()
    service.list_seasons.return_value = [SEASON]
    response = await call_catalog("GET", "/api/v1/seasons", service=service)
    assert response.status_code == 200


async def test_create_collection() -> None:
    service = AsyncMock()
    service.create_collection.return_value = COLLECTION
    response = await call_catalog(
        "POST",
        "/api/v1/collections",
        service=service,
        principal=make_principal("productos.crear"),
        json={"id_temporada": 1, "nombre": "Verano 2026"},
    )
    assert response.status_code == 201


async def test_list_products_without_filters() -> None:
    service = AsyncMock()
    service.list_products.return_value = {
        "items": [PRODUCT],
        "page": 1,
        "page_size": 20,
        "total": 1,
        "pages": 1,
    }
    response = await call_catalog("GET", "/api/v1/products", service=service)
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.parametrize(
    "query,expected",
    [
        ("categoria=POLERA", {"category": "POLERA"}),
        ("publico_objetivo=MUJER", {"target": "MUJER"}),
        ("talla=M&color=Negro", {"size": "M", "color": "Negro"}),
        ("sucursal=2", {"branch_id": 2}),
    ],
)
async def test_product_catalog_filters(query: str, expected: dict) -> None:
    service = AsyncMock()
    service.list_products.return_value = {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
        "pages": 0,
    }
    response = await call_catalog("GET", f"/api/v1/products?{query}", service=service)
    assert response.status_code == 200
    kwargs = service.list_products.await_args.kwargs
    assert all(kwargs[key] == value for key, value in expected.items())


async def test_product_detail() -> None:
    service = AsyncMock()
    service.get_product.return_value = PRODUCT
    response = await call_catalog("GET", "/api/v1/products/1", service=service)
    assert response.status_code == 200
    assert response.json()["variantes"][0]["sku"] == "POL-NEG-S"


async def test_create_product_with_permission() -> None:
    service = AsyncMock()
    service.create_product.return_value = PRODUCT
    response = await call_catalog(
        "POST",
        "/api/v1/products",
        service=service,
        principal=make_principal("productos.crear"),
        json={
            "id_categoria": 1,
            "id_marca": 1,
            "nombre": "Polera negra",
            "publico_objetivo": "HOMBRE",
        },
    )
    assert response.status_code == 201


async def test_create_product_without_permission() -> None:
    response = await call_catalog(
        "POST",
        "/api/v1/products",
        service=AsyncMock(),
        principal=make_principal(),
        json={
            "id_categoria": 1,
            "id_marca": 1,
            "nombre": "Polera negra",
            "publico_objetivo": "HOMBRE",
        },
    )
    assert response.status_code == 403


def test_reject_blouse_for_man() -> None:
    with pytest.raises(Exception, match="only valid for MUJER"):
        CatalogService.validate_blouse_rule("BLUSA", "HOMBRE")


def test_reject_product_category_outside_official_catalog() -> None:
    with pytest.raises(Exception, match="official catalog"):
        CatalogService.validate_catalog_rule("PANTALON", "HOMBRE")


async def test_reject_unisex_target() -> None:
    response = await call_catalog(
        "POST",
        "/api/v1/products",
        service=AsyncMock(),
        principal=make_principal("productos.crear"),
        json={
            "id_categoria": 1,
            "id_marca": 1,
            "nombre": "Polera",
            "publico_objetivo": "UNISEX",
        },
    )
    assert response.status_code == 422


async def test_create_valid_variant() -> None:
    service = AsyncMock()
    service.create_variant.return_value = VARIANT
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/variants",
        service=service,
        principal=make_principal("productos.crear"),
        json={"id_talla": 1, "id_color": 1, "sku": "POL-NEG-S", "codigo_barras": ""},
    )
    assert response.status_code == 201
    assert service.create_variant.await_args.args[1].codigo_barras is None


async def test_create_variant_matrix_in_one_request() -> None:
    service = AsyncMock()
    service.create_variants_batch.return_value = [VARIANT]
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/variants/batch",
        service=service,
        principal=make_principal("productos.crear"),
        json={"id_color": 1, "id_tallas": [1, 2, 3, 4], "sku_base": "RL-POLO-AZM"},
    )
    assert response.status_code == 201
    payload = service.create_variants_batch.await_args.args[1]
    assert payload.id_tallas == [1, 2, 3, 4]
    assert payload.sku_base == "RL-POLO-AZM"


async def test_reject_duplicate_variant() -> None:
    service = AsyncMock()
    service.create_variant.side_effect = CatalogConflictError("Variant already registered")
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/variants",
        service=service,
        principal=make_principal("productos.crear"),
        json={"id_talla": 1, "id_color": 1, "sku": "POL-NEG-S"},
    )
    assert response.status_code == 409


async def test_update_variant() -> None:
    service = AsyncMock()
    service.update_variant.return_value = {**VARIANT, "activo": False}
    response = await call_catalog(
        "PATCH",
        "/api/v1/variants/1",
        service=service,
        principal=make_principal("productos.editar"),
        json={"activo": False},
    )
    assert response.status_code == 200


async def test_reject_moving_existing_variant_to_another_size_or_color() -> None:
    response = await call_catalog(
        "PATCH",
        "/api/v1/variants/1",
        service=AsyncMock(),
        principal=make_principal("productos.editar"),
        json={"id_color": 2},
    )
    assert response.status_code == 422


async def test_register_measurements() -> None:
    service = AsyncMock()
    service.upsert_measurement.return_value = {
        "id_medida": 1,
        "id_producto": 1,
        "id_talla": 1,
        "talla": "S",
        "ancho_hombros_cm": "40.00",
        "ancho_pecho_cm": None,
        "largo_prenda_cm": None,
        "largo_manga_cm": None,
    }
    response = await call_catalog(
        "PUT",
        "/api/v1/products/1/measurements/1",
        service=service,
        principal=make_principal("productos.editar"),
        json={"ancho_hombros_cm": 40},
    )
    assert response.status_code == 200


async def test_reject_non_positive_measurement() -> None:
    response = await call_catalog(
        "PUT",
        "/api/v1/products/1/measurements/1",
        service=AsyncMock(),
        principal=make_principal("productos.editar"),
        json={"ancho_hombros_cm": 0},
    )
    assert response.status_code == 422


async def test_associate_product_to_season() -> None:
    service = AsyncMock()
    service.add_product_season.return_value = SEASON
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/seasons",
        service=service,
        principal=make_principal("productos.editar"),
        json={"id_temporada": 1},
    )
    assert response.status_code == 200


async def test_remove_product_season_relation() -> None:
    response = await call_catalog(
        "DELETE",
        "/api/v1/products/1/seasons/1",
        service=AsyncMock(),
        principal=make_principal("productos.editar"),
    )
    assert response.status_code == 204


async def test_associate_product_to_collection() -> None:
    service = AsyncMock()
    service.add_product_collection.return_value = COLLECTION
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/collections",
        service=service,
        principal=make_principal("productos.editar"),
        json={"id_coleccion": 1},
    )
    assert response.status_code == 200


async def test_get_current_price() -> None:
    service = AsyncMock()
    service.get_current_price.return_value = PRICE
    response = await call_catalog("GET", "/api/v1/products/1/price", service=service)
    assert response.status_code == 200
    assert response.json()["precio"] == "109.90"


async def test_change_price_closes_previous_and_creates_new() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    repository.get_product.return_value = SimpleNamespace(product=Producto(id_producto=1))
    repository.replace_current_price.return_value = HistorialPrecio(
        id_historial_precio=2,
        id_producto=1,
        precio=Decimal("109.90"),
        fecha_inicio=datetime(2026, 8, 30, tzinfo=UTC),
        fecha_fin=None,
        creado_por=99,
    )
    service = CatalogService(session, repository)
    result = await service.set_price(
        1,
        PriceCreate(precio=Decimal("109.90")),
        99,
        AuditContext(usuario_id=99),
    )
    assert result.precio == Decimal("109.90")
    repository.replace_current_price.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_reject_negative_price() -> None:
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/price",
        service=AsyncMock(),
        principal=make_principal("productos.editar"),
        json={"precio": -1},
    )
    assert response.status_code == 422


async def test_create_product_image() -> None:
    service = AsyncMock()
    service.create_image.return_value = IMAGE
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/images",
        service=service,
        principal=make_principal("productos.editar"),
        json={
            "public_id": "catalog/polera-negra",
            "secure_url": "https://example.com/image.jpg",
            "es_principal": True,
        },
    )
    assert response.status_code == 201


async def test_upload_product_image_to_cloudinary() -> None:
    service = AsyncMock()
    storage = AsyncMock()
    service.create_image.return_value = IMAGE
    storage.upload_product_image.return_value = CloudinaryUpload(
        public_id="capricho-store/productos/1/polera-negra",
        secure_url="https://res.cloudinary.com/demo/image/upload/polera-negra.webp",
        formato="webp",
        ancho_px=900,
        alto_px=1200,
    )
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/images/upload",
        service=service,
        storage=storage,
        principal=make_principal("productos.editar"),
        data={
            "tipo": "CATALOGO",
            "id_color": "1",
            "orden": "1",
            "es_principal": "true",
        },
        files={"file": ("polera.webp", b"image-bytes", "image/webp")},
    )
    assert response.status_code == 201
    storage.upload_product_image.assert_awaited_once()
    payload = service.create_image.await_args.args[1]
    assert payload.public_id.endswith("polera-negra")
    assert payload.id_color == 1
    assert payload.es_principal is True


async def test_upload_rejects_unsupported_product_image() -> None:
    response = await call_catalog(
        "POST",
        "/api/v1/products/1/images/upload",
        service=AsyncMock(),
        storage=AsyncMock(),
        principal=make_principal("productos.editar"),
        files={"file": ("producto.gif", b"gif", "image/gif")},
    )
    assert response.status_code == 400


async def test_replace_product_image_in_cloudinary() -> None:
    service = AsyncMock()
    storage = AsyncMock()
    service.get_image.return_value = SimpleNamespace(
        id_producto=1, public_id="catalog/polera-anterior"
    )
    service.update_image.return_value = IMAGE
    storage.upload_product_image.return_value = CloudinaryUpload(
        public_id="capricho-store/productos/1/polera-nueva",
        secure_url="https://res.cloudinary.com/demo/image/upload/polera-nueva.webp",
        formato="webp",
        ancho_px=900,
        alto_px=1200,
    )
    response = await call_catalog(
        "PUT",
        "/api/v1/product-images/1/replace",
        service=service,
        storage=storage,
        principal=make_principal("productos.editar"),
        files={"file": ("polera-nueva.webp", b"new-image", "image/webp")},
    )
    assert response.status_code == 200
    payload = service.update_image.await_args.args[1]
    assert payload.public_id.endswith("polera-nueva")
    storage.destroy.assert_awaited_once_with("catalog/polera-anterior")


async def test_delete_product_image_from_catalog_and_cloudinary() -> None:
    service = AsyncMock()
    storage = AsyncMock()
    service.delete_image.return_value = "catalog/polera-blanca"
    response = await call_catalog(
        "DELETE",
        "/api/v1/product-images/4",
        service=service,
        storage=storage,
        principal=make_principal("productos.editar"),
    )
    assert response.status_code == 204
    service.delete_image.assert_awaited_once()
    storage.destroy.assert_awaited_once_with("catalog/polera-blanca")


async def test_only_one_principal_image_is_kept() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    repository.get_product.return_value = SimpleNamespace(product=Producto(id_producto=1))

    async def persist_image(item: ImagenProducto) -> ImagenProducto:
        item.id_imagen = 1
        item.created_at = datetime(2026, 8, 30, tzinfo=UTC)
        return item

    repository.add.side_effect = persist_image
    service = CatalogService(session, repository)
    payload = ProductImageCreate(
        public_id="catalog/polera",
        secure_url="https://example.com/image.jpg",
        es_principal=True,
    )
    result = await service.create_image(1, payload, AuditContext(usuario_id=99))
    assert isinstance(result, object)
    repository.clear_principal_image.assert_awaited_once_with(1, None)


async def test_principal_image_is_scoped_to_product_color() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    repository.get_product.return_value = SimpleNamespace(product=Producto(id_producto=1))
    repository.get_entity.return_value = Color(
        id_color=2, nombre="Azul marino", codigo_hex="#17233B", activo=True
    )
    repository.product_has_color.return_value = True

    async def persist_image(item: ImagenProducto) -> ImagenProducto:
        item.id_imagen = 4
        item.created_at = datetime(2026, 8, 30, tzinfo=UTC)
        return item

    repository.add.side_effect = persist_image
    service = CatalogService(session, repository)
    payload = ProductImageCreate(
        id_color=2,
        public_id="catalog/polo-azul",
        secure_url="https://example.com/polo-azul.jpg",
        es_principal=True,
    )
    result = await service.create_image(1, payload, AuditContext(usuario_id=99))
    assert result.id_color == 2
    repository.product_has_color.assert_awaited_once_with(1, 2)
    repository.clear_principal_image.assert_awaited_once_with(1, 2)


@pytest.mark.parametrize(
    "available,minimum,state",
    [(8, 2, "DISPONIBLE"), (2, 2, "STOCK_BAJO"), (0, 2, "AGOTADO")],
)
def test_stock_state(available: int, minimum: int, state: str) -> None:
    assert CatalogService.stock_state(available, minimum) == state


async def test_catalog_mutation_applies_audit_context() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    repository.get_product.return_value = SimpleNamespace(product=Producto(id_producto=1))
    repository.replace_current_price.return_value = HistorialPrecio(
        id_historial_precio=3,
        id_producto=1,
        precio=Decimal("120.00"),
        fecha_inicio=datetime(2026, 8, 30, tzinfo=UTC),
        creado_por=99,
    )
    service = CatalogService(session, repository)
    await service.set_price(
        1, PriceCreate(precio=120), 99, AuditContext(usuario_id=99, request_id="req-1")
    )
    assert session.execute.await_count >= 1


async def test_catalog_not_found_error() -> None:
    service = AsyncMock()
    service.get_product.side_effect = CatalogNotFoundError("Product not found")
    response = await call_catalog("GET", "/api/v1/products/999", service=service)
    assert response.status_code == 404


def test_no_physical_delete_for_catalog_resources() -> None:
    allowed_relations = {
        "/api/v1/products/{product_id}/seasons/{season_id}",
        "/api/v1/products/{product_id}/collections/{collection_id}",
        # Product images are external Cloudinary assets explicitly managed by the editor.
        "/api/v1/product-images/{image_id}",
        "/api/v1/suppliers/{supplier_id}/products/{product_id}",
        "/api/v1/employees/{employee_id}/permissions/{permission_id}",
        "/api/v1/admin/promotions/{promotion_id}",
        "/api/v1/auth/me/avatar",
    }
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/v1/") and "delete" in operations:
            assert path in allowed_relations
