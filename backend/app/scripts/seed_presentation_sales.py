"""Genera ventas sintéticas para la presentación de Zentry del 10 de noviembre."""

import argparse
import asyncio
import calendar
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from secrets import token_urlsafe

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_password
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.db.tenant_context import clear_tenant_context, database_scope, set_tenant_context
from app.modules.auth.models import Cliente, Sucursal, Usuario
from app.modules.catalog.models import (
    HistorialPrecio,
    InventarioSucursal,
    Producto,
    VarianteProducto,
)
from app.modules.commerce.models import DetalleVenta, MetodoPago, Pago, TransaccionPasarela, Venta
from app.modules.inventory.models import (
    DetalleRecepcion,
    LoteInventario,
    MovimientoInventario,
    MovimientoLote,
    RecepcionMercaderia,
)
from app.modules.platform.models import Tenant
from app.scripts.seed_demo_empresarial import DEMOS
from app.scripts.seed_demo_sales import DEMO_SLUGS, SeedError, add

SLUGS = ("capricho-store", *DEMO_SLUGS, *(demo.slug for demo, _ in DEMOS))
MARKER = "ZENTRY-DEMO-PRESENTACION-20261110"
LOCAL_TIME = timezone(timedelta(hours=-4))
MONDAY = date(2026, 11, 9)
CUSTOMERS = 12


@dataclass(frozen=True)
class SaleSlot:
    when: datetime
    customer: int


@dataclass(frozen=True)
class Line:
    inventory_id: int
    variant_id: int
    price: Decimal
    quantity: int


@dataclass(frozen=True)
class PlannedSale:
    slot: SaleSlot
    branch_id: int
    lines: tuple[Line, ...]


def sale_slots(slug: str, phase: str) -> list[SaleSlot]:
    rng = random.Random(f"{MARKER}:{slug}")
    total = rng.randint(60, 75)
    monday_count = rng.randint(1, 3)
    november_count = rng.randint(2, 5)
    weights = [rng.randint(6, 15) for _ in range(6)]
    months = [month for month, weight in enumerate(weights, 5) for _ in range(weight)]
    counts = Counter(range(5, 11))
    counts.update(rng.choices(months, k=total - monday_count - november_count - 6))
    counts[11] = november_count

    if phase == "lunes":
        dates = [
            datetime.combine(MONDAY, time(9 + 2 * index, rng.randrange(60)), LOCAL_TIME)
            for index in range(monday_count)
        ]
    else:
        dates = []
        for month in sorted(counts):
            last_day = 8 if month == 11 else calendar.monthrange(MONDAY.year, month)[1]
            days = [date(MONDAY.year, month, day) for day in range(1, last_day + 1)]
            for day in rng.choices(
                days,
                weights=[2 if value.weekday() in (4, 5) else 1 for value in days],
                k=counts[month],
            ):
                dates.append(
                    datetime.combine(day, time(rng.randint(9, 19), rng.randrange(60)), LOCAL_TIME)
                )
    return [
        SaleSlot(when, rng.choices(range(CUSTOMERS), weights=range(CUSTOMERS, 0, -1))[0])
        for when in sorted(dates)
    ]


async def plan_sales(session, slug: str, phase: str) -> list[PlannedSale]:
    price = (
        select(HistorialPrecio.precio)
        .where(
            HistorialPrecio.id_producto == Producto.id_producto, HistorialPrecio.fecha_fin.is_(None)
        )
        .correlate(Producto)
        .scalar_subquery()
    )
    result = await session.execute(
        select(
            InventarioSucursal.id_sucursal,
            InventarioSucursal.id_inventario,
            InventarioSucursal.id_variante,
            price,
        )
        .join(Sucursal, Sucursal.id_sucursal == InventarioSucursal.id_sucursal)
        .join(VarianteProducto, VarianteProducto.id_variante == InventarioSucursal.id_variante)
        .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
        .where(
            Sucursal.activo.is_(True), VarianteProducto.activo.is_(True), Producto.activo.is_(True)
        )
        .order_by(InventarioSucursal.id_sucursal, InventarioSucursal.id_variante)
    )
    options = defaultdict(list)
    for branch_id, inventory_id, variant_id, amount in result:
        if amount is not None and amount > 0:
            options[branch_id].append((inventory_id, variant_id, amount))
    if not options:
        raise SeedError(f"{slug}: no hay sucursales con variantes y precio vigente.")
    rng = random.Random(f"{MARKER}:{slug}:{phase}:prendas")
    branches = list(options)
    rng.shuffle(branches)
    planned = []
    for index, slot in enumerate(sale_slots(slug, phase)):
        branch_id = branches[index % len(branches)]
        variants = options[branch_id]
        picks = rng.sample(variants, min(len(variants), rng.choices((1, 2, 3), (5, 3, 1))[0]))
        lines = tuple(Line(*item, rng.choices((1, 2, 3), (8, 3, 1))[0]) for item in picks)
        planned.append(PlannedSale(slot, branch_id, lines))
    return planned


async def get_customers(session, slug: str, created_at: datetime) -> list[int]:
    emails = [f"presentacion-{index + 1:02d}.{slug}@example.invalid" for index in range(CUSTOMERS)]
    result = await session.execute(
        select(Usuario.correo, Cliente.id_cliente)
        .join(Cliente, Cliente.id_usuario == Usuario.id_usuario)
        .where(Usuario.correo.in_(emails))
    )
    customer_ids = dict(result.all())
    for index, email in enumerate(emails, 1):
        if email in customer_ids:
            continue
        user = await add(
            session,
            Usuario(
                nombres=f"Cliente demo {index:02d}",
                apellidos="Presentación",
                correo=email,
                password_hash=hash_password(token_urlsafe(32)),
                estado="INACTIVO",
                created_at=created_at,
                updated_at=created_at,
            ),
        )
        customer = await add(session, Cliente(id_usuario=user.id_usuario, estado="ACTIVO"))
        customer_ids[email] = customer.id_cliente
    return [customer_ids[email] for email in emails]


async def stage_lots(session, planned, phase):
    quantities = Counter()
    first_sale = {}
    variants = {}
    for sale in planned:
        first_sale.setdefault(sale.branch_id, sale.slot.when)
        for line in sale.lines:
            quantities[line.inventory_id] += line.quantity
            variants[line.inventory_id] = (sale.branch_id, line.variant_id, line.price)
    before = dict(
        (
            await session.execute(
                select(InventarioSucursal.id_inventario, InventarioSucursal.stock_fisico)
                .where(InventarioSucursal.id_inventario.in_(quantities))
                .order_by(InventarioSucursal.id_inventario)
                .with_for_update()
            )
        ).all()
    )
    if before.keys() != quantities.keys():
        raise SeedError("Cambió el inventario mientras se preparaba la carga.")
    receipts = {}
    for branch_id, first in first_sale.items():
        arrived_at = first - timedelta(hours=2)
        receipts[branch_id] = await add(
            session,
            RecepcionMercaderia(
                id_sucursal=branch_id,
                fecha_recepcion=arrived_at,
                created_at=arrived_at,
                observacion=f"{MARKER}:{phase}",
            ),
        )
    lots = {}
    for inventory_id, quantity in sorted(quantities.items()):
        branch_id, variant_id, price = variants[inventory_id]
        receipt = receipts[branch_id]
        cost = (price / 2).quantize(Decimal("0.01"))
        detail = await add(
            session,
            DetalleRecepcion(
                id_recepcion=receipt.id_recepcion,
                id_variante=variant_id,
                cantidad_recibida=quantity,
                costo_unitario=cost,
            ),
        )
        lot = await add(
            session,
            LoteInventario(
                id_detalle_recepcion=detail.id_detalle_recepcion,
                id_sucursal=branch_id,
                id_variante=variant_id,
                numero_lote=f"{MARKER}:{phase}:{inventory_id}",
                cantidad_inicial=quantity,
                cantidad_disponible=0,
                costo_unitario=cost,
                fecha_ingreso=receipt.fecha_recepcion,
            ),
        )
        movement = await add(
            session,
            MovimientoInventario(
                id_inventario=inventory_id,
                tipo_movimiento="ENTRADA_PROVEEDOR",
                cantidad=quantity,
                referencia_tipo="RECEPCION",
                referencia_id=receipt.id_recepcion,
                motivo=f"{MARKER}: entrada sintética",
                fecha_hora=receipt.fecha_recepcion,
            ),
        )
        session.add(
            MovimientoLote(
                id_movimiento=movement.id_movimiento,
                id_lote=lot.id_lote,
                cantidad=quantity,
                costo_unitario=cost,
            )
        )
        lots[inventory_id] = lot
    await session.flush()
    return lots, before


async def record_sales(session, tenant, phase, planned):
    first = planned[0].slot.when
    customers = await get_customers(session, tenant.slug, first - timedelta(days=1))
    method = await session.scalar(select(MetodoPago).where(MetodoPago.codigo == "EFECTIVO"))
    if method is None:
        method = await add(
            session, MetodoPago(codigo="EFECTIVO", nombre="Efectivo", tipo="EFECTIVO")
        )
    lots, before = await stage_lots(session, planned, phase)
    for index, item in enumerate(planned, 1):
        when = item.slot.when
        total = sum(line.price * line.quantity for line in item.lines)
        sale = await add(
            session,
            Venta(
                id_cliente=customers[item.slot.customer],
                id_sucursal=item.branch_id,
                canal_venta="PRESENCIAL",
                modalidad_entrega="ENTREGA_DIRECTA",
                estado="PAGADA",
                subtotal=total,
                total=total,
                fecha_venta=when,
                created_at=when,
                updated_at=when,
            ),
        )
        for line in item.lines:
            session.add(
                DetalleVenta(
                    id_venta=sale.id_venta,
                    id_variante=line.variant_id,
                    cantidad=line.quantity,
                    precio_unitario=line.price,
                    subtotal=line.price * line.quantity,
                )
            )
            movement = await add(
                session,
                MovimientoInventario(
                    id_inventario=line.inventory_id,
                    tipo_movimiento="VENTA",
                    cantidad=line.quantity,
                    referencia_tipo="VENTA",
                    referencia_id=sale.id_venta,
                    motivo=f"{MARKER}: venta sintética",
                    fecha_hora=when,
                ),
            )
            lot = lots[line.inventory_id]
            session.add(
                MovimientoLote(
                    id_movimiento=movement.id_movimiento,
                    id_lote=lot.id_lote,
                    cantidad=line.quantity,
                    costo_unitario=lot.costo_unitario,
                )
            )
        payment = await add(
            session,
            Pago(
                id_venta=sale.id_venta,
                id_metodo_pago=method.id_metodo_pago,
                monto=total,
                moneda="BOB",
                estado="PAGADO",
                fecha_creacion=when,
                fecha_confirmacion=when,
            ),
        )
        session.add(
            TransaccionPasarela(
                id_pago=payment.id_pago,
                proveedor="EFECTIVO",
                estado="SUCCEEDED",
                monto=total,
                moneda="BOB",
                external_payment_id=f"{MARKER}:{phase}:{tenant.slug}:{index:03d}",
                respuesta_resumen={"synthetic": True, "seed": MARKER, "phase": phase},
                fecha_creacion=when,
                fecha_confirmacion=when,
            )
        )
    await session.flush()
    after = dict(
        (
            await session.execute(
                select(InventarioSucursal.id_inventario, InventarioSucursal.stock_fisico).where(
                    InventarioSucursal.id_inventario.in_(before)
                )
            )
        ).all()
    )
    open_lots = await session.scalar(
        select(func.count())
        .select_from(LoteInventario)
        .where(
            LoteInventario.id_lote.in_([lot.id_lote for lot in lots.values()]),
            LoteInventario.cantidad_disponible != 0,
        )
    )
    if before != after or open_lots:
        raise SeedError(f"{tenant.slug}: el saldo final no coincide con el saldo original.")


async def count_loaded(session, slug: str, phase: str) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(TransaccionPasarela)
        .where(TransaccionPasarela.external_payment_id.like(f"{MARKER}:{phase}:{slug}:%"))
    )


async def seed_tenant(tenant, phase: str, apply: bool) -> int:
    slug = tenant.slug
    set_tenant_context(tenant.id_tenant)
    try:
        with database_scope("tenant"):
            async with async_session_factory.begin() as session:
                if apply:
                    await session.execute(
                        text("SELECT pg_advisory_xact_lock(20261110, :tenant_id)"),
                        {"tenant_id": tenant.id_tenant},
                    )
                existing = await count_loaded(session, slug, phase)
                if existing == len(sale_slots(slug, phase)):
                    print(f"{slug}: {existing} ventas ya registradas en esta fase.")
                    return 0
                if existing:
                    raise SeedError(f"{slug}: hay una carga parcial que requiere revisión.")
                if apply and phase == "lunes":
                    historical = await count_loaded(session, slug, "historico")
                    if historical != len(sale_slots(slug, "historico")):
                        raise SeedError(f"{slug}: aplica primero la fase histórica.")
                planned = await plan_sales(session, slug, phase)
                by_month = Counter(sale.slot.when.strftime("%Y-%m") for sale in planned)
                branches = len({sale.branch_id for sale in planned})
                months = ", ".join(f"{month}={count}" for month, count in sorted(by_month.items()))
                print(
                    f"{slug}: {len(planned)} ventas, {branches} sucursales · {months}", flush=True
                )
                if apply:
                    await apply_audit_context(
                        session,
                        AuditContext(
                            tenant_id=tenant.id_tenant,
                            origen="SISTEMA",
                            user_agent="seed_presentation_sales",
                            request_id=f"{MARKER}:{phase}",
                        ),
                    )
                    await record_sales(session, tenant, phase, planned)
            return len(planned)
    finally:
        clear_tenant_context()


async def run(slugs, phase: str, apply: bool) -> None:
    latest = max(sale_slots(slug, phase)[-1].when for slug in slugs)
    if apply and datetime.now(LOCAL_TIME) < latest:
        raise SeedError(f"Ejecuta esta fase a partir del {latest:%d/%m/%Y a las %H:%M} (Bolivia).")
    with database_scope("global"):
        async with async_session_factory() as session:
            tenants = {
                tenant.slug: tenant
                for tenant in await session.scalars(
                    select(Tenant).where(Tenant.slug.in_(slugs), Tenant.estado == "ACTIVO")
                )
            }
    missing = set(slugs) - tenants.keys()
    if missing:
        raise SeedError("Empresas activas faltantes: " + ", ".join(sorted(missing)))
    count = 0
    for slug in slugs:
        count += await seed_tenant(tenants[slug], phase, apply)
    label = "Ventas nuevas registradas" if apply else "Vista previa · ventas nuevas"
    print(f"{label}: {count}. Última fecha de la fase: {latest:%d/%m/%Y %H:%M} (Bolivia).")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fase", choices=("historico", "lunes"), required=True)
    parser.add_argument("--empresa", choices=SLUGS, help="Limita la carga a una empresa.")
    parser.add_argument(
        "--aplicar", action="store_true", help="Confirma la escritura en PostgreSQL."
    )
    args = parser.parse_args()
    slugs = (args.empresa,) if args.empresa else SLUGS
    try:
        await run(slugs, args.fase, args.aplicar)
    except SeedError as exc:
        raise SystemExit(str(exc)) from None
    except SQLAlchemyError as exc:
        code = getattr(getattr(exc, "orig", None), "sqlstate", "-")
        raise SystemExit(f"Falló la carga de una empresa. PostgreSQL: {code}.") from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
