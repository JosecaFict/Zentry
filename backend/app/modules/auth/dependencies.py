from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import get_db_session
from app.db.tenant_context import set_tenant_context
from app.modules.auth.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    PermissionDeniedError,
)
from app.modules.auth.models import Usuario
from app.modules.auth.password_recovery import BrevoEmailClient, RedisPasswordResetStore
from app.modules.auth.password_recovery_service import PasswordRecoveryService
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthService
from app.modules.auth.throttler import InMemoryLoginThrottler, RedisLoginThrottler

bearer_scheme = HTTPBearer(auto_error=False)
_local_login_throttler = InMemoryLoginThrottler()


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    user: Usuario
    roles: frozenset[str]
    permissions: frozenset[str]
    session_id: str
    id_sucursal: int | None = None
    sucursal: str | None = None
    id_tenant: int | None = None
    tenant_slug: str | None = None
    plan_codigo: str | None = None
    max_sucursales_activas: int | None = None
    max_usuarios_internos: int | None = None
    max_productos_activos: int | None = None
    permite_reportes_ia: bool = False
    permite_offline: bool = False


def build_request_audit_context(
    request: Request,
    *,
    user_id: int | None = None,
    session_id: str | None = None,
    tenant_id: int | None = None,
) -> AuditContext:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip = forwarded_for.split(",", maxsplit=1)[0].strip() if forwarded_for else None
    if ip is None and request.client is not None:
        ip = request.client.host

    return AuditContext(
        tenant_id=tenant_id,
        usuario_id=user_id,
        sesion_id=session_id or request.headers.get("x-session-id") or str(uuid4()),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        origen="API",
        request_id=request.headers.get("x-request-id") or str(uuid4()),
    )


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[AuthService]:
    settings = get_settings()
    redis_client = None
    throttler = None
    if settings.redis_url:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        throttler = RedisLoginThrottler(redis_client)
    elif settings.app_env in {"development", "test"}:
        throttler = _local_login_throttler
    try:
        yield AuthService(
            session=session,
            repository=AuthRepository(session),
            throttler=throttler,
        )
    finally:
        if redis_client is not None:
            await redis_client.aclose()


async def get_password_recovery_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[PasswordRecoveryService]:
    settings = get_settings()
    if not settings.redis_url:
        from app.modules.auth.exceptions import SecurityConfigurationError

        raise SecurityConfigurationError("REDIS_URL is missing")
    if not settings.brevo_api_key or not settings.brevo_sender_email:
        from app.modules.auth.exceptions import SecurityConfigurationError

        raise SecurityConfigurationError("Brevo configuration is missing")

    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield PasswordRecoveryService(
            session=session,
            repository=AuthRepository(session),
            store=RedisPasswordResetStore(redis_client),
            email_client=BrevoEmailClient(
                api_key=settings.brevo_api_key,
                sender_email=settings.brevo_sender_email,
                sender_name=settings.brevo_sender_name,
            ),
            settings=settings,
            throttler=RedisLoginThrottler(redis_client),
        )
    finally:
        await redis_client.aclose()


async def get_current_principal(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentPrincipal:
    raw_token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials
    elif "token" in request.query_params:
        raw_token = request.query_params["token"]

    if not raw_token:
        raise InvalidCredentialsError

    try:
        claims = decode_access_token(raw_token)
    except ValueError as exc:
        raise InvalidCredentialsError from exc

    repository = AuthRepository(session)
    user = await repository.get_user_by_id(claims.user_id)
    if user is None:
        raise InvalidCredentialsError
    if user.estado != "ACTIVO":
        raise InactiveUserError(user.estado)

    tenant_access = None
    if user.id_tenant is not None:
        tenant_access = await repository.get_tenant_access(user.id_tenant)
        if tenant_access is None or tenant_access.tenant_estado != "ACTIVO":
            raise InactiveUserError("TENANT_SUSPENDIDO")
        if (
            tenant_access.subscription_estado not in {"ACTIVA", "POR_VENCER", "GRACIA"}
            or tenant_access.plan_codigo is None
        ):
            raise InactiveUserError("SUSCRIPCION_NO_VIGENTE")
        requested_slug = getattr(request.state, "tenant_slug", None)
        if requested_slug != tenant_access.slug:
            raise PermissionDeniedError
        set_tenant_context(user.id_tenant)

    roles = await repository.get_role_names(user.id_usuario)
    permissions = await repository.get_effective_permissions(user.id_usuario)
    employee_branch = (
        await repository.get_employee_branch(user.id_usuario)
        if user.id_tenant is not None
        else None
    )
    await apply_audit_context(
        session,
        build_request_audit_context(
            request,
            user_id=user.id_usuario,
            session_id=claims.session_id,
            tenant_id=user.id_tenant,
        ),
    )
    return CurrentPrincipal(
        user=user,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        session_id=claims.session_id,
        id_sucursal=employee_branch[0] if employee_branch else None,
        sucursal=employee_branch[1] if employee_branch else None,
        id_tenant=user.id_tenant,
        tenant_slug=tenant_access.slug if tenant_access else None,
        plan_codigo=tenant_access.plan_codigo if tenant_access else None,
        max_sucursales_activas=tenant_access.max_sucursales_activas if tenant_access else None,
        max_usuarios_internos=tenant_access.max_usuarios_internos if tenant_access else None,
        max_productos_activos=tenant_access.max_productos_activos if tenant_access else None,
        permite_reportes_ia=tenant_access.permite_reportes_ia if tenant_access else False,
        permite_offline=tenant_access.permite_offline if tenant_access else False,
    )


async def get_optional_principal(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentPrincipal | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError:
        return None

    repository = AuthRepository(session)
    user = await repository.get_user_by_id(claims.user_id)
    if user is None or user.estado != "ACTIVO":
        return None

    tenant_access = None
    if user.id_tenant is not None:
        tenant_access = await repository.get_tenant_access(user.id_tenant)
        if (
            tenant_access is None
            or tenant_access.tenant_estado != "ACTIVO"
            or tenant_access.subscription_estado not in {"ACTIVA", "POR_VENCER", "GRACIA"}
            or tenant_access.plan_codigo is None
        ):
            return None
        requested_slug = getattr(request.state, "tenant_slug", None)
        if requested_slug != tenant_access.slug:
            return None
        set_tenant_context(user.id_tenant)

    roles = await repository.get_role_names(user.id_usuario)
    permissions = await repository.get_effective_permissions(user.id_usuario)
    employee_branch = (
        await repository.get_employee_branch(user.id_usuario)
        if user.id_tenant is not None
        else None
    )
    await apply_audit_context(
        session,
        build_request_audit_context(
            request,
            user_id=user.id_usuario,
            session_id=claims.session_id,
            tenant_id=user.id_tenant,
        ),
    )
    return CurrentPrincipal(
        user=user,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        session_id=claims.session_id,
        id_sucursal=employee_branch[0] if employee_branch else None,
        sucursal=employee_branch[1] if employee_branch else None,
        id_tenant=user.id_tenant,
        tenant_slug=tenant_access.slug if tenant_access else None,
        plan_codigo=tenant_access.plan_codigo if tenant_access else None,
        max_sucursales_activas=tenant_access.max_sucursales_activas if tenant_access else None,
        max_usuarios_internos=tenant_access.max_usuarios_internos if tenant_access else None,
        max_productos_activos=tenant_access.max_productos_activos if tenant_access else None,
        permite_reportes_ia=tenant_access.permite_reportes_ia if tenant_access else False,
        permite_offline=tenant_access.permite_offline if tenant_access else False,
    )


PermissionDependency = Callable[
    [CurrentPrincipal],
    Coroutine[Any, Any, CurrentPrincipal],
]


def require_permission(permission_code: str) -> PermissionDependency:
    async def dependency(
        principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    ) -> CurrentPrincipal:
        if permission_code not in principal.permissions:
            raise PermissionDeniedError
        return principal

    return dependency


def require_global_permission(permission_code: str) -> PermissionDependency:
    async def dependency(
        request: Request,
        principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    ) -> CurrentPrincipal:
        if (
            getattr(request.state, "tenant_id", None) is not None
            or principal.id_tenant is not None
            or "SUPERADMIN" not in principal.roles
            or permission_code not in principal.permissions
        ):
            raise PermissionDeniedError
        return principal

    return dependency
