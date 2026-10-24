from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.integrations.cloudinary import CloudinaryError, CloudinaryStorage
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.service import PlatformService


async def get_platform_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[PlatformService]:
    yield PlatformService(PlatformRepository(session))


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
