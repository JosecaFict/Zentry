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


async def run_startup_migrations() -> None:
    """Run idempotent schema updates and constraint migrations on PostgreSQL."""
    try:
        import logging

        from sqlalchemy import text

        logger = logging.getLogger("capricho.migrations")
        async with engine.begin() as conn:
            for target_table in ["capricho.notificacion", "notificacion"]:
                try:
                    # 1. Primero eliminar la restricción restrictiva antigua
                    await conn.execute(
                        text(f"ALTER TABLE IF EXISTS {target_table} DROP CONSTRAINT IF EXISTS notificacion_estado_check;")
                    )
                    # 2. Añadir la restricción moderna que incluye LEIDO, ACTIVO, FALLIDO
                    await conn.execute(
                        text(
                            f"""
                            ALTER TABLE IF EXISTS {target_table} 
                            ADD CONSTRAINT notificacion_estado_check 
                            CHECK (estado IN ('PENDIENTE', 'ENVIANDO', 'ENVIADO', 'ENTREGADO', 'ERROR', 'LEIDO', 'ACTIVO', 'FALLIDO'));
                            """
                        )
                    )
                    logger.info("Restricción notificacion_estado_check actualizada para %s.", target_table)
                except Exception as inner_exc:
                    logger.warning("Aviso durante migración de %s: %s", target_table, inner_exc)

            for target_table in ["capricho.usuario", "usuario"]:
                try:
                    await conn.execute(
                        text(f"ALTER TABLE IF EXISTS {target_table} ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);")
                    )
                    logger.info("Columna avatar_url verificada/añadida en %s.", target_table)
                except Exception as inner_exc:
                    logger.warning("Aviso durante migración de avatar_url en %s: %s", target_table, inner_exc)
    except Exception as exc:
        import logging
        logging.getLogger("capricho.migrations").warning("No se pudo ejecutar la migración inicial: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release the connection pool when the application stops."""
    await run_startup_migrations()
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
