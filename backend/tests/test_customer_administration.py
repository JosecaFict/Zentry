from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient, Response

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.customers.dependencies import get_customer_admin_service
from app.modules.customers.schemas import (
    CustomerAddressItem,
    CustomerAdminDetail,
    CustomerAdminSummary,
)


def make_principal(
    *permissions: str,
    roles: frozenset[str] = frozenset({"ADMIN"}),
) -> CurrentPrincipal:
    user = Usuario(
        id_usuario=1,
        nombres="Admin",
        apellidos="Principal",
        correo="admin@capricho.com",
        telefono="70000000",
        ci="ADM-001",
        password_hash="hashed",
        estado="ACTIVO",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return CurrentPrincipal(
        user=user,
        roles=roles,
        permissions=frozenset(permissions),
        session_id="test-session-id",
    )


def make_customer_summary(
    *,
    id_cliente: int = 1,
    nombres: str = "María",
    apellidos: str = "Paredes",
    correo: str = "maria@example.com",
    ci: str | None = "6543210",
    telefono: str | None = "71234567",
    estado: str = "ACTIVO",
    total_pedidos: int = 3,
    total_reservas: int = 1,
    total_ventas: int = 4,
) -> CustomerAdminSummary:
    return CustomerAdminSummary(
        id_cliente=id_cliente,
        id_usuario=20,
        nombres=nombres,
        apellidos=apellidos,
        nombre_completo=f"{nombres} {apellidos}",
        correo=correo,
        ci=ci,
        telefono=telefono,
        fecha_nacimiento=date(1995, 5, 20),
        estado=estado,
        total_pedidos=total_pedidos,
        total_reservas=total_reservas,
        total_ventas=total_ventas,
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
        updated_at=datetime(2026, 1, 15, tzinfo=UTC),
    )


def make_customer_detail(
    *,
    id_cliente: int = 1,
    nombres: str = "María",
    apellidos: str = "Paredes",
    correo: str = "maria@example.com",
    ci: str | None = "6543210",
    telefono: str | None = "71234567",
    estado: str = "ACTIVO",
) -> CustomerAdminDetail:
    summary = make_customer_summary(
        id_cliente=id_cliente,
        nombres=nombres,
        apellidos=apellidos,
        correo=correo,
        ci=ci,
        telefono=telefono,
        estado=estado,
    )
    address = CustomerAddressItem(
        id_direccion=10,
        id_ciudad=1,
        ciudad="Santa Cruz de la Sierra",
        departamento="Santa Cruz",
        alias="Casa",
        zona="Equipetrol",
        direccion="Av. San Martín #123",
        referencia="Frente a la plaza",
        es_principal=True,
        activo=True,
    )
    return CustomerAdminDetail(
        **summary.model_dump(),
        direcciones=[address],
    )


async def call_customer_endpoint(
    method: str,
    path: str,
    *,
    principal: CurrentPrincipal | None = None,
    service: AsyncMock,
    json: dict | None = None,
    params: dict | None = None,
) -> Response:
    async def override_principal() -> CurrentPrincipal:
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return principal

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield service

    app.dependency_overrides[get_current_principal] = override_principal
    app.dependency_overrides[get_customer_admin_service] = override_service
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(
                method=method,
                url=f"/api/v1{path}",
                json=json,
                params=params,
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        app.dependency_overrides.pop(get_current_principal, None)
        app.dependency_overrides.pop(get_customer_admin_service, None)


@pytest.mark.asyncio
async def test_list_customers_success():
    service = AsyncMock()
    customer1 = make_customer_summary(id_cliente=1, nombres="Ana", apellidos="Gomez")
    customer2 = make_customer_summary(id_cliente=2, nombres="Bruno", apellidos="Diaz")
    service.list_customers.return_value = [customer1, customer2]

    principal = make_principal("ventas.ver")
    response = await call_customer_endpoint("GET", "/customers", principal=principal, service=service)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert data[0]["nombres"] == "Ana"
    assert data[1]["nombres"] == "Bruno"
    assert data[0]["total_pedidos"] == 3


@pytest.mark.asyncio
async def test_list_customers_with_filters():
    service = AsyncMock()
    service.list_customers.return_value = []
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint(
        "GET",
        "/customers",
        principal=principal,
        service=service,
        params={"q": "Gomez", "estado": "ACTIVO", "limit": "20", "offset": "10"},
    )

    assert response.status_code == status.HTTP_200_OK
    service.list_customers.assert_awaited_once_with(
        q="Gomez",
        estado="ACTIVO",
        limit=20,
        offset=10,
    )


@pytest.mark.asyncio
async def test_list_customers_forbidden_without_permission():
    service = AsyncMock()
    principal = make_principal("productos.ver", roles=frozenset({"CAJERO"}))

    response = await call_customer_endpoint("GET", "/customers", principal=principal, service=service)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_customer_success():
    service = AsyncMock()
    detail = make_customer_detail(id_cliente=5)
    service.get_customer.return_value = detail
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint("GET", "/customers/5", principal=principal, service=service)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id_cliente"] == 5
    assert len(data["direcciones"]) == 1
    assert data["direcciones"][0]["zona"] == "Equipetrol"


@pytest.mark.asyncio
async def test_get_customer_not_found():
    service = AsyncMock()
    service.get_customer.side_effect = HTTPException(status_code=404, detail="Cliente no encontrado")
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint("GET", "/customers/999", principal=principal, service=service)
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_customer_success():
    service = AsyncMock()
    updated = make_customer_detail(
        id_cliente=1,
        nombres="María Elena",
        apellidos="Paredes Rojas",
        correo="nuevo.correo@example.com",
        ci="1234567",
        telefono="79998888",
        estado="INACTIVO",
    )
    service.update_customer.return_value = updated
    principal = make_principal("ventas.ver")

    payload = {
        "nombres": "María Elena",
        "apellidos": "Paredes Rojas",
        "correo": "nuevo.correo@example.com",
        "ci": "1234567",
        "telefono": "79998888",
        "estado": "INACTIVO",
        "nuevo_password": "NewSecretPassword123",
    }
    response = await call_customer_endpoint(
        "PATCH",
        "/customers/1",
        principal=principal,
        service=service,
        json=payload,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["nombres"] == "María Elena"
    assert data["correo"] == "nuevo.correo@example.com"
    assert data["estado"] == "INACTIVO"
    service.update_customer.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_customer_conflict_email():
    service = AsyncMock()
    service.update_customer.side_effect = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="El correo electrónico ingresado ya está registrado por otro usuario",
    )
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint(
        "PATCH",
        "/customers/1",
        principal=principal,
        service=service,
        json={"correo": "ocupado@example.com"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "correo electrónico" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_customer_conflict_ci():
    service = AsyncMock()
    service.update_customer.side_effect = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="El número de CI ya está registrado por otro usuario",
    )
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint(
        "PATCH",
        "/customers/1",
        principal=principal,
        service=service,
        json={"ci": "DUPLICATED-CI"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "CI" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_customer_empty_payload_rejected():
    service = AsyncMock()
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint(
        "PATCH",
        "/customers/1",
        principal=principal,
        service=service,
        json={},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_quick_customer_success():
    service = AsyncMock()
    created = CustomerAdminSummary(
        id_cliente=99,
        id_usuario=999,
        nombres="Juan Carlos",
        apellidos="Perez",
        nombre_completo="Juan Carlos Perez",
        correo="juan.perez@example.com",
        ci="6829401",
        telefono="78012345",
        estado="ACTIVO",
        total_pedidos=0,
        total_reservas=0,
        total_ventas=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.create_quick_customer.return_value = created
    principal = make_principal("ventas.ver")

    response = await call_customer_endpoint(
        "POST",
        "/customers/quick",
        principal=principal,
        service=service,
        json={
            "nombres": "Juan Carlos",
            "apellidos": "Perez",
            "ci": "6829401",
            "correo": "juan.perez@example.com",
            "telefono": "78012345",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id_cliente"] == 99
    assert data["nombre_completo"] == "Juan Carlos Perez"

