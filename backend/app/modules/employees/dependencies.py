from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.employees.repository import EmployeeRepository
from app.modules.employees.service import EmployeeService


async def get_employee_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AsyncIterator[EmployeeService]:
    yield EmployeeService(session=session, repository=EmployeeRepository(session))
