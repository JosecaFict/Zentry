from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Empleado, Rol, RolPermiso, Sucursal, Usuario, UsuarioRol
from app.modules.catalog.models import Producto
from app.modules.platform.models import Plan, Subscription, SubscriptionPayment, Tenant
from app.modules.platform.schemas import TenantBrandUpdate, TenantCreate, TenantUpdate


class PlatformRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def overview(self) -> tuple[int, int, int, int, int, int, int]:
        tenants = await self.session.execute(
            select(
                func.count(Tenant.id_tenant),
                func.count(Tenant.id_tenant).filter(Tenant.estado == "ACTIVO"),
                func.count(Tenant.id_tenant).filter(Tenant.estado == "SUSPENDIDO"),
            )
        )
        total, active, suspended = tenants.one()
        branches = await self.session.scalar(
            select(func.count(Sucursal.id_sucursal))
            .where(Sucursal.activo.is_(True))
            .execution_options(include_all_tenants=True)
        )
        subscription_counts = (
            await self.session.execute(
                select(
                    func.count(Subscription.id_subscription).filter(
                        Subscription.estado == "POR_VENCER"
                    ),
                    func.count(Subscription.id_subscription).filter(
                        Subscription.estado == "GRACIA"
                    ),
                    func.count(Subscription.id_subscription).filter(
                        Subscription.estado == "SUSPENDIDA"
                    ),
                ).execution_options(include_all_tenants=True)
            )
        ).one()
        expiring, grace, subscription_suspended = subscription_counts
        return (
            int(total),
            int(active),
            int(suspended),
            int(branches or 0),
            int(expiring or 0),
            int(grace or 0),
            int(subscription_suspended or 0),
        )

    async def list_plans(self) -> list[Plan]:
        return list((await self.session.scalars(select(Plan).order_by(Plan.id_plan))).all())

    async def get_active_plan(self, plan_id: int) -> Plan | None:
        return await self.session.scalar(
            select(Plan).where(Plan.id_plan == plan_id, Plan.activo.is_(True))
        )

    async def get_tenant(self, tenant_id: int) -> Tenant | None:
        return await self.session.get(Tenant, tenant_id)

    async def tenant_identity_exists(self, slug: str, nit: str | None) -> bool:
        conditions = [Tenant.slug == slug]
        if nit:
            conditions.append(Tenant.nit == nit)
        statement = select(Tenant.id_tenant).where(or_(*conditions))
        return await self.session.scalar(statement) is not None

    async def tenant_nit_exists(self, tenant_id: int, nit: str | None) -> bool:
        if not nit:
            return False
        return (
            await self.session.scalar(
                select(Tenant.id_tenant).where(
                    Tenant.nit == nit,
                    Tenant.id_tenant != tenant_id,
                )
            )
            is not None
        )

    async def user_identity_exists(self, correo: str, ci: str | None) -> bool:
        conditions = [func.lower(Usuario.correo) == correo]
        if ci:
            conditions.append(Usuario.ci == ci)
        statement = select(Usuario.id_usuario).where(or_(*conditions))
        return (
            await self.session.scalar(statement.execution_options(include_all_tenants=True))
            is not None
        )

    async def provision_tenant(
        self,
        payload: TenantCreate,
        *,
        email: str,
        password_hash: str,
    ) -> int:
        plan = await self.get_active_plan(payload.id_plan)
        if plan is None:
            raise LookupError("PLAN_NOT_FOUND")

        template_role = await self.session.scalar(
            select(Rol)
            .where(Rol.nombre == "ADMIN", Rol.alcance == "TENANT")
            .order_by(Rol.id_rol)
            .execution_options(include_all_tenants=True)
        )
        if template_role is None:
            raise LookupError("ADMIN_ROLE_NOT_FOUND")
        permission_ids = list(
            (
                await self.session.scalars(
                    select(RolPermiso.id_permiso).where(RolPermiso.id_rol == template_role.id_rol)
                )
            ).all()
        )

        tenant = Tenant(
            nombre=payload.nombre,
            slug=payload.slug,
            razon_social=payload.razon_social,
            nit=payload.nit,
            correo_contacto=str(payload.correo_contacto) if payload.correo_contacto else None,
            telefono_contacto=payload.telefono_contacto,
            logo_url=payload.logo_url,
            color_primario=payload.color_primario.upper(),
            color_primario_oscuro=payload.color_primario_oscuro.upper(),
            estado="ACTIVO",
        )
        self.session.add(tenant)
        await self.session.flush()

        self.session.add(
            Subscription(
                id_tenant=tenant.id_tenant,
                id_plan=plan.id_plan,
                estado="SUSPENDIDA",
                modalidad=payload.modalidad,
                precio_acordado=(
                    plan.precio_mensual if payload.modalidad == "MENSUAL" else plan.precio_anual
                ),
                fecha_inicio=date.today(),
                fecha_fin=payload.fecha_fin,
            )
        )
        admin_role = Rol(
            id_tenant=tenant.id_tenant,
            alcance="TENANT",
            nombre="ADMIN",
            descripcion="Administrador principal de la empresa",
            activo=True,
        )
        self.session.add(admin_role)
        await self.session.flush()
        self.session.add_all(
            [RolPermiso(id_rol=admin_role.id_rol, id_permiso=value) for value in permission_ids]
        )

        admin = payload.administrador
        user = Usuario(
            id_tenant=tenant.id_tenant,
            nombres=admin.nombres.strip(),
            apellidos=admin.apellidos.strip(),
            correo=email,
            telefono=admin.telefono.strip() if admin.telefono else None,
            ci=admin.ci.strip() if admin.ci else None,
            password_hash=password_hash,
            estado="ACTIVO",
        )
        self.session.add(user)
        await self.session.flush()
        self.session.add(UsuarioRol(id_usuario=user.id_usuario, id_rol=admin_role.id_rol))
        await self.session.flush()
        return tenant.id_tenant

    async def update_tenant(self, tenant_id: int, payload: TenantUpdate) -> bool:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            return False
        plan = await self.get_active_plan(payload.id_plan)
        if plan is None:
            raise LookupError("PLAN_NOT_FOUND")
        subscription_row = await self.get_subscription(tenant_id)
        if subscription_row is None:
            raise LookupError("SUBSCRIPTION_NOT_FOUND")
        subscription, _ = subscription_row
        tenant.nombre = payload.nombre
        tenant.razon_social = payload.razon_social
        tenant.nit = payload.nit
        tenant.correo_contacto = str(payload.correo_contacto) if payload.correo_contacto else None
        tenant.telefono_contacto = payload.telefono_contacto
        tenant.logo_url = payload.logo_url
        tenant.color_primario = payload.color_primario.upper()
        tenant.color_primario_oscuro = payload.color_primario_oscuro.upper()
        subscription.id_plan = plan.id_plan
        subscription.modalidad = payload.modalidad
        subscription.precio_acordado = (
            plan.precio_mensual if payload.modalidad == "MENSUAL" else plan.precio_anual
        )
        subscription.fecha_fin = payload.fecha_fin
        await self.session.flush()
        return True

    async def update_tenant_status(self, tenant_id: int, tenant_status: str) -> bool:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            return False
        tenant.estado = tenant_status
        await self.session.flush()
        return True

    async def update_tenant_brand(self, tenant_id: int, payload: TenantBrandUpdate) -> bool:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            return False
        tenant.nombre = payload.nombre
        tenant.logo_url = payload.logo_url
        tenant.color_primario = payload.color_primario.upper()
        tenant.color_primario_oscuro = payload.color_primario_oscuro.upper()
        await self.session.flush()
        return True

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def list_tenants(self) -> list[tuple]:
        branch_count = (
            select(Sucursal.id_tenant, func.count().label("branches"))
            .where(Sucursal.activo.is_(True))
            .group_by(Sucursal.id_tenant)
            .execution_options(include_all_tenants=True)
            .subquery()
        )
        statement = (
            select(Tenant, Subscription, Plan, func.coalesce(branch_count.c.branches, 0))
            .outerjoin(
                Subscription,
                (Subscription.id_tenant == Tenant.id_tenant)
                & Subscription.estado.in_(("ACTIVA", "POR_VENCER", "GRACIA", "SUSPENDIDA")),
            )
            .outerjoin(Plan, Plan.id_plan == Subscription.id_plan)
            .outerjoin(branch_count, branch_count.c.id_tenant == Tenant.id_tenant)
            .order_by(Tenant.nombre)
            .execution_options(include_all_tenants=True)
        )
        return list((await self.session.execute(statement)).all())

    async def search_public_tenants(self, query: str, limit: int = 20) -> list[Tenant]:
        pattern = f"%{query.strip()}%"
        statement = (
            select(Tenant)
            .where(
                Tenant.estado == "ACTIVO",
                Tenant.nombre.ilike(pattern) | Tenant.slug.ilike(pattern),
            )
            .order_by(Tenant.nombre)
            .limit(limit)
            .execution_options(include_all_tenants=True)
        )
        return list((await self.session.scalars(statement)).all())

    async def tenant_detail(self, tenant_id: int) -> tuple | None:
        rows = [row for row in await self.list_tenants() if row[0].id_tenant == tenant_id]
        if not rows:
            return None
        users = await self.session.scalar(
            select(func.count(Usuario.id_usuario))
            .where(Usuario.id_tenant == tenant_id)
            .execution_options(include_all_tenants=True)
        )
        admins = await self.session.scalar(
            select(func.count(func.distinct(Usuario.id_usuario)))
            .join(UsuarioRol, UsuarioRol.id_usuario == Usuario.id_usuario)
            .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
            .where(Usuario.id_tenant == tenant_id, Rol.nombre == "ADMIN")
            .execution_options(include_all_tenants=True)
        )
        internal_users = await self.session.scalar(
            select(func.count(Empleado.id_empleado))
            .where(Empleado.id_tenant == tenant_id, Empleado.estado_laboral == "ACTIVO")
            .execution_options(include_all_tenants=True)
        )
        products = await self.session.scalar(
            select(func.count(Producto.id_producto))
            .where(Producto.id_tenant == tenant_id, Producto.activo.is_(True))
            .execution_options(include_all_tenants=True)
        )
        return (
            *rows[0],
            int(users or 0),
            int(admins or 0),
            int(internal_users or 0),
            int(products or 0),
        )

    async def get_subscription(self, tenant_id: int) -> tuple[Subscription, Plan] | None:
        statement = (
            select(Subscription, Plan)
            .join(Plan, Plan.id_plan == Subscription.id_plan)
            .where(
                Subscription.id_tenant == tenant_id,
                Subscription.estado.in_(("ACTIVA", "POR_VENCER", "GRACIA", "SUSPENDIDA")),
            )
            .execution_options(include_all_tenants=True)
        )
        return (await self.session.execute(statement)).one_or_none()

    async def add_payment(self, payment: SubscriptionPayment) -> None:
        self.session.add(payment)
        await self.session.flush()

    async def list_payments(self, tenant_id: int) -> list[SubscriptionPayment]:
        statement = (
            select(SubscriptionPayment)
            .join(Subscription, Subscription.id_subscription == SubscriptionPayment.id_subscription)
            .where(Subscription.id_tenant == tenant_id)
            .order_by(SubscriptionPayment.fecha_pago.desc(), SubscriptionPayment.id_payment.desc())
            .execution_options(include_all_tenants=True)
        )
        return list((await self.session.scalars(statement)).all())
