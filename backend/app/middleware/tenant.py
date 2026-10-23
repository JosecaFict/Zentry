import re
from dataclasses import dataclass

from fastapi import status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.types import ASGIApp, Receive, Scope, Send

from app.db.session import async_session_factory
from app.db.tenant_context import clear_tenant_context, set_tenant_context
from app.modules.platform.models import Tenant

TENANT_PATH = re.compile(r"^/api/v1/t/(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)(?P<rest>/.*|$)")
TENANT_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GLOBAL_PREFIXES = ("/api/v1/platform",)


@dataclass(frozen=True, slots=True)
class ResolvedTenant:
    id_tenant: int
    slug: str
    estado: str


async def resolve_tenant_slug(slug: str) -> ResolvedTenant | None:
    async with async_session_factory() as session:
        statement = (
            select(Tenant).where(Tenant.slug == slug).execution_options(include_all_tenants=True)
        )
        tenant = (await session.execute(statement)).scalar_one_or_none()
        if tenant is None:
            return None
        return ResolvedTenant(
            id_tenant=tenant.id_tenant,
            slug=tenant.slug,
            estado=tenant.estado,
        )


class TenantPathMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        clear_tenant_context()
        match = TENANT_PATH.match(scope["path"])
        header_slug = self._header_slug(scope)
        slug = match.group("slug") if match is not None else header_slug
        if slug is None or (match is None and scope["path"].startswith(GLOBAL_PREFIXES)):
            try:
                await self.app(scope, receive, send)
                return
            finally:
                clear_tenant_context()

        tenant = await resolve_tenant_slug(slug)
        if tenant is None:
            response = JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Empresa no encontrada"},
            )
            await response(scope, receive, send)
            return
        if tenant.estado != "ACTIVO":
            response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Empresa suspendida"},
            )
            await response(scope, receive, send)
            return

        set_tenant_context(tenant.id_tenant)
        tenant_scope = dict(scope)
        tenant_scope["state"] = dict(scope.get("state", {}))
        tenant_scope["state"]["tenant_id"] = tenant.id_tenant
        tenant_scope["state"]["tenant_slug"] = tenant.slug
        if match is not None:
            rewritten_path = f"/api/v1{match.group('rest') or '/'}"
            tenant_scope["path"] = rewritten_path
            tenant_scope["raw_path"] = rewritten_path.encode("utf-8")
        try:
            await self.app(tenant_scope, receive, send)
        finally:
            clear_tenant_context()

    @staticmethod
    def _header_slug(scope: Scope) -> str | None:
        headers = dict(scope.get("headers", []))
        raw_slug = headers.get(b"x-tenant-slug")
        if raw_slug is None:
            return None
        try:
            slug = raw_slug.decode("ascii").strip().lower()
        except UnicodeDecodeError:
            return None
        return slug if TENANT_SLUG.fullmatch(slug) else None
