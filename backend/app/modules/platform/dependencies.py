from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.db.tenant_context import reset_database_scope, set_database_scope
from app.integrations.cloudinary import CloudinaryError, CloudinaryStorage
from app.modules.auth.dependencies import CurrentPrincipal, get_current_principal
from app.modules.auth.exceptions import PermissionDeniedError
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.service import PlatformService


async def get_platform_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[PlatformService]:
    yield PlatformService(PlatformRepository(session))


async def require_platform_database_scope(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[None]:
    """Elevate RLS only after authenticating a global SUPERADMIN.

    The middleware deliberately starts platform requests with ``identity`` scope,
    which is sufficient to authenticate a global account but cannot read tenant
    business data.  This dependency performs the audited privilege boundary for
    the platform router and keeps the elevation active across transaction
    restarts made by the service.
    """
    if principal.id_tenant is not None or "SUPERADMIN" not in principal.roles:
        raise PermissionDeniedError

    scope_token = set_database_scope("global")
    try:
        await session.execute(text("SELECT set_config('app.rls_scope', 'global', true)"))
        yield
    finally:
        reset_database_scope(scope_token)


def get_platform_cloudinary_storage() -> CloudinaryStorage:
    settings = get_settings()
    if not settings.cloudinary_url:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary no está configurado",
        )
    try:
        return CloudinaryStorage(settings.cloudinary_url)
    except CloudinaryError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
