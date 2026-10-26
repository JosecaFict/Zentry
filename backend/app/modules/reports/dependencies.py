from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.modules.reports.ai import LocalReportInterpreter, OpenAIReportInterpreter
from app.modules.reports.service import ReportsService


def get_reports_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportsService:
    return ReportsService(session)


def get_ai_report_interpreter():
    settings = get_settings()
    if settings.openai_api_key:
        return OpenAIReportInterpreter(
            api_key=settings.openai_api_key,
            model=settings.openai_reports_model,
        )
    if settings.app_env in {"development", "test"}:
        return LocalReportInterpreter()
    return None
