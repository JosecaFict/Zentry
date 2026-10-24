from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.reports.service import ReportsService


def get_reports_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportsService:
    return ReportsService(session)
