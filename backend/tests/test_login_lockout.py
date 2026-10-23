from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_password
from app.db.audit_context import AuditContext
from app.main import app
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.exceptions import (
    AccountPermanentlyBlockedError,
    AccountTemporarilyLockedError,
    InvalidCredentialsError,
)
from app.modules.auth.models import Usuario
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService
from app.modules.auth.throttler import InMemoryLoginThrottler


def make_test_user(estado: str = "ACTIVO", password: str = "Password123!") -> Usuario:
    return Usuario(
        id_usuario=99,
        nombres="Carlos",
        apellidos="Gomez",
        correo="carlos@example.com",
        telefono="70000000",
        ci="9876543",
        password_hash=hash_password(password),
        estado=estado,
        created_at=datetime(2026, 8, 30, tzinfo=UTC),
        updated_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def make_audit_context() -> AuditContext:
    return AuditContext(
        usuario_id=None,
        sesion_id="test-session",
        ip="127.0.0.1",
        user_agent="pytest",
        origen="API",
        request_id="test-request",
    )


@pytest.mark.asyncio
async def test_throttler_unit_behavior() -> None:
    throttler = InMemoryLoginThrottler()
    email = "test@example.com"

    # Intentos 1 y 2 no activan pausa
    att1, cd1 = await throttler.record_failed_attempt(email)
    assert att1 == 1
    assert cd1 is None
    assert await throttler.get_cooldown_remaining(email) is None

    att2, cd2 = await throttler.record_failed_attempt(email)
    assert att2 == 2
    assert cd2 is None

    # Intento 3 activa pausa de 60 segundos
    att3, cd3 = await throttler.record_failed_attempt(email)
    assert att3 == 3
    assert cd3 == 60
    remaining = await throttler.get_cooldown_remaining(email)
    assert remaining is not None
    assert 1 <= remaining <= 60

    # Limpiar resetea todo
    await throttler.clear(email)
    assert await throttler.get_cooldown_remaining(email) is None

    # Avanzar hasta 6 intentos
    for _ in range(5):
        await throttler.record_failed_attempt(email)
    att6, cd6 = await throttler.record_failed_attempt(email)
    assert att6 == 6
    assert cd6 == 300
    rem6 = await throttler.get_cooldown_remaining(email)
    assert rem6 is not None
    assert 250 <= rem6 <= 300


@pytest.mark.asyncio
async def test_auth_service_progressive_lockout() -> None:
    user = make_test_user(estado="ACTIVO", password="CorrectPassword123!")
    session = AsyncMock()
    repository = AsyncMock()
    repository.get_user_by_email.return_value = user
    throttler = InMemoryLoginThrottler()

    service = AuthService(session=session, repository=repository, throttler=throttler)
    audit = make_audit_context()
    login_payload = LoginRequest(correo=user.correo, password="WrongPassword")

    # Intentos 1 y 2: InvalidCredentialsError con aviso de intentos restantes
    with pytest.raises(InvalidCredentialsError) as exc_info1:
        await service.login(login_payload, audit)
    assert "Te quedan 2 intento(s) antes de una pausa de seguridad" in exc_info1.value.detail

    with pytest.raises(InvalidCredentialsError) as exc_info2:
        await service.login(login_payload, audit)
    assert "Te quedan 1 intento(s) antes de una pausa de seguridad" in exc_info2.value.detail

    # Intento 3: AccountTemporarilyLockedError con pausa de 60 segundos
    with pytest.raises(AccountTemporarilyLockedError) as exc_info3:
        await service.login(login_payload, audit)
    assert exc_info3.value.retry_after == 60
    assert "1 minuto" in exc_info3.value.message or "60 segundos" in exc_info3.value.message

    # Intento durante cooldown: se rechaza inmediatamente sin verificar credenciales
    with pytest.raises(AccountTemporarilyLockedError) as exc_info_cooldown:
        await service.login(login_payload, audit)
    assert exc_info_cooldown.value.retry_after <= 60

    # Simulamos que el tiempo de la primera pausa (1 min) expira
    throttler._cooldowns.clear()

    # Intentos 4 y 5: InvalidCredentialsError avisando pausa de 5 minutos
    with pytest.raises(InvalidCredentialsError) as exc_info4:
        await service.login(login_payload, audit)
    assert "Te quedan 2 intento(s) antes de una pausa de 5 minutos" in exc_info4.value.detail

    with pytest.raises(InvalidCredentialsError) as exc_info5:
        await service.login(login_payload, audit)
    assert "Te quedan 1 intento(s) antes de una pausa de 5 minutos" in exc_info5.value.detail

    # Intento 6: Pausa de 5 minutos (300s)
    with pytest.raises(AccountTemporarilyLockedError) as exc_info6:
        await service.login(login_payload, audit)
    assert exc_info6.value.retry_after == 300
    assert "5 minutos" in exc_info6.value.message

    # Simulamos que la segunda pausa (5 min) expira para probar intentos 7, 8 y 9
    throttler._cooldowns.clear()

    # Intento 7
    with pytest.raises(InvalidCredentialsError) as exc_info7:
        await service.login(login_payload, audit)
    assert "Te quedan 2 intento(s) antes del bloqueo definitivo" in exc_info7.value.detail

    # Intento 8
    with pytest.raises(InvalidCredentialsError) as exc_info8:
        await service.login(login_payload, audit)
    assert "Te quedan 1 intento(s) antes del bloqueo definitivo" in exc_info8.value.detail

    # Intento 9: Bloqueo definitivo de la cuenta en base de datos
    with pytest.raises(AccountPermanentlyBlockedError) as exc_info9:
        await service.login(login_payload, audit)
    assert "bloqueada" in exc_info9.value.message
    repository.update_user_status.assert_awaited_with(user, "BLOQUEADO")
    session.commit.assert_awaited()

    # Siguiente intento: Rechazado inmediatamente como bloqueado
    user.estado = "BLOQUEADO"
    with pytest.raises(AccountPermanentlyBlockedError):
        await service.login(login_payload, audit)


@pytest.mark.asyncio
async def test_auth_service_successful_login_clears_throttler() -> None:
    user = make_test_user(estado="ACTIVO", password="CorrectPassword123!")
    session = AsyncMock()
    repository = AsyncMock()
    repository.get_user_by_email.return_value = user
    throttler = InMemoryLoginThrottler()

    service = AuthService(session=session, repository=repository, throttler=throttler)
    audit = make_audit_context()

    # Fallar dos veces
    with pytest.raises(InvalidCredentialsError):
        await service.login(LoginRequest(correo=user.correo, password="WrongPassword"), audit)
    with pytest.raises(InvalidCredentialsError):
        await service.login(LoginRequest(correo=user.correo, password="WrongPassword"), audit)

    # Login exitoso con password correcto
    success = await service.login(
        LoginRequest(correo=user.correo, password="CorrectPassword123!"), audit
    )
    assert success.access_token is not None

    # Verificar que el throttler quedó completamente limpio
    assert await throttler.get_cooldown_remaining(user.correo) is None
    # Un nuevo fallo empezará desde intento 1
    att, _ = await throttler.record_failed_attempt(user.correo)
    assert att == 1


@pytest.mark.asyncio
async def test_http_endpoint_cooldown_and_lockout_responses() -> None:
    service = AsyncMock()
    service.login.side_effect = AccountTemporarilyLockedError(
        retry_after=60,
        message="Demasiados intentos fallidos. Por seguridad, tu cuenta está pausada por 1 minuto.",
    )

    async def override_service() -> AsyncIterator[AsyncMock]:
        yield service

    app.dependency_overrides[get_auth_service] = override_service
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/auth/login",
                json={"correo": "carlos@example.com", "password": "WrongPassword"},
            )
            assert resp.status_code == 429
            assert resp.headers.get("retry-after") == "60"
            data = resp.json()
            assert "1 minuto" in data["detail"]
            assert data["retry_after"] == 60

            # Probar respuesta de bloqueo permanente (403)
            service.login.side_effect = AccountPermanentlyBlockedError(
                "Tu cuenta ha sido bloqueada tras alcanzar 9 intentos fallidos. Debes recuperar tu contraseña para desbloquearla."
            )
            resp_blocked = await client.post(
                "/api/v1/auth/login",
                json={"correo": "carlos@example.com", "password": "WrongPassword"},
            )
            assert resp_blocked.status_code == 403
            assert "bloqueada" in resp_blocked.json()["detail"]
    finally:
        app.dependency_overrides.clear()
