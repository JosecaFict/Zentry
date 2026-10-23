from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.service import PlatformService


async def get_platform_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[PlatformService]:
    yield PlatformService(PlatformRepository(session))
