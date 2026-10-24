from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import AccessTokenClaims
from app.modules.auth.dependencies import get_current_principal, get_optional_principal
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.auth.repository import TenantAccess


def tenant_user() -> SimpleNamespace:
    return SimpleNamespace(
        id_usuario=91,
        id_tenant=7,
        estado="ACTIVO",
    )


def tenant_access() -> TenantAccess:
    return TenantAccess(
        id_tenant=7,
        slug="tienda-uno",
        tenant_estado="ACTIVO",
        subscription_estado="ACTIVA",
        plan_codigo="BASICO",
        max_sucursales_activas=2,
        max_usuarios_internos=5,
        max_productos_activos=100,
        permite_reportes_ia=False,
        permite_offline=True,
    )


def request_with_tenant(slug: str | None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/auth/me",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
        "scheme": "http",
        "state": {},
    }
    request = Request(scope)
    if slug is not None:
        request.state.tenant_slug = slug
    return request


def auth_repository() -> AsyncMock:
    repository = AsyncMock()
    repository.get_user_by_id.return_value = tenant_user()
    repository.get_tenant_access.return_value = tenant_access()
    return repository


@pytest.mark.asyncio
@pytest.mark.parametrize("requested_slug", [None, "tienda-dos"])
async def test_tenant_token_requires_matching_tenant_context(
    monkeypatch: pytest.MonkeyPatch,
    requested_slug: str | None,
) -> None:
    repository = auth_repository()
    monkeypatch.setattr(
        "app.modules.auth.dependencies.AuthRepository",
        lambda _: repository,
    )
    monkeypatch.setattr(
        "app.modules.auth.dependencies.decode_access_token",
        lambda _: AccessTokenClaims(user_id=91, session_id="session-1"),
    )

    with pytest.raises(PermissionDeniedError):
        await get_current_principal(
            request=request_with_tenant(requested_slug),
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="valid-token",
            ),
            session=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_optional_tenant_token_is_ignored_outside_its_tenant(monkeypatch) -> None:
    repository = auth_repository()
    monkeypatch.setattr(
        "app.modules.auth.dependencies.AuthRepository",
        lambda _: repository,
    )
    monkeypatch.setattr(
        "app.modules.auth.dependencies.decode_access_token",
        lambda _: AccessTokenClaims(user_id=91, session_id="session-1"),
    )

    principal = await get_optional_principal(
        request=request_with_tenant("tienda-dos"),
        credentials=HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid-token",
        ),
        session=AsyncMock(),
    )

    assert principal is None
