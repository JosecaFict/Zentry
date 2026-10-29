from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.commerce.dependencies import get_commerce_service
from app.modules.commerce.service import CommerceService
from app.modules.sync.repository import SyncRepository
from app.modules.sync.service import SyncService


async def get_sync_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    commerce: Annotated[CommerceService, Depends(get_commerce_service)],
) -> AsyncIterator[SyncService]:
    yield SyncService(session, SyncRepository(session), commerce)

