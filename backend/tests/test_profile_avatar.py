from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.auth.dependencies import CurrentPrincipal, get_auth_service, get_current_principal
from app.modules.auth.models import Usuario
from app.modules.catalog.dependencies import get_cloudinary_storage


def make_user(
    *,
    id_usuario: int = 1,
    nombres: str = "Maria",
    apellidos: str = "Perez",
    correo: str = "maria@example.com",
    telefono: str | None = "70012345",
    ci: str | None = "9876543",
    estado: str = "ACTIVO",
    avatar_url: str | None = None,
) -> Usuario:
    return Usuario(
        id_usuario=id_usuario,
        nombres=nombres,
        apellidos=apellidos,
        correo=correo,
        telefono=telefono,
        ci=ci,
        estado=estado,
        avatar_url=avatar_url,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_upload_avatar_success() -> None:
    initial_user = make_user()
    updated_user = make_user(avatar_url="https://res.cloudinary.com/demo/image/upload/v1/avatars/1.jpg")

    principal = CurrentPrincipal(
        user=initial_user,
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(),
        session_id="session-1",
    )

    mock_service = AsyncMock()
    mock_service.upload_avatar.return_value = updated_user

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield mock_service

    mock_storage = AsyncMock()

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_auth_service] = override_service
    app.dependency_overrides[get_cloudinary_storage] = lambda: mock_storage

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            files = {"file": ("avatar.jpg", b"\xff\xd8\xff\xe0testimagecontent", "image/jpeg")}
            response = await client.post("/api/v1/auth/me/avatar", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["avatar_url"] == "https://res.cloudinary.com/demo/image/upload/v1/avatars/1.jpg"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_avatar_success() -> None:
    initial_user = make_user(avatar_url="https://res.cloudinary.com/demo/image/upload/v1/avatars/1.jpg")
    updated_user = make_user(avatar_url=None)

    principal = CurrentPrincipal(
        user=initial_user,
        roles=frozenset({"CLIENTE"}),
        permissions=frozenset(),
        session_id="session-1",
    )

    mock_service = AsyncMock()
    mock_service.delete_avatar.return_value = updated_user

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield mock_service

    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_auth_service] = override_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/auth/me/avatar")

        assert response.status_code == 200
        data = response.json()
        assert data["avatar_url"] is None
    finally:
        app.dependency_overrides.clear()
