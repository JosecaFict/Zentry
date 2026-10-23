from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import (
    CurrentPrincipal,
    get_current_principal,
    get_optional_principal,
)
from app.modules.auth.models import Usuario
from app.modules.recommendations.dependencies import get_recommendation_service
from app.modules.recommendations.schemas import (
    InteractionResponse,
    RecommendationConfigResponse,
    RecommendationStats,
    RecommendedProductItem,
)

NOW = datetime(2026, 9, 14, 12, 0, 0, tzinfo=UTC)

SAMPLE_CONFIG = RecommendationConfigResponse(
    id_configuracion=1,
    peso_categoria=Decimal("40.00"),
    peso_marca=Decimal("20.00"),
    peso_color=Decimal("15.00"),
    peso_talla=Decimal("10.00"),
    peso_temporada=Decimal("10.00"),
    peso_promocion=Decimal("5.00"),
    activo=True,
    created_at=NOW,
    suma_pesos=Decimal("100.00"),
)

SAMPLE_REC_ITEM = RecommendedProductItem(
    id_producto=1,
    nombre="Camisa Oxford Clásica",
    categoria="Camisas",
    marca="Capricho Elegance",
    precio_actual=Decimal("180.00"),
    descuento_porcentaje=Decimal("15.00"),
    precio_promocional=Decimal("153.00"),
    imagen_url="https://res.cloudinary.com/demo/image/upload/sample.jpg",
    puntuacion=Decimal("88.50"),
    motivo="Por tu preferencia en Camisas",
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
        session_id="test-session-recommendations",
        id_sucursal=1,
    )


@pytest.mark.asyncio
async def test_get_recommendations_anonymous() -> None:
    mock_service = AsyncMock()
    mock_service.get_personalized_recommendations.return_value = [SAMPLE_REC_ITEM]

    app.dependency_overrides[get_recommendation_service] = lambda: mock_service
    app.dependency_overrides[get_optional_principal] = lambda: None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recommendations")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Camisa Oxford Clásica"
    assert Decimal(str(data[0]["puntuacion"])) == Decimal("88.50")


@pytest.mark.asyncio
async def test_get_related_products() -> None:
    mock_service = AsyncMock()
    mock_service.get_related_products.return_value = [SAMPLE_REC_ITEM]

    app.dependency_overrides[get_recommendation_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recommendations/products/1/related")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id_producto"] == 1


@pytest.mark.asyncio
async def test_record_interaction_authenticated() -> None:
    principal = make_principal(["ventas.ver"])
    mock_service = AsyncMock()
    mock_service.record_interaction.return_value = InteractionResponse(
        id_interaccion=10,
        id_cliente=1,
        id_producto=1,
        id_variante=2,
        tipo_interaccion="VER_PRODUCTO",
        fecha_hora=NOW,
    )

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_recommendation_service] = lambda: mock_service

    payload = {
        "id_producto": 1,
        "id_variante": 2,
        "tipo_interaccion": "VER_PRODUCTO",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/recommendations/interaction", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["id_interaccion"] == 10
    assert response.json()["tipo_interaccion"] == "VER_PRODUCTO"


@pytest.mark.asyncio
async def test_get_config_admin() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    mock_service.get_config.return_value = SAMPLE_CONFIG

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_recommendation_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/recommendations/config")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert Decimal(str(response.json()["peso_categoria"])) == Decimal("40.00")
    assert Decimal(str(response.json()["suma_pesos"])) == Decimal("100.00")


@pytest.mark.asyncio
async def test_update_config_validation_rejects_non_100() -> None:
    principal = make_principal(["promociones.gestionar"])
    app.dependency_overrides[get_current_principal] = lambda: principal

    payload = {
        "peso_categoria": 50.0,
        "peso_marca": 20.0,
        "peso_color": 15.0,
        "peso_talla": 10.0,
        "peso_temporada": 10.0,
        "peso_promocion": 10.0,  # Sum = 115 != 100
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.put("/api/v1/admin/recommendations/config", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_config_success() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    updated_config = SAMPLE_CONFIG.model_copy(
        update={"peso_categoria": Decimal("35.00"), "peso_promocion": Decimal("10.00")}
    )
    mock_service.update_config.return_value = updated_config

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_recommendation_service] = lambda: mock_service

    payload = {
        "peso_categoria": 35.0,
        "peso_marca": 20.0,
        "peso_color": 15.0,
        "peso_talla": 10.0,
        "peso_temporada": 10.0,
        "peso_promocion": 10.0,
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.put("/api/v1/admin/recommendations/config", json=payload)

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert Decimal(str(response.json()["peso_categoria"])) == Decimal("35.00")
    assert Decimal(str(response.json()["peso_promocion"])) == Decimal("10.00")


@pytest.mark.asyncio
async def test_recommendation_stats_admin() -> None:
    principal = make_principal(["promociones.gestionar"])
    mock_service = AsyncMock()
    mock_service.get_stats.return_value = RecommendationStats(
        total_interacciones=120,
        interacciones_por_tipo={"VER_PRODUCTO": 80, "COMPRAR": 40},
        clientes_con_interacciones=18,
        pesos_activos={
            "categoria": Decimal("40.00"),
            "marca": Decimal("20.00"),
            "color": Decimal("15.00"),
            "talla": Decimal("10.00"),
            "temporada": Decimal("10.00"),
            "promocion": Decimal("5.00"),
        },
    )

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_recommendation_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/recommendations/stats")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total_interacciones"] == 120
    assert response.json()["clientes_con_interacciones"] == 18
