from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.modules.reports.ai import GroqReportInterpreter, LocalReportInterpreter
from app.modules.reports.service import ReportsService
from app.modules.reports.speech import GroqSpeechTranscriber


def get_reports_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReportsService:
    return ReportsService(session)


def get_ai_report_interpreter():
    settings = get_settings()
    if settings.groq_api_key:
        return GroqReportInterpreter(
            api_key=settings.groq_api_key,
            model=settings.groq_reports_model,
        )
    if settings.app_env in {"development", "test"}:
        return LocalReportInterpreter()
    return None


def get_speech_transcriber():
    settings = get_settings()
    if not settings.groq_api_key:
        return None
    return GroqSpeechTranscriber(
        api_key=settings.groq_api_key,
        model=settings.groq_speech_model,
    )
