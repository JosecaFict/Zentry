from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.types import Receive, Scope, Send

from app.db.tenant_context import (
    current_database_scope,
    current_tenant_id,
    database_scope,
)
from app.middleware.tenant import ResolvedTenant, TenantPathMiddleware
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.platform.dependencies import require_platform_database_scope


def test_database_scope_is_nested_and_restored() -> None:
    assert current_database_scope() == "restricted"
    with database_scope("global"):
        assert current_database_scope() == "global"
        with database_scope("tenant"):
            assert current_database_scope() == "tenant"
        assert current_database_scope() == "global"
    assert current_database_scope() == "restricted"


def capture_app(
    observed: list[tuple[str, int | None]],
) -> Callable[[Scope, Receive, Send], Awaitable[None]]:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        observed.append((current_database_scope(), current_tenant_id()))
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})

    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_scope"),
    [
        ("/api/v1/platform/overview", "identity"),
        ("/api/v1/public/tenants", "restricted"),
        ("/api/v1/auth/login", "identity"),
        ("/api/v1/password/request", "identity"),
        ("/api/v1/health", "restricted"),
    ],
)
async def test_middleware_assigns_database_scope_and_restores_it(
    path: str,
    expected_scope: str,
) -> None:
    observed: list[tuple[str, int | None]] = []
    middleware = TenantPathMiddleware(capture_app(observed))

    async with AsyncClient(
        transport=ASGITransport(app=middleware), base_url="http://test"
    ) as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert observed == [(expected_scope, None)]
    assert current_database_scope() == "restricted"
    assert current_tenant_id() is None


@pytest.mark.asyncio
async def test_platform_scope_is_elevated_only_for_global_superadmin() -> None:
    session = SimpleNamespace(execute=AsyncMock())
    principal = SimpleNamespace(id_tenant=None, roles=frozenset({"SUPERADMIN"}))

    dependency = require_platform_database_scope(principal, session)  # type: ignore[arg-type]
    await anext(dependency)
    try:
        assert current_database_scope() == "global"
        session.execute.assert_awaited_once()
    finally:
        await dependency.aclose()

    assert current_database_scope() == "restricted"


@pytest.mark.asyncio
async def test_platform_scope_rejects_tenant_principal() -> None:
    session = SimpleNamespace(execute=AsyncMock())
    principal = SimpleNamespace(id_tenant=42, roles=frozenset({"ADMIN"}))

    dependency = require_platform_database_scope(principal, session)  # type: ignore[arg-type]
    with pytest.raises(PermissionDeniedError):
        await anext(dependency)

    session.execute.assert_not_awaited()
    assert current_database_scope() == "restricted"


@pytest.mark.asyncio
async def test_middleware_assigns_tenant_scope_and_restores_it(monkeypatch) -> None:
    async def resolve(slug: str) -> ResolvedTenant:
        return ResolvedTenant(id_tenant=42, slug=slug, estado="ACTIVO")

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", resolve)
    observed: list[tuple[str, int | None]] = []
    middleware = TenantPathMiddleware(capture_app(observed))

    async with AsyncClient(
        transport=ASGITransport(app=middleware), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/t/casa-elena/health")

    assert response.status_code == 200
    assert observed == [("tenant", 42)]
    assert current_database_scope() == "restricted"
    assert current_tenant_id() is None


@pytest.mark.asyncio
async def test_middleware_restores_scope_after_early_rejection(monkeypatch) -> None:
    async def missing(_: str) -> None:
        return None

    monkeypatch.setattr("app.middleware.tenant.resolve_tenant_slug", missing)
    middleware = TenantPathMiddleware(capture_app([]))

    async with AsyncClient(
        transport=ASGITransport(app=middleware), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/t/no-existe/health")

    assert response.status_code == 404
    assert current_database_scope() == "restricted"
    assert current_tenant_id() is None
