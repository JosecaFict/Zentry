import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(RuntimeError):
    """Raised when PostgreSQL cannot serve a readiness query."""


async def database_unavailable_handler(
    request: Request,
    exc: DatabaseUnavailableError,
) -> JSONResponse:
    logger.error(
        "Database readiness check failed",
        extra={"path": request.url.path},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database unavailable"},
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled error on %s: %s",
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Ocurrió un error interno. Intenta nuevamente en unos minutos."},
    )


async def database_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    if getattr(exc.orig, "sqlstate", None) == "PZ001":
        message = getattr(exc.orig.__cause__, "message", None)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": message or "Se alcanzó el límite de recursos del plan."},
        )
    return await unhandled_exception_handler(request, exc)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)
    app.add_exception_handler(DBAPIError, database_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
