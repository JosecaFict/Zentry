"""Provision two independent Empresarial demos. Run from the backend directory."""

import asyncio
from datetime import date, time, timedelta
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.core.security import hash_password
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.db.tenant_context import database_scope
from app.modules.auth.models import Ciudad, Sucursal
from app.modules.platform.models import Plan, Subscription, Tenant
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.schemas import TenantAdminCreate, TenantCreate
from app.scripts.seed_demo_tenants import DemoTenant, SeedError, add_one_month

DEMOS = (
    (
        DemoTenant(
            "Línea Urbana", "linea-urbana", "EMPRESARIAL", "Andrea", "Rojas", "#0F766E", "#115E59"
        ),
        12,
    ),
    (
        DemoTenant(
            "Horizonte Textil", "horizonte-textil", "EMPRESARIAL",
            "Mateo", "Vargas", "#4338CA", "#312E81",
        ),
        18,
    ),
)


async def seed() -> None:
    with database_scope("global"):
        await provision()

    for demo, count in DEMOS:
        print(f"{demo.nombre} · {count} sucursales activas · {demo.correo}")


async def provision() -> None:
    async with async_session_factory.begin() as session:
        await apply_audit_context(
            session, AuditContext(origen="SISTEMA", user_agent="seed_demo_empresarial")
        )
        await session.execute(text("SELECT pg_advisory_xact_lock(20261108, 29)"))
        plan = await session.scalar(
            select(Plan).where(Plan.codigo == "EMPRESARIAL", Plan.activo.is_(True))
        )
        if (
            plan is None
            or plan.max_sucursales_activas != 25
            or (plan.precio_mensual, plan.precio_anual) != (1500, 18000)
        ):
            raise SeedError("Aplica primero la migración 20261108_0029.")

        existing_rows = await session.execute(
            select(Tenant.slug, Tenant.id_tenant)
            .where(Tenant.slug.in_([demo.slug for demo, _ in DEMOS]))
            .execution_options(include_all_tenants=True)
        )
        existing = dict(existing_rows.all())
        if existing and len(existing) != len(DEMOS):
            raise SeedError("Ya existe una empresa con uno de los identificadores de la carga.")
        if not existing:
            admins = [
                TenantAdminCreate(
                    nombres=demo.administrador_nombres,
                    apellidos=demo.administrador_apellidos,
                    correo=demo.correo,
                    password=getpass(f"Contraseña nueva para {demo.correo}: "),
                )
                for demo, _ in DEMOS
            ]
            city = await session.scalar(
                select(Ciudad)
                .where(
                    func.lower(Ciudad.nombre) == "santa cruz de la sierra",
                    func.lower(Ciudad.departamento) == "santa cruz",
                    Ciudad.activo.is_(True),
                )
                .order_by(Ciudad.id_ciudad)
                .limit(1)
            )
            if city is None:
                city = Ciudad(nombre="Santa Cruz de la Sierra", departamento="Santa Cruz")
                session.add(city)
                await session.flush()

            repository = PlatformRepository(session)
            end_date = add_one_month(date.today())
            for (demo, count), admin in zip(DEMOS, admins, strict=True):
                tenant_id = await repository.provision_tenant(
                    TenantCreate(
                        nombre=demo.nombre,
                        slug=demo.slug,
                        razon_social=f"{demo.nombre} (Demo)",
                        nit=demo.nit,
                        correo_contacto=demo.correo,
                        color_primario=demo.color_primario,
                        color_primario_oscuro=demo.color_primario_oscuro,
                        id_plan=plan.id_plan,
                        fecha_fin=end_date,
                        administrador=admin,
                    ),
                    email=demo.correo,
                    password_hash=hash_password(admin.password.get_secret_value()),
                )
                subscription = await session.scalar(
                    select(Subscription).where(Subscription.id_tenant == tenant_id)
                )
                if subscription is None:
                    raise SeedError(f"No se creó la suscripción de {demo.nombre}.")
                subscription.estado = "ACTIVA"
                subscription.proxima_renovacion = end_date + timedelta(days=1)
                subscription.fecha_fin_gracia = end_date + timedelta(days=7)
                session.add_all(
                    Sucursal(
                        id_tenant=tenant_id,
                        id_ciudad=city.id_ciudad,
                        nombre=f"{demo.nombre} · Sucursal {number:02d}",
                        direccion=f"Dirección de demostración {number:02d}, Santa Cruz",
                        hora_apertura=time(9),
                        hora_cierre=time(20),
                    )
                    for number in range(1, count + 1)
                )
                await session.flush()
                existing[demo.slug] = tenant_id

        for demo, count in DEMOS:
            tenant_id = existing[demo.slug]
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            subscription = await session.scalar(
                select(Subscription).where(Subscription.id_tenant == tenant_id)
            )
            active_branches = await session.scalar(
                select(func.count()).select_from(Sucursal)
                .where(Sucursal.id_tenant == tenant_id, Sucursal.activo.is_(True))
            )
            if (
                subscription is None
                or subscription.id_plan != plan.id_plan
                or active_branches != count
            ):
                raise SeedError(f"{demo.slug} no coincide con la demo esperada.")


async def main() -> None:
    try:
        await seed()
    except ValidationError:
        raise SystemExit("Usa una contraseña válida y vuelve a ejecutar la carga.") from None
    except SeedError as exc:
        raise SystemExit(str(exc)) from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
