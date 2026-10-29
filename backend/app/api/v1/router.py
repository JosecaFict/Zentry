from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DatabaseUnavailableError
from app.db.session import check_database, get_db_session
from app.modules.analytics.router import router as analytics_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.commerce.router import router as commerce_router
from app.modules.customers.router import router as customers_router
from app.modules.employees.router import router as employee_router
from app.modules.inventory.router import router as inventory_router
from app.modules.platform.router import public_router, tenant_router
from app.modules.platform.router import router as platform_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.reports.router import router as reports_router
from app.modules.virtual_tryon.router import router as tryon_router

router = APIRouter()
system_router = APIRouter(tags=["system"])
router.include_router(auth_router)
router.include_router(employee_router)
router.include_router(customers_router)
router.include_router(catalog_router)
router.include_router(commerce_router)
router.include_router(inventory_router)
router.include_router(platform_router)
router.include_router(tenant_router)
router.include_router(public_router)
router.include_router(audit_router)
router.include_router(analytics_router)
router.include_router(recommendations_router)
router.include_router(reports_router)
router.include_router(tryon_router)


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: str
    environment: str


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["available"]


@system_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the FastAPI process is running."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        environment=settings.app_env,
    )


@system_router.get("/ready", response_model=ReadyResponse)
async def ready(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReadyResponse:
    """Report readiness after executing a real PostgreSQL query."""
    try:
        await check_database(session)
    except (SQLAlchemyError, OSError) as exc:
        raise DatabaseUnavailableError from exc

    return ReadyResponse(status="ready", database="available")


router.include_router(system_router)
