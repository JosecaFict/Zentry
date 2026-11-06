import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import engine
from app.middleware.tenant import TenantPathMiddleware
from app.modules.auth.handlers import register_auth_exception_handlers
from app.modules.catalog.handlers import register_catalog_exception_handlers
from app.modules.commerce.handlers import register_commerce_exception_handlers
from app.modules.employees.handlers import register_employee_exception_handlers
from app.modules.inventory.handlers import register_inventory_exception_handlers
from app.modules.platform.subscription_lifecycle import (
    stop_subscription_worker,
    subscription_lifecycle_worker,
)
from app.modules.recommendations.handlers import register_recommendation_exception_handlers


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release the connection pool when the application stops."""
    subscription_task = asyncio.create_task(subscription_lifecycle_worker())
    try:
        yield
    finally:
        await stop_subscription_worker(subscription_task)
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.debug)

    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    application.add_middleware(TenantPathMiddleware)
    application.include_router(api_v1_router, prefix="/api/v1")
    register_exception_handlers(application)
    register_auth_exception_handlers(application)
    register_employee_exception_handlers(application)
    register_catalog_exception_handlers(application)
    register_commerce_exception_handlers(application)
    register_inventory_exception_handlers(application)
    register_recommendation_exception_handlers(application)
    return application


app = create_app()
