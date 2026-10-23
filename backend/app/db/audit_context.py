from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class AuditContext:
    tenant_id: int | None = None
    usuario_id: int | None = None
    sesion_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    origen: Literal["WEB", "MOVIL", "API", "SISTEMA"] = "API"
    request_id: str | None = None


async def apply_audit_context(session: AsyncSession, context: AuditContext) -> None:
    """Set transaction-local values consumed by PostgreSQL audit triggers."""
    values = {
        "app.usuario_id": str(context.usuario_id) if context.usuario_id is not None else "",
        "app.sesion_id": context.sesion_id or "",
        "app.ip": context.ip or "",
        "app.user_agent": context.user_agent or "",
        "app.origen": context.origen,
        "app.request_id": context.request_id or "",
    }
    if context.tenant_id is not None:
        values["app.tenant_id"] = str(context.tenant_id)
    statement = text("SELECT set_config(:setting_name, :setting_value, true)")
    for setting_name, setting_value in values.items():
        await session.execute(
            statement,
            {"setting_name": setting_name, "setting_value": setting_value},
        )

