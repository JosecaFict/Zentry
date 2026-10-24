import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.tenant import ResolvedTenant


@pytest.mark.asyncio
async def test_tenant_slug_route_reuses_api_router(monkeypatch) -> None:
    async def resolve(slug: str) -> ResolvedTenant:
        return ResolvedTenant(id_tenant=1, slug=slug, estado="ACTIVO")

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", resolve)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/t/capricho-store/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_tenant_slug_route_rejects_unknown_and_suspended(monkeypatch) -> None:
    async def missing(_: str) -> None:
        return None

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", missing)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        missing_response = await client.get("/api/v1/t/missing-store/health")
    assert missing_response.status_code == 404

    async def suspended(slug: str) -> ResolvedTenant:
        return ResolvedTenant(id_tenant=8, slug=slug, estado="SUSPENDIDO")

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", suspended)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        suspended_response = await client.get("/api/v1/t/suspendida/health")
    assert suspended_response.status_code == 403


@pytest.mark.asyncio
async def test_tenant_header_sets_context_without_rewriting_path(monkeypatch) -> None:
    async def resolve(slug: str) -> ResolvedTenant:
        return ResolvedTenant(id_tenant=4, slug=slug, estado="ACTIVO")

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", resolve)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-Slug": "capricho-store"},
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_tenant_route_rejects_conflicting_header(monkeypatch) -> None:
    async def should_not_resolve(_: str) -> ResolvedTenant:
        raise AssertionError("A conflicting tenant identity must be rejected first")

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", should_not_resolve)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-Slug": "otra-tienda"},
    ) as client:
        response = await client.get("/api/v1/t/capricho-store/health")

    assert response.status_code == 400
    assert response.json()["detail"] == "La URL y la cabecera indican empresas diferentes"


@pytest.mark.asyncio
async def test_platform_routes_ignore_tenant_header(monkeypatch) -> None:
    async def should_not_resolve(_: str) -> ResolvedTenant:
        raise AssertionError("Platform routes must remain global")

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", should_not_resolve)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-Slug": "capricho-store"},
    ) as client:
        response = await client.get("/api/v1/platform/overview")

    assert response.status_code == 401
