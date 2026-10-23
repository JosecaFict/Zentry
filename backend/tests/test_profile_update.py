from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_auth_service, get_current_principal
from app.modules.auth.models import Usuario


def make_user(
    *,
    id_usuario: int = 1,
    nombres: str = "Maria",
    apellidos: str = "Perez",
    correo: str = "maria@example.com",
    telefono: str | None = "70012345",
    ci: str | None = "9876543",
    estado: str = "ACTIVO",
) -> Usuario:
    return Usuario(
        id_usuario=id_usuario,
        nombres=nombres,
        apellidos=apellidos,
        correo=correo,
        telefono=telefono,
        ci=ci,
        estado=estado,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_update_profile_success() -> None:
    initial_user = make_user()
    updated_user = make_user(
        nombres="Maria Elena",
        apellidos="Perez Rojas",
        telefono="77889900",
        ci="1234567-SC",
    )

    principal = CurrentPrincipal(
        user=initial_user,
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(),
        session_id="session-1",
    )

    mock_service = AsyncMock()
    mock_service.update_profile.return_value = updated_user

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield mock_service

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_auth_service] = override_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/auth/me",
                json={
                    "nombres": "Maria Elena",
                    "apellidos": "Perez Rojas",
                    "telefono": "77889900",
                    "ci": "1234567-SC",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["nombres"] == "Maria Elena"
    assert data["apellidos"] == "Perez Rojas"
    assert data["telefono"] == "77889900"
    assert data["ci"] == "1234567-SC"
    assert data["correo"] == "maria@example.com"


@pytest.mark.asyncio
async def test_update_profile_without_token_returns_401() -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/auth/me",
            json={"nombres": "Ana", "apellidos": "Lopez"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_empty_name_returns_422() -> None:
    principal = CurrentPrincipal(
        user=make_user(),
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(),
        session_id="session-1",
    )

    app.dependency_overrides[get_current_principal] = lambda: principal
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/auth/me",
                json={"nombres": "   ", "apellidos": "Lopez"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_success() -> None:
    principal = CurrentPrincipal(
        user=make_user(),
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"admin.total"}),
        session_id="session-1",
    )

    mock_service = AsyncMock()
    mock_service.change_password.return_value = None

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield mock_service

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_auth_service] = override_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/change-password",
                json={
                    "current_password": "Password123!",
                    "new_password": "NewSecret456!",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"message": "Contraseña actualizada exitosamente"}


@pytest.mark.asyncio
async def test_change_password_invalid_current_returns_401() -> None:
    from app.modules.auth.exceptions import InvalidCredentialsError

    principal = CurrentPrincipal(
        user=make_user(),
        roles=frozenset({"ADMIN"}),
        permissions=frozenset({"admin.total"}),
        session_id="session-1",
    )

    mock_service = AsyncMock()
    mock_service.change_password.side_effect = InvalidCredentialsError("Current password is incorrect")

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield mock_service

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_auth_service] = override_service

    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/change-password",
                json={
                    "current_password": "WrongPassword123!",
                    "new_password": "NewSecret456!",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_weak_new_password_returns_422() -> None:
    principal = CurrentPrincipal(
        user=make_user(),
        roles=frozenset({"ADMIN"}),
        permissions=frozenset(),
        session_id="session-1",
    )

    app.dependency_overrides[get_current_principal] = lambda: principal
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/change-password",
                json={
                    "current_password": "Password123!",
                    "new_password": "weak",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_service_update_profile_commits_transaction() -> None:
    from app.db.audit_context import AuditContext
    from app.modules.auth.schemas import UpdateProfileRequest
    from app.modules.auth.service import AuthService

    mock_session = AsyncMock()
    mock_repository = AsyncMock()
    mock_repository.get_user_by_ci.return_value = None
    updated_user = make_user(nombres="Carlos", apellidos="Dueñas")
    mock_repository.update_profile.return_value = updated_user

    service = AuthService(session=mock_session, repository=mock_repository)
    audit = AuditContext(usuario_id=1, sesion_id="s1")

    result = await service.update_profile(
        user_id=1,
        payload=UpdateProfileRequest(
            nombres="Carlos",
            apellidos="Dueñas",
            telefono="70011223",
            ci="6339300",
        ),
        audit_context=audit,
    )

    assert result == updated_user
    mock_session.commit.assert_awaited_once()
    mock_session.begin.assert_not_called()


@pytest.mark.asyncio
async def test_auth_service_update_profile_raises_ci_conflict() -> None:
    from app.db.audit_context import AuditContext
    from app.modules.auth.exceptions import CiAlreadyRegisteredError
    from app.modules.auth.schemas import UpdateProfileRequest
    from app.modules.auth.service import AuthService

    mock_session = AsyncMock()
    mock_repository = AsyncMock()
    existing_other_user = make_user(id_usuario=2, ci="6339300")
    mock_repository.get_user_by_ci.return_value = existing_other_user

    service = AuthService(session=mock_session, repository=mock_repository)
    audit = AuditContext(usuario_id=1, sesion_id="s1")

    with pytest.raises(CiAlreadyRegisteredError):
        await service.update_profile(
            user_id=1,
            payload=UpdateProfileRequest(
                nombres="Carlos",
                apellidos="Dueñas",
                ci="6339300",
            ),
            audit_context=audit,
        )


@pytest.mark.asyncio
async def test_auth_service_update_profile_rolls_back_on_error() -> None:
    from app.db.audit_context import AuditContext
    from app.modules.auth.schemas import UpdateProfileRequest
    from app.modules.auth.service import AuthService

    mock_session = AsyncMock()
    mock_repository = AsyncMock()
    mock_repository.update_profile.side_effect = RuntimeError("DB error")

    service = AuthService(session=mock_session, repository=mock_repository)
    audit = AuditContext(usuario_id=1, sesion_id="s1")

    with pytest.raises(RuntimeError, match="DB error"):
        await service.update_profile(
            user_id=1,
            payload=UpdateProfileRequest(nombres="Carlos", apellidos="Dueñas"),
            audit_context=audit,
        )

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_called()

