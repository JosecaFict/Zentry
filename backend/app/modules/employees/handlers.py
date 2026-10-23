from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.employees.exceptions import (
    InvalidEmployeeDataError,
    ResourceConflictError,
    ResourceNotFoundError,
)


async def resource_not_found_handler(
    _: Request,
    exc: ResourceNotFoundError,
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.detail})


async def resource_conflict_handler(
    _: Request,
    exc: ResourceConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.detail})


async def invalid_employee_data_handler(
    _: Request,
    exc: InvalidEmployeeDataError,
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.detail})


def register_employee_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
    app.add_exception_handler(ResourceConflictError, resource_conflict_handler)
    app.add_exception_handler(InvalidEmployeeDataError, invalid_employee_data_handler)
