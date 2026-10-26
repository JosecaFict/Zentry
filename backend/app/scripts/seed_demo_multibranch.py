"""Amplía las empresas demo con sucursales, inventario y seis meses de ventas.

Uso desde ``backend`` en Railway::

    python -m app.scripts.seed_demo_multibranch

La carga es idempotente por tenant. Los planes Básicos quedan con 2 sucursales;
los Profesionales reciben entre 3 y 8. Se crean 30 ventas por mes y empresa,
distribuidas entre todas sus sucursales durante seis meses.
"""

import argparse
import asyncio
import calendar
import random
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_password
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.db.tenant_context import clear_tenant_context, set_tenant_context
from app.modules.auth.models import Ciudad, Cliente, Sucursal, Usuario, UsuarioRol
from app.modules.catalog.models import (
    HistorialPrecio,
    InventarioSucursal,
    Producto,
    VarianteProducto,
)
from app.modules.commerce.models import DetalleVenta, MetodoPago, Pago, TransaccionPasarela, Venta
from app.modules.inventory.models import (
    DetalleOrdenCompra,
    DetalleRecepcion,
    LoteInventario,
    MovimientoInventario,
    MovimientoLote,
    OrdenCompra,
    Proveedor,
    RecepcionMercaderia,
)
from app.modules.platform.models import Plan, Subscription, Tenant
from app.scripts.seed_demo_sales import (
    CUSTOMER_PASSWORD,
    CUSTOMERS,
    DEMO_SLUGS,
    SeedError,
    StockRow,
    add,
    consume_fifo,
    customer_email,
    get_or_create_customer_role,
)

SEED_PREFIX = "ZENTRY-DEMO-MULTIBRANCH-V1"
MONTHS = 6
SALES_PER_MONTH = 30
STOCK_PER_VARIANT = 30
BRANCH_NAMES = (
    ("Sucursal Principal", "Av. San Martín, Equipetrol"),
    ("Sucursal Norte", "Av. Cristo Redentor, 4.º anillo"),
    ("Sucursal Centro", "Calle Libertad, centro histórico"),
    ("Sucursal Las Palmas", "Av. Piraí, barrio Las Palmas"),
    ("Sucursal Urubó", "Av. Metropolitana, Urubó"),
    ("Sucursal Sur", "Av. Santos Dumont, 5.º anillo"),
    ("Sucursal Este", "Av. Virgen de Cotoca, 4.º anillo"),
    ("Sucursal Montero", "Av. Kennedy, Montero"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crea sucursales y ventas históricas demo.")
    parser.add_argument("--yes", action="store_true", help="Omite la confirmación interactiva.")
    return parser


def target_branch_count(slug: str, plan_code: str) -> int:
    if plan_code == "BASICO":
        return 2
    return random.Random(f"zentry:{slug}:branches").randint(3, 8)


def month_windows(today: date) -> list[tuple[date, date]]:
    windows = []
    for offset in reversed(range(MONTHS)):
        month_index = today.year * 12 + today.month - 1 - offset
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        if offset == 0:
            end = today
        windows.append((start, end))
    return windows


async def ensure_branches(session, tenant: Tenant, count: int) -> list[Sucursal]:
    city = await session.scalar(
        select(Ciudad).where(
            func.lower(Ciudad.nombre) == "santa cruz de la sierra",
            func.lower(Ciudad.departamento) == "santa cruz",
        )
    )
    if city is None:
        city = await add(
            session,
            Ciudad(nombre="Santa Cruz de la Sierra", departamento="Santa Cruz", pais="Bolivia"),
        )
    existing = {branch.nombre: branch for branch in (await session.scalars(select(Sucursal))).all()}
    branches = []
    for index, (name, address) in enumerate(BRANCH_NAMES[:count], start=1):
        branch = existing.get(name)
        if branch is None:
            branch = await add(
                session,
                Sucursal(
                    id_ciudad=city.id_ciudad,
                    nombre=name,
                    direccion=address,
                    telefono=f"7{tenant.id_tenant:04d}{index:03d}"[-8:],
                    hora_apertura=time(9),
                    hora_cierre=time(20),
                ),
            )
        branches.append(branch)
    return branches


async def ensure_customers(session, tenant: Tenant) -> list[Cliente]:
    role = await get_or_create_customer_role(session)
    password_hash = hash_password(CUSTOMER_PASSWORD)
    clients = []
    for index, (first_name, last_name) in enumerate(CUSTOMERS, start=1):
        email = customer_email(tenant.slug, index)
        user = await session.scalar(select(Usuario).where(func.lower(Usuario.correo) == email))
        if user is None:
            user = await add(
                session,
                Usuario(
                    nombres=first_name,
                    apellidos=last_name,
                    ci=f"DEMO-{tenant.id_tenant:04d}-CLI-{index:02d}",
                    correo=email,
                    telefono=f"72{tenant.id_tenant:04d}{index:02d}"[-8:],
                    password_hash=password_hash,
                    estado="ACTIVO",
                ),
            )
        else:
            user.estado = "ACTIVO"
        role_link = await session.scalar(
            select(UsuarioRol).where(
                UsuarioRol.id_usuario == user.id_usuario,
                UsuarioRol.id_rol == role.id_rol,
            )
        )
        if role_link is None:
            await add(session, UsuarioRol(id_usuario=user.id_usuario, id_rol=role.id_rol))
        client = await session.scalar(select(Cliente).where(Cliente.id_usuario == user.id_usuario))
        if client is None:
            client = await add(
                session,
                Cliente(
                    id_usuario=user.id_usuario,
                    fecha_nacimiento=date(1988 + index, (index * 2 - 1) % 12 + 1, 10 + index),
                    estado="ACTIVO",
                ),
            )
        else:
            client.estado = "ACTIVO"
        clients.append(client)
    return clients


async def provision_branch_stock(session, tenant: Tenant, branches: list[Sucursal]) -> None:
    supplier = await session.scalar(
        select(Proveedor).where(Proveedor.activo.is_(True)).order_by(Proveedor.id_proveedor)
    )
    if supplier is None:
        raise SeedError(f"{tenant.slug}: falta un proveedor activo.")
    variants = list(
        (
            await session.scalars(
                select(VarianteProducto)
                .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
                .where(VarianteProducto.activo.is_(True), Producto.activo.is_(True))
                .order_by(VarianteProducto.id_variante)
            )
        ).all()
    )
    if not variants:
        raise SeedError(f"{tenant.slug}: no tiene variantes activas.")
    for branch_index, branch in enumerate(branches, start=1):
        marker = f"{SEED_PREFIX}:{branch.nombre}"
        existing = await session.scalar(
            select(OrdenCompra.id_orden_compra).where(OrdenCompra.observacion == marker)
        )
        if existing is not None:
            continue
        order = await add(
            session,
            OrdenCompra(
                id_proveedor=supplier.id_proveedor,
                id_sucursal=branch.id_sucursal,
                estado="RECIBIDA",
                fecha_estimada=date.today(),
                observacion=marker,
            ),
        )
        receipt = await add(
            session,
            RecepcionMercaderia(
                id_orden_compra=order.id_orden_compra,
                id_sucursal=branch.id_sucursal,
                estado="CONFIRMADA",
                observacion="Inventario sintético para operación multisucursal.",
            ),
        )
        for line_index, variant in enumerate(variants, start=1):
            cost = Decimal("75.00")
            await add(
                session,
                DetalleOrdenCompra(
                    id_orden_compra=order.id_orden_compra,
                    id_variante=variant.id_variante,
                    cantidad=STOCK_PER_VARIANT,
                    costo_unitario_estimado=cost,
                ),
            )
            detail = await add(
                session,
                DetalleRecepcion(
                    id_recepcion=receipt.id_recepcion,
                    id_variante=variant.id_variante,
                    cantidad_recibida=STOCK_PER_VARIANT,
                    costo_unitario=cost,
                ),
            )
            lot = await add(
                session,
                LoteInventario(
                    id_detalle_recepcion=detail.id_detalle_recepcion,
                    id_sucursal=branch.id_sucursal,
                    id_variante=variant.id_variante,
                    numero_lote=f"MB-{tenant.id_tenant}-{branch_index}-{line_index}",
                    cantidad_inicial=STOCK_PER_VARIANT,
                    cantidad_disponible=0,
                    costo_unitario=cost,
                ),
            )
            inventory = await session.scalar(
                select(InventarioSucursal).where(
                    InventarioSucursal.id_sucursal == branch.id_sucursal,
                    InventarioSucursal.id_variante == variant.id_variante,
                )
            )
            if inventory is None:
                inventory = await add(
                    session,
                    InventarioSucursal(
                        id_sucursal=branch.id_sucursal,
                        id_variante=variant.id_variante,
                        stock_minimo=3,
                    ),
                )
            movement = await add(
                session,
                MovimientoInventario(
                    id_inventario=inventory.id_inventario,
                    tipo_movimiento="ENTRADA_PROVEEDOR",
                    cantidad=STOCK_PER_VARIANT,
                    referencia_tipo="RECEPCION",
                    referencia_id=receipt.id_recepcion,
                    motivo="Abastecimiento demo multisucursal",
                ),
            )
            await add(
                session,
                MovimientoLote(
                    id_movimiento=movement.id_movimiento,
                    id_lote=lot.id_lote,
                    cantidad=STOCK_PER_VARIANT,
                    costo_unitario=cost,
                ),
            )


async def branch_stock(session, branch_id: int) -> list[StockRow]:
    current_price = (
        select(HistorialPrecio.precio)
        .where(
            HistorialPrecio.id_producto == Producto.id_producto,
            HistorialPrecio.fecha_fin.is_(None),
        )
        .order_by(HistorialPrecio.fecha_inicio.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(InventarioSucursal, VarianteProducto.id_variante, current_price.label("price"))
            .join(VarianteProducto, VarianteProducto.id_variante == InventarioSucursal.id_variante)
            .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
            .where(
                InventarioSucursal.id_sucursal == branch_id,
                InventarioSucursal.stock_fisico - InventarioSucursal.stock_reservado >= 2,
                Producto.activo.is_(True),
                VarianteProducto.activo.is_(True),
            )
        )
    ).all()
    return [
        StockRow(row[0], row[1], Decimal(row[2]), row[0].stock_fisico - row[0].stock_reservado)
        for row in rows
        if row[2] is not None
    ]


async def create_sales(
    session, tenant: Tenant, branches: list[Sucursal], clients: list[Cliente]
) -> int:
    method = await session.scalar(select(MetodoPago).where(MetodoPago.codigo == "EFECTIVO"))
    if method is None:
        method = await add(
            session, MetodoPago(codigo="EFECTIVO", nombre="Efectivo", tipo="EFECTIVO", activo=True)
        )
    stocks = {
        branch.id_sucursal: await branch_stock(session, branch.id_sucursal) for branch in branches
    }
    if any(len(items) < 10 for items in stocks.values()):
        raise SeedError(f"{tenant.slug}: una sucursal no tiene inventario suficiente.")
    rng = random.Random(f"zentry:{tenant.slug}:six-month-sales")
    sale_number = 0
    for month_index, (start, end) in enumerate(month_windows(date.today())):
        days = (end - start).days + 1
        for monthly_index in range(SALES_PER_MONTH):
            branch = branches[(monthly_index + month_index) % len(branches)]
            options = [item for item in stocks[branch.id_sucursal] if item.available >= 2]
            choices = rng.sample(options, rng.randint(1, 3))
            quantities = [rng.choice((1, 1, 2)) for _ in choices]
            sold_at = datetime.combine(
                start + timedelta(days=rng.randrange(days)),
                time(rng.randint(9, 19), rng.randint(0, 59)),
                tzinfo=UTC,
            )
            subtotal = sum(
                (item.price * quantity for item, quantity in zip(choices, quantities, strict=True)),
                Decimal("0.00"),
            )
            channel = rng.choice(("PRESENCIAL", "PRESENCIAL", "WEB"))
            sale = await add(
                session,
                Venta(
                    id_cliente=rng.choice(clients).id_cliente,
                    id_sucursal=branch.id_sucursal,
                    canal_venta=channel,
                    modalidad_entrega="MOSTRADOR" if channel == "PRESENCIAL" else "RETIRO_SUCURSAL",
                    estado="PAGADA",
                    subtotal=subtotal,
                    descuento_total=Decimal("0.00"),
                    costo_envio=Decimal("0.00"),
                    total=subtotal,
                    fecha_venta=sold_at,
                    created_at=sold_at,
                    updated_at=sold_at,
                ),
            )
            for item, quantity in zip(choices, quantities, strict=True):
                await add(
                    session,
                    DetalleVenta(
                        id_venta=sale.id_venta,
                        id_variante=item.variant_id,
                        cantidad=quantity,
                        precio_unitario=item.price,
                        descuento=Decimal("0.00"),
                        subtotal=item.price * quantity,
                    ),
                )
                movement = await add(
                    session,
                    MovimientoInventario(
                        id_inventario=item.inventory.id_inventario,
                        tipo_movimiento="VENTA",
                        cantidad=quantity,
                        referencia_tipo="VENTA",
                        referencia_id=sale.id_venta,
                        motivo="Venta histórica demo multisucursal",
                        fecha_hora=sold_at,
                    ),
                )
                await consume_fifo(session, item, quantity, movement.id_movimiento)
                item.available -= quantity
            payment = await add(
                session,
                Pago(
                    id_venta=sale.id_venta,
                    id_metodo_pago=method.id_metodo_pago,
                    monto=subtotal,
                    moneda="BOB",
                    estado="PAGADO",
                    fecha_creacion=sold_at,
                    fecha_confirmacion=sold_at,
                ),
            )
            sale_number += 1
            await add(
                session,
                TransaccionPasarela(
                    id_pago=payment.id_pago,
                    proveedor="EFECTIVO",
                    external_payment_id=f"{SEED_PREFIX}:{tenant.slug}:{sale_number:04d}",
                    estado="SUCCEEDED",
                    monto=subtotal,
                    moneda="BOB",
                    respuesta_resumen={"synthetic": True, "seed": SEED_PREFIX},
                    fecha_creacion=sold_at,
                    fecha_confirmacion=sold_at,
                ),
            )
    return sale_number


async def seed_tenant(tenant: Tenant, plan_code: str) -> tuple[int, int, bool]:
    set_tenant_context(tenant.id_tenant)
    try:
        async with async_session_factory() as session:
            await apply_audit_context(
                session,
                AuditContext(
                    tenant_id=tenant.id_tenant,
                    origen="SISTEMA",
                    user_agent="seed_demo_multibranch",
                    request_id=f"multibranch-{tenant.slug}-v1",
                ),
            )
            previous = await session.scalar(
                select(TransaccionPasarela.id_transaccion)
                .where(
                    TransaccionPasarela.external_payment_id.like(f"{SEED_PREFIX}:{tenant.slug}:%")
                )
                .limit(1)
            )
            if previous is not None:
                count = await session.scalar(select(func.count(Sucursal.id_sucursal)))
                return int(count or 0), 0, True
            branch_count = target_branch_count(tenant.slug, plan_code)
            branches = await ensure_branches(session, tenant, branch_count)
            clients = await ensure_customers(session, tenant)
            await provision_branch_stock(session, tenant, branches)
            sales = await create_sales(session, tenant, branches, clients)
            await session.commit()
            return len(branches), sales, False
    finally:
        clear_tenant_context()


async def async_main() -> int:
    args = build_parser().parse_args()
    if not args.yes:
        print("Se completarán las sucursales y seis meses de ventas en las 10 empresas demo.")
        confirmation = await asyncio.to_thread(
            input, "Escribe CARGAR MULTISUCURSAL para confirmar: "
        )
        if confirmation.strip() != "CARGAR MULTISUCURSAL":
            print("Operación cancelada.")
            return 1
    try:
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(Tenant, Plan.codigo)
                    .join(Subscription, Subscription.id_tenant == Tenant.id_tenant)
                    .join(Plan, Plan.id_plan == Subscription.id_plan)
                    .where(Tenant.slug.in_(DEMO_SLUGS))
                    .execution_options(include_all_tenants=True)
                )
            ).all()
        by_slug = {tenant.slug: (tenant, plan_code) for tenant, plan_code in rows}
        missing = [slug for slug in DEMO_SLUGS if slug not in by_slug]
        if missing:
            raise SeedError("Faltan empresas demo: " + ", ".join(missing))
        for slug in DEMO_SLUGS:
            tenant, plan_code = by_slug[slug]
            branches, sales, skipped = await seed_tenant(tenant, plan_code)
            status = "omitida (ya cargada)" if skipped else f"{branches} sucursales, {sales} ventas"
            print(f"  {slug}: {status}")
    except (SeedError, SQLAlchemyError, ValueError) as exc:
        print(f"No se completó la carga: {exc}")
        return 1
    finally:
        await engine.dispose()
    print("Carga multisucursal completada correctamente.")
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
