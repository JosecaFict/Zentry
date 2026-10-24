"""Crea diez empresas de demostración y exporta sus credenciales.

Uso desde ``backend`` con las variables de Railway:
    railway run python -m app.scripts.seed_demo_tenants

La contraseña compartida solo está pensada para pruebas y debe cambiarse antes
de utilizar estas cuentas con información real.
"""

import argparse
import asyncio
import calendar
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_password
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.modules.auth.models import Usuario
from app.modules.platform.models import Plan, Subscription, Tenant
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.schemas import TenantAdminCreate, TenantCreate

DEMO_PASSWORD = "Admin123*"


@dataclass(frozen=True, slots=True)
class DemoTenant:
    nombre: str
    slug: str
    plan_codigo: str
    administrador_nombres: str
    administrador_apellidos: str
    color_primario: str
    color_primario_oscuro: str

    @property
    def correo(self) -> str:
        return f"admin+{self.slug}@zentrysaas.store"

    @property
    def nit(self) -> str:
        return f"DEMO-{self.slug.upper()}"


DEMO_TENANTS = (
    DemoTenant("Casa Elena", "casa-elena", "BASICO", "Elena", "Rojas", "#A23E48", "#762832"),
    DemoTenant("Nova Moda", "nova-moda", "BASICO", "Natalia", "Vargas", "#6D28D9", "#4C1D95"),
    DemoTenant("Urban Style", "urban-style", "BASICO", "Marco", "Suárez", "#0F766E", "#115E59"),
    DemoTenant(
        "Bella Boutique", "bella-boutique", "BASICO", "Camila", "Flores", "#DB2777", "#9D174D"
    ),
    DemoTenant(
        "Andina Fashion", "andina-fashion", "BASICO", "Lucía", "Mamani", "#C2410C", "#9A3412"
    ),
    DemoTenant(
        "Prisma Store", "prisma-store", "PROFESIONAL", "Paola", "Méndez", "#2563EB", "#1E40AF"
    ),
    DemoTenant("Élite Moda", "elite-moda", "PROFESIONAL", "Valeria", "López", "#7C3AED", "#5B21B6"),
    DemoTenant("Vértice", "vertice", "PROFESIONAL", "Diego", "Paredes", "#047857", "#065F46"),
    DemoTenant("Magnolia", "magnolia", "PROFESIONAL", "Sofía", "Cabrera", "#BE185D", "#831843"),
    DemoTenant(
        "Altura Comercial",
        "altura-comercial",
        "PROFESIONAL",
        "Andrés",
        "Salvatierra",
        "#0369A1",
        "#075985",
    ),
)


class SeedError(RuntimeError):
    """Error esperado que impide una carga parcial de datos."""


def add_one_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crea 10 empresas de demostración para Zentry.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tenant_credentials.csv"),
        help="Archivo CSV donde se guardará el listado de accesos.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirma la creación sin solicitar entrada interactiva.",
    )
    return parser


async def ensure_available() -> None:
    slugs = [item.slug for item in DEMO_TENANTS]
    emails = [item.correo for item in DEMO_TENANTS]
    async with async_session_factory() as session:
        existing_slugs = list(
            (
                await session.scalars(
                    select(Tenant.slug)
                    .where(Tenant.slug.in_(slugs))
                    .execution_options(include_all_tenants=True)
                )
            ).all()
        )
        existing_emails = list(
            (
                await session.scalars(
                    select(Usuario.correo)
                    .where(func.lower(Usuario.correo).in_(emails))
                    .execution_options(include_all_tenants=True)
                )
            ).all()
        )
    conflicts = [*existing_slugs, *existing_emails]
    if conflicts:
        raise SeedError(
            "La carga fue cancelada porque ya existen estos identificadores: "
            + ", ".join(conflicts)
        )


async def create_demo_tenants() -> list[dict[str, str]]:
    await ensure_available()
    credentials: list[dict[str, str]] = []
    today = date.today()
    end_date = add_one_month(today)

    async with async_session_factory() as session:
        try:
            await apply_audit_context(
                session,
                AuditContext(
                    origen="SISTEMA",
                    user_agent="seed_demo_tenants",
                    request_id="seed-10-demo-tenants",
                ),
            )
            plans = {
                plan.codigo: plan
                for plan in (
                    await session.scalars(
                        select(Plan)
                        .where(Plan.codigo.in_(("BASICO", "PROFESIONAL")), Plan.activo.is_(True))
                        .execution_options(include_all_tenants=True)
                    )
                ).all()
            }
            if set(plans) != {"BASICO", "PROFESIONAL"}:
                raise SeedError("Los planes activos BASICO y PROFESIONAL deben existir.")

            repository = PlatformRepository(session)
            for index, item in enumerate(DEMO_TENANTS, start=1):
                plan = plans[item.plan_codigo]
                payload = TenantCreate(
                    nombre=item.nombre,
                    slug=item.slug,
                    razon_social=f"{item.nombre} S.R.L. (Demo)",
                    nit=item.nit,
                    correo_contacto=item.correo,
                    telefono_contacto=f"7000{index:04d}",
                    color_primario=item.color_primario,
                    color_primario_oscuro=item.color_primario_oscuro,
                    id_plan=plan.id_plan,
                    modalidad="MENSUAL",
                    fecha_fin=end_date,
                    administrador=TenantAdminCreate(
                        nombres=item.administrador_nombres,
                        apellidos=item.administrador_apellidos,
                        correo=item.correo,
                        telefono=f"7100{index:04d}",
                        ci=f"DEMO-CI-{index:02d}",
                        password=SecretStr(DEMO_PASSWORD),
                    ),
                )
                tenant_id = await repository.provision_tenant(
                    payload,
                    email=item.correo,
                    password_hash=hash_password(DEMO_PASSWORD),
                )
                subscription = await session.scalar(
                    select(Subscription)
                    .where(Subscription.id_tenant == tenant_id)
                    .execution_options(include_all_tenants=True)
                )
                if subscription is None:
                    raise SeedError(f"No se creó la suscripción de {item.nombre}.")
                subscription.estado = "ACTIVA"
                subscription.fecha_inicio = today
                subscription.fecha_fin = end_date
                subscription.proxima_renovacion = end_date + timedelta(days=1)
                subscription.fecha_fin_gracia = end_date + timedelta(days=7)

                credentials.append(
                    {
                        "empresa": item.nombre,
                        "slug": item.slug,
                        "plan": item.plan_codigo,
                        "subdominio": f"https://{item.slug}.zentrysaas.store",
                        "correo": item.correo,
                        "password": DEMO_PASSWORD,
                    }
                )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return credentials


def write_credentials(path: Path, credentials: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(credentials[0]))
        writer.writeheader()
        writer.writerows(credentials)


async def async_main() -> int:
    args = build_parser().parse_args()
    if not args.yes:
        print("Se crearán 10 empresas demo con la contraseña compartida Admin123*.")
        confirmation = await asyncio.to_thread(input, "Escribe CREAR 10 EMPRESAS para confirmar: ")
        if confirmation.strip() != "CREAR 10 EMPRESAS":
            print("Operación cancelada; no se guardó ningún cambio.")
            return 1
    try:
        credentials = await create_demo_tenants()
        write_credentials(args.output, credentials)
    except (SeedError, SQLAlchemyError) as exc:
        print(f"No se crearon las empresas: {exc}")
        return 1
    finally:
        await engine.dispose()

    print("\nSe crearon correctamente 10 empresas demo:")
    for item in credentials:
        print(f"  {item['empresa']}: {item['correo']} | {item['password']} | {item['plan']}")
    print(f"\nCredenciales guardadas en: {args.output.resolve()}")
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print("\nOperación cancelada; no se guardó ningún cambio.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
