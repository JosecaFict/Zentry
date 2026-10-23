from contextvars import ContextVar, Token

from sqlalchemy import event, func
from sqlalchemy.orm import Session, with_loader_criteria

from app.db.base import Base

_tenant_id: ContextVar[int | None] = ContextVar("tenant_id", default=None)


def current_tenant_id() -> int | None:
    return _tenant_id.get()


def set_tenant_context(tenant_id: int) -> Token:
    return _tenant_id.set(tenant_id)


def clear_tenant_context() -> None:
    _tenant_id.set(None)


@event.listens_for(Session, "do_orm_execute")
def add_tenant_filter(execute_state) -> None:
    tenant_id = current_tenant_id()
    if not execute_state.is_select or execute_state.execution_options.get(
        "include_all_tenants"
    ):
        return

    statement = execute_state.statement
    for mapper in tuple(Base.registry.mappers):
        entity = mapper.class_
        tenant_column = getattr(entity, "id_tenant", None)
        if tenant_column is None or entity.__tablename__ in {"tenant", "subscription"}:
            continue
        tenant_value = (
            tenant_id
            if tenant_id is not None
            else func.capricho.fn_tenant_actual()
        )
        statement = statement.options(
            with_loader_criteria(
                entity,
                tenant_column == tenant_value,
                include_aliases=True,
            )
        )
    execute_state.statement = statement
