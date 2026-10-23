from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.commerce.dependencies import get_commerce_service
from app.modules.commerce.schemas import (
    ActivePromotionItem,
    PromotionResponse,
)

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=UTC)

SAMPLE_PROMO = PromotionResponse(
    id_promocion=1,
    nombre="20% Off Primavera",
    descripcion="Descuento en toda la temporada primavera.",
    porcentaje_descuento=Decimal("20.00"),
    fecha_inicio=NOW - timedelta(days=1),
    fecha_fin=NOW + timedelta(days=10),
    activo=True,
    created_at=NOW,
    updated_at=NOW,
    producto_ids=[1, 2],
    categoria_ids=[3],
    temporada_ids=[1],
    productos_count=2,
    categorias_count=1,
    temporadas_count=1,
    estado_vigencia="VIGENTE",
)


def make_principal(permissions: list[str]) -> CurrentPrincipal:
    user = Usuario(
        id_usuario=1,
        nombres="Marketing",
        apellidos="Capricho",
        correo="marketing@capricho.com",
        password_hash="fake",
    )
    return CurrentPrincipal(
        user=user,
        roles=frozenset(["ADMIN"]),
        permissions=frozenset(permissions),
        session_id="test-session-promotions",
        id_sucursal=1,
    )


@pytest.mark.asyncio
async def test_list_promotions_requires_permission() -> None:
    principal_no_perm = make_principal(["ventas.ver"])

    app.dependency_overrides[get_current_principal] = lambda: principal_no_perm

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/promotions")

    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_promotions_admin_success() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    mock_service.list_promotions.return_value = [SAMPLE_PROMO]

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_commerce_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/promotions")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["nombre"] == "20% Off Primavera"
    assert Decimal(str(data[0]["porcentaje_descuento"])) == Decimal("20.00")
    assert data[0]["estado_vigencia"] == "VIGENTE"


@pytest.mark.asyncio
async def test_create_promotion_success() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    mock_service.create_promotion.return_value = SAMPLE_PROMO

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_commerce_service] = lambda: mock_service

    payload = {
        "nombre": "20% Off Primavera",
        "descripcion": "Descuento en toda la temporada primavera.",
        "porcentaje_descuento": 20.0,
        "fecha_inicio": (NOW - timedelta(days=1)).isoformat(),
        "fecha_fin": (NOW + timedelta(days=10)).isoformat(),
        "activo": True,
        "producto_ids": [1, 2],
        "categoria_ids": [3],
        "temporada_ids": [1],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/admin/promotions", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["id_promocion"] == 1


@pytest.mark.asyncio
async def test_create_promotion_validation_dates() -> None:
    principal = make_principal(["promociones.gestionar"])
    app.dependency_overrides[get_current_principal] = lambda: principal

    payload = {
        "nombre": "Promo Inválida",
        "porcentaje_descuento": 15.0,
        "fecha_inicio": (NOW + timedelta(days=5)).isoformat(),
        "fecha_fin": NOW.isoformat(),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/admin/promotions", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_promotion_success() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    updated = SAMPLE_PROMO.model_copy(update={"nombre": "Super Oferta 30%"})
    mock_service.update_promotion.return_value = updated

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_commerce_service] = lambda: mock_service

    payload = {"nombre": "Super Oferta 30%"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch("/api/v1/admin/promotions/1", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["nombre"] == "Super Oferta 30%"


@pytest.mark.asyncio
async def test_delete_promotion_success() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    mock_service.delete_promotion.return_value = {"mensaje": "Promoción eliminada con éxito"}

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_commerce_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete("/api/v1/admin/promotions/1")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["mensaje"] == "Promoción eliminada con éxito"


@pytest.mark.asyncio
async def test_list_active_promotions_public() -> None:
    mock_service = AsyncMock()
    mock_service.list_active_promotions_public.return_value = [
        ActivePromotionItem(
            id_promocion=1,
            nombre="20% Off Primavera",
            descripcion="Descuento en toda la temporada primavera.",
            porcentaje_descuento=Decimal("20.00"),
            fecha_inicio=NOW - timedelta(days=1),
            fecha_fin=NOW + timedelta(days=10),
            productos_count=2,
            categorias_count=1,
            temporadas_count=1,
        )
    ]

    app.dependency_overrides[get_commerce_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/promotions/active")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["nombre"] == "20% Off Primavera"
    assert Decimal(str(data[0]["porcentaje_descuento"])) == Decimal("20.00")
