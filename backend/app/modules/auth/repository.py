from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant_context import current_tenant_id
from app.modules.auth.exceptions import InactiveUserError
from app.modules.auth.models import (
    Cliente,
    Empleado,
    Permiso,
    Rol,
    RolPermiso,
    Sucursal,
    Usuario,
    UsuarioPermiso,
    UsuarioRol,
)
from app.modules.platform.models import Plan, Subscription, Tenant


@dataclass(frozen=True, slots=True)
class TenantAccess:
    id_tenant: int
    slug: str
    tenant_estado: str
    subscription_estado: str | None
    plan_codigo: str | None
    max_sucursales_activas: int | None
    max_usuarios_internos: int | None
    max_productos_activos: int | None
    permite_reportes_ia: bool
    permite_offline: bool


def resolve_effective_permissions(
    role_permissions: set[str],
    individual_overrides: Mapping[str, bool],
) -> set[str]:
    granted = {code for code, is_granted in individual_overrides.items() if is_granted}
    revoked = {code for code, is_granted in individual_overrides.items() if not is_granted}
    return (role_permissions | granted) - revoked


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> Usuario | None:
        tenant_id = current_tenant_id()
        tenant_filter = (
            Usuario.id_tenant == tenant_id if tenant_id is not None else Usuario.id_tenant.is_(None)
        )
        statement = (
            select(Usuario)
            .where(func.lower(func.btrim(Usuario.correo)) == email, tenant_filter)
            .execution_options(include_all_tenants=True)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_user_by_ci(self, ci: str) -> Usuario | None:
        tenant_id = current_tenant_id()
        tenant_filter = (
            Usuario.id_tenant == tenant_id if tenant_id is not None else Usuario.id_tenant.is_(None)
        )
        statement = (
            select(Usuario)
            .where(Usuario.ci == ci.strip(), tenant_filter)
            .execution_options(include_all_tenants=True)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Usuario | None:
        statement = (
            select(Usuario)
            .where(Usuario.id_usuario == user_id)
            .execution_options(include_all_tenants=True)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_tenant_access(self, tenant_id: int) -> TenantAccess | None:
        statement = (
            select(Tenant, Subscription, Plan)
            .outerjoin(
                Subscription,
                (Subscription.id_tenant == Tenant.id_tenant)
                & (Subscription.estado.in_(("ACTIVA", "POR_VENCER", "GRACIA")))
                & (Subscription.fecha_inicio <= func.current_date())
                & (
                    (Subscription.fecha_fin.is_(None))
                    | (Subscription.fecha_fin >= func.current_date())
                ),
            )
            .outerjoin(Plan, Plan.id_plan == Subscription.id_plan)
            .where(Tenant.id_tenant == tenant_id)
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        tenant, subscription, plan = row
        return TenantAccess(
            id_tenant=tenant.id_tenant,
            slug=tenant.slug,
            tenant_estado=tenant.estado,
            subscription_estado=subscription.estado if subscription else None,
            plan_codigo=plan.codigo if plan else None,
            max_sucursales_activas=plan.max_sucursales_activas if plan else None,
            max_usuarios_internos=plan.max_usuarios_internos if plan else None,
            max_productos_activos=plan.max_productos_activos if plan else None,
            permite_reportes_ia=bool(plan and plan.permite_reportes_ia),
            permite_offline=bool(plan and plan.permite_offline),
        )

    async def get_employee_branch(self, user_id: int) -> tuple[int, str] | None:
        statement = (
            select(Empleado.id_sucursal, Sucursal.nombre)
            .join(Sucursal, Sucursal.id_sucursal == Empleado.id_sucursal)
            .where(Empleado.id_usuario == user_id)
        )
        row = (await self.session.execute(statement)).one_or_none()
        return (int(row[0]), str(row[1])) if row else None

    async def get_active_role_by_name(self, name: str) -> Rol | None:
        statement = select(Rol).where(Rol.nombre == name, Rol.activo.is_(True))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def create_customer_user(
        self,
        *,
        user: Usuario,
        client_role: Rol,
    ) -> Usuario:
        self.session.add(user)
        await self.session.flush()
        self.session.add_all(
            [
                Cliente(id_usuario=user.id_usuario),
                UsuarioRol(id_usuario=user.id_usuario, id_rol=client_role.id_rol),
            ]
        )
        await self.session.flush()
        return user

    async def update_last_access(self, user: Usuario) -> None:
        self.session.add(user)
        await self.session.flush()

    async def update_password(self, user: Usuario, password_hash: str) -> None:
        user.password_hash = password_hash
        self.session.add(user)
        await self.session.flush()

    async def update_user_status(self, user: Usuario, estado: str) -> None:
        user.estado = estado
        self.session.add(user)
        await self.session.flush()

    async def get_role_names(self, user_id: int) -> set[str]:
        statement = (
            select(Rol.nombre)
            .join(UsuarioRol, UsuarioRol.id_rol == Rol.id_rol)
            .where(UsuarioRol.id_usuario == user_id, Rol.activo.is_(True))
            .execution_options(include_all_tenants=True)
        )
        return set((await self.session.scalars(statement)).all())

    async def get_role_permission_codes(self, user_id: int) -> set[str]:
        statement = (
            select(Permiso.codigo)
            .join(RolPermiso, RolPermiso.id_permiso == Permiso.id_permiso)
            .join(Rol, Rol.id_rol == RolPermiso.id_rol)
            .join(UsuarioRol, UsuarioRol.id_rol == Rol.id_rol)
            .where(
                UsuarioRol.id_usuario == user_id,
                Rol.activo.is_(True),
                Permiso.activo.is_(True),
            )
            .execution_options(include_all_tenants=True)
        )
        return set((await self.session.scalars(statement)).all())

    async def get_user_permission_overrides(self, user_id: int) -> dict[str, bool]:
        statement = (
            select(Permiso.codigo, UsuarioPermiso.otorgado)
            .join(UsuarioPermiso, UsuarioPermiso.id_permiso == Permiso.id_permiso)
            .where(
                UsuarioPermiso.id_usuario == user_id,
                Permiso.activo.is_(True),
            )
            .execution_options(include_all_tenants=True)
        )
        rows: Sequence[tuple[str, bool]] = (await self.session.execute(statement)).all()
        return dict(rows)

    async def get_effective_permissions(self, user_id: int) -> set[str]:
        role_permissions = await self.get_role_permission_codes(user_id)
        overrides = await self.get_user_permission_overrides(user_id)
        return resolve_effective_permissions(role_permissions, overrides)

    async def update_profile(
        self,
        user_id: int,
        *,
        nombres: str,
        apellidos: str,
        telefono: str | None,
        ci: str | None,
    ) -> Usuario:
        user = await self.session.get(Usuario, user_id)
        if user is None:
            raise InactiveUserError("User not found")
        user.nombres = nombres
        user.apellidos = apellidos
        user.telefono = telefono
        user.ci = ci
        self.session.add(user)
        await self.session.flush()
        return user
