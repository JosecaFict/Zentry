from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.integrations.openrouteservice import OpenRouteServiceClient, RouteEstimate
from app.modules.auth.models import Cliente, Sucursal
from app.modules.commerce.models import CotizacionEnvio, DireccionCliente, TarifaEnvio
from app.modules.commerce.schemas import ShippingQuoteCreate
from app.modules.commerce.service import CommerceService


async def test_openrouteservice_client_returns_estimate_on_success() -> None:
    client = OpenRouteServiceClient(api_key="fake-jwt-token")

    fake_response = {
        "routes": [
            {
                "summary": {
                    "distance": 8450.5,
                    "duration": 1140.2,
                }
            }
        ]
    }

    from unittest.mock import MagicMock

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_response
        mock_post.return_value = mock_resp

        estimate = await client.calculate_route(
            start_lat=-17.7654,
            start_lng=-63.1812,
            end_lat=-17.7921,
            end_lng=-63.1650,
        )

    assert estimate is not None
    assert estimate.distance_km == Decimal("8.45")
    assert estimate.duration_min == 19
    assert estimate.provider == "OPEN_ROUTE_SERVICE"


async def test_openrouteservice_client_returns_none_when_unconfigured() -> None:
    client = OpenRouteServiceClient(api_key=None)
    assert not client.is_configured
    assert await client.calculate_route(0, 0, 1, 1) is None


async def test_quote_shipping_uses_openrouteservice_when_available() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    route_client = AsyncMock()

    customer = Cliente(id_cliente=4, id_usuario=9, estado="ACTIVO")
    branch = Sucursal(
        id_sucursal=1,
        nombre="Central",
        activo=True,
        latitud=Decimal("-17.765400"),
        longitud=Decimal("-63.181200"),
    )
    address = DireccionCliente(
        id_direccion=2,
        id_cliente=4,
        activo=True,
        latitud=Decimal("-17.792100"),
        longitud=Decimal("-63.165000"),
    )
    rate = TarifaEnvio(
        id_tarifa=1,
        tarifa_base=Decimal("15.00"),
        distancia_base_km=Decimal("5.00"),
        costo_km_adicional=Decimal("2.50"),
        activo=True,
    )

    repository.customer_by_user.return_value = customer
    repository.get.side_effect = lambda model, identity: branch if model is Sucursal else address
    repository.active_rate.return_value = rate

    route_client.calculate_route.return_value = RouteEstimate(
        distance_km=Decimal("8.00"),
        duration_min=18,
        provider="OPEN_ROUTE_SERVICE",
    )

    async def add(entity):
        if isinstance(entity, CotizacionEnvio):
            entity.id_cotizacion = 10
        return entity

    repository.add.side_effect = add

    service = CommerceService(session, repository, route_client=route_client)
    quote = await service.quote_shipping(9, ShippingQuoteCreate(id_sucursal=1, id_direccion=2))

    assert quote.distancia_km == Decimal("8.00")
    assert quote.duracion_estimada_min == 18
    assert quote.proveedor_rutas == "OPEN_ROUTE_SERVICE"
    # cost = 15.00 + (8.00 - 5.00) * 2.50 = 15 + 7.50 = 22.50
    assert quote.costo_estimado == Decimal("22.50")
    session.commit.assert_awaited_once()


async def test_quote_shipping_rounds_additional_km_upward() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    route_client = AsyncMock()

    customer = Cliente(id_cliente=1, id_usuario=1, estado="ACTIVO")
    branch = Sucursal(id_sucursal=1, nombre="Central", activo=True, latitud=Decimal("-17.76"), longitud=Decimal("-63.18"))
    address = DireccionCliente(id_direccion=1, id_cliente=1, activo=True, latitud=Decimal("-17.78"), longitud=Decimal("-63.19"))
    # Base: 5.00 Bs (1 km), 2.50 Bs per additional km
    rate = TarifaEnvio(id_tarifa=1, tarifa_base=Decimal("5.00"), distancia_base_km=Decimal("1.00"), costo_km_adicional=Decimal("2.50"), activo=True)

    repository.customer_by_user.return_value = customer
    repository.get.side_effect = lambda model, identity: branch if model is Sucursal else address
    repository.active_rate.return_value = rate
    repository.add.side_effect = lambda entity: entity

    service = CommerceService(session, repository, route_client=route_client)

    # Test 1: 3.55 km -> 1 km base (5.00) + ceil(2.55 km = 3 km) * 2.50 = 5.00 + 7.50 = 12.50 Bs
    route_client.calculate_route.return_value = RouteEstimate(distance_km=Decimal("3.55"), duration_min=10, provider="OPEN_ROUTE_SERVICE")
    quote1 = await service.quote_shipping(1, ShippingQuoteCreate(id_sucursal=1, id_direccion=1))
    assert quote1.costo_estimado == Decimal("12.50")

    # Test 2: 1.10 km -> 1 km base (5.00) + ceil(0.10 km = 1 km) * 2.50 = 5.00 + 2.50 = 7.50 Bs
    route_client.calculate_route.return_value = RouteEstimate(distance_km=Decimal("1.10"), duration_min=5, provider="OPEN_ROUTE_SERVICE")
    quote2 = await service.quote_shipping(1, ShippingQuoteCreate(id_sucursal=1, id_direccion=1))
    assert quote2.costo_estimado == Decimal("7.50")

    # Test 3: 0.80 km (within base) -> 5.00 Bs
    route_client.calculate_route.return_value = RouteEstimate(distance_km=Decimal("0.80"), duration_min=3, provider="OPEN_ROUTE_SERVICE")
    quote3 = await service.quote_shipping(1, ShippingQuoteCreate(id_sucursal=1, id_direccion=1))
    assert quote3.costo_estimado == Decimal("5.00")


async def test_quote_shipping_uses_fallback_coordinates_when_missing() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    route_client = AsyncMock()

    customer = Cliente(id_cliente=1, id_usuario=1, estado="ACTIVO")
    branch = Sucursal(id_sucursal=1, nombre="Central", activo=True, latitud=None, longitud=None)
    address = DireccionCliente(id_direccion=1, id_cliente=1, activo=True, latitud=None, longitud=None)
    rate = TarifaEnvio(id_tarifa=1, tarifa_base=Decimal("15.00"), distancia_base_km=Decimal("5.00"), costo_km_adicional=Decimal("2.50"), activo=True)

    repository.customer_by_user.return_value = customer
    repository.get.side_effect = lambda model, identity: branch if model is Sucursal else address
    repository.active_rate.return_value = rate
    repository.add.side_effect = lambda entity: entity

    # Route client returns a route based on fallback coordinates
    route_client.calculate_route.return_value = RouteEstimate(distance_km=Decimal("4.00"), duration_min=12, provider="OPEN_ROUTE_SERVICE")

    service = CommerceService(session, repository, route_client=route_client)
    quote = await service.quote_shipping(1, ShippingQuoteCreate(id_sucursal=1, id_direccion=1))

    assert quote.costo_estimado == Decimal("15.00")
    assert quote.distancia_km == Decimal("4.00")
    # Verify calculate_route was called with default fallback coordinates (-17.7833, -63.1821)
    route_client.calculate_route.assert_awaited_once_with(
        start_lat=-17.7833,
        start_lng=-63.1821,
        end_lat=-17.7833,
        end_lng=-63.1821,
    )


