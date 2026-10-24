"""Genera clientes y ventas históricas coherentes para las diez empresas demo.

Uso desde ``backend`` en Railway::

    python -m app.scripts.seed_demo_sales

La carga es idempotente por empresa. Consume inventario y lotes FIFO existentes,
registra pagos en efectivo y conserva fechas históricas para alimentar reportes.
"""

import argparse
import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import hash_password
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.db.tenant_context import clear_tenant_context, set_tenant_context
from app.modules.auth.models import Cliente, Rol, Sucursal, Usuario, UsuarioRol
from app.modules.catalog.models import (
    HistorialPrecio,
    InventarioSucursal,
    Producto,
    VarianteProducto,
)
from app.modules.commerce.models import DetalleVenta, MetodoPago, Pago, TransaccionPasarela, Venta
from app.modules.inventory.models import LoteInventario, MovimientoInventario, MovimientoLote
from app.modules.platform.models import Tenant

DEMO_SLUGS = (
    "casa-elena", "nova-moda", "urban-style", "bella-boutique", "andina-fashion",
    "prisma-store", "elite-moda", "vertice", "magnolia", "altura-comercial",
)
CUSTOMER_PASSWORD = "Cliente123*"
CUSTOMERS_PER_TENANT = 6
SALES_PER_TENANT = 30
SEED_PREFIX = "ZENTRY-DEMO-SALES-V1"
CUSTOMERS = (
    ("María", "Fernández"), ("Carlos", "Gutiérrez"), ("Ana", "Ribera"),
    ("Jorge", "Mendoza"), ("Daniela", "Soto"), ("Luis", "Mercado"),
)


class SeedError(RuntimeError):
    """Impide guardar una carga comercial incompleta."""


@dataclass(slots=True)
class StockRow:
    inventory: InventarioSucursal
    variant_id: int
    price: Decimal
    available: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crea clientes y ventas para empresas demo.")
    parser.add_argument("--yes", action="store_true", help="Omite la confirmación interactiva.")
    return parser


def customer_email(tenant_slug: str, customer_number: int) -> str:
    return f"cliente{customer_number:02d}+{tenant_slug}@zentrysaas.store"


async def add(session, entity):
    session.add(entity)
    await session.flush()
    return entity


async def consume_fifo(session, stock: StockRow, quantity: int, movement_id: int) -> None:
    remaining = quantity
    lots = list((await session.scalars(
        select(LoteInventario)
        .where(
            LoteInventario.id_sucursal == stock.inventory.id_sucursal,
            LoteInventario.id_variante == stock.variant_id,
            LoteInventario.activo.is_(True),
            LoteInventario.cantidad_disponible > 0,
        )
        .order_by(LoteInventario.fecha_ingreso, LoteInventario.id_lote)
        .with_for_update()
    )).all())
    for lot in lots:
        used = min(remaining, lot.cantidad_disponible)
        if used:
            lot.cantidad_disponible -= used
            await add(session, MovimientoLote(
                id_movimiento=movement_id,
                id_lote=lot.id_lote,
                cantidad=used,
                costo_unitario=lot.costo_unitario,
            ))
            remaining -= used
        if remaining == 0:
            break
    if remaining:
        raise SeedError(f"Los lotes no cubren la variante {stock.variant_id}.")


async def create_customers(session, tenant: Tenant, role: Rol) -> list[Cliente]:
    clients: list[Cliente] = []
    password_hash = hash_password(CUSTOMER_PASSWORD)
    for index, (first_name, last_name) in enumerate(CUSTOMERS, start=1):
        email = customer_email(tenant.slug, index)
        user = await add(session, Usuario(
            nombres=first_name,
            apellidos=last_name,
            ci=f"DEMO-{tenant.id_tenant:04d}-CLI-{index:02d}",
            correo=email,
            telefono=f"72{tenant.id_tenant:04d}{index:02d}"[-8:],
            password_hash=password_hash,
            estado="ACTIVO",
        ))
        await add(session, UsuarioRol(id_usuario=user.id_usuario, id_rol=role.id_rol))
        clients.append(await add(session, Cliente(
            id_usuario=user.id_usuario,
            fecha_nacimiento=date(1988 + index, (index * 2 - 1) % 12 + 1, 10 + index),
            estado="ACTIVO",
        )))
    return clients


async def available_stock(session, branch_id: int) -> list[StockRow]:
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
    rows = (await session.execute(
        select(InventarioSucursal, VarianteProducto.id_variante, current_price.label("price"))
        .join(VarianteProducto, VarianteProducto.id_variante == InventarioSucursal.id_variante)
        .join(Producto, Producto.id_producto == VarianteProducto.id_producto)
        .where(
            InventarioSucursal.id_sucursal == branch_id,
            Producto.activo.is_(True),
            VarianteProducto.activo.is_(True),
            InventarioSucursal.stock_fisico - InventarioSucursal.stock_reservado >= 2,
        )
        .order_by(VarianteProducto.id_variante)
    )).all()
    return [
        StockRow(inventory=row[0], variant_id=row[1], price=Decimal(row[2]),
                 available=row[0].stock_fisico - row[0].stock_reservado)
        for row in rows if row[2] is not None
    ]


async def seed_tenant(tenant: Tenant) -> dict[str, int]:
    set_tenant_context(tenant.id_tenant)
    try:
        async with async_session_factory() as session:
            await apply_audit_context(session, AuditContext(
                tenant_id=tenant.id_tenant,
                origen="SISTEMA",
                user_agent="seed_demo_sales",
                request_id=f"seed-sales-{tenant.slug}-v1",
            ))
            existing = await session.scalar(
                select(TransaccionPasarela.id_transaccion)
                .where(TransaccionPasarela.external_payment_id.like(f"{SEED_PREFIX}:{tenant.slug}:%"))
                .limit(1)
            )
            if existing is not None:
                return {"clientes": 0, "ventas": 0, "omitida": 1}

            branch = await session.scalar(
                select(Sucursal).where(Sucursal.activo.is_(True)).order_by(Sucursal.id_sucursal)
            )
            role = await session.scalar(
                select(Rol).where(func.upper(Rol.nombre) == "CLIENTE", Rol.activo.is_(True))
            )
            if branch is None or role is None:
                raise SeedError("Falta una sucursal activa o el rol CLIENTE.")
            stocks = await available_stock(session, branch.id_sucursal)
            if len(stocks) < 10:
                raise SeedError("Se requieren al menos 10 variantes con inventario.")

            method = await session.scalar(select(MetodoPago).where(MetodoPago.codigo == "EFECTIVO"))
            if method is None:
                method = await add(session, MetodoPago(
                    codigo="EFECTIVO", nombre="Efectivo", tipo="EFECTIVO", activo=True
                ))
            clients = await create_customers(session, tenant, role)
            rng = random.Random(tenant.id_tenant * 10_003)
            now = datetime.now(UTC)

            for sale_number in range(1, SALES_PER_TENANT + 1):
                sold_at = now - timedelta(
                    days=rng.randint(1, 179), hours=rng.randint(0, 10), minutes=rng.randint(0, 59)
                )
                choices = rng.sample(
                    [item for item in stocks if item.available >= 1], rng.randint(1, 3)
                )
                quantities = [
                    1 if item.available < 3 else rng.choice((1, 1, 2))
                    for item in choices
                ]
                subtotal = sum(
                    (
                        item.price * quantity
                        for item, quantity in zip(choices, quantities, strict=True)
                    ),
                    Decimal("0.00"),
                )
                channel = rng.choice(("PRESENCIAL", "WEB", "PRESENCIAL"))
                sale = await add(session, Venta(
                    id_cliente=rng.choice(clients).id_cliente,
                    id_sucursal=branch.id_sucursal,
                    canal_venta=channel,
                    modalidad_entrega=(
                        "MOSTRADOR" if channel == "PRESENCIAL" else "RETIRO_SUCURSAL"
                    ),
                    estado="PAGADA",
                    subtotal=subtotal,
                    descuento_total=Decimal("0.00"),
                    costo_envio=Decimal("0.00"),
                    total=subtotal,
                    fecha_venta=sold_at,
                    created_at=sold_at,
                    updated_at=sold_at,
                ))
                for item, quantity in zip(choices, quantities, strict=True):
                    await add(session, DetalleVenta(
                        id_venta=sale.id_venta,
                        id_variante=item.variant_id,
                        cantidad=quantity,
                        precio_unitario=item.price,
                        descuento=Decimal("0.00"),
                        subtotal=item.price * quantity,
                    ))
                    movement = await add(session, MovimientoInventario(
                        id_inventario=item.inventory.id_inventario,
                        tipo_movimiento="VENTA",
                        cantidad=quantity,
                        referencia_tipo="VENTA",
                        referencia_id=sale.id_venta,
                        motivo="Venta sintética para reportes",
                        fecha_hora=sold_at,
                    ))
                    await consume_fifo(session, item, quantity, movement.id_movimiento)
                    item.available -= quantity
                payment = await add(session, Pago(
                    id_venta=sale.id_venta,
                    id_metodo_pago=method.id_metodo_pago,
                    monto=sale.total,
                    moneda="BOB",
                    estado="PAGADO",
                    fecha_creacion=sold_at,
                    fecha_confirmacion=sold_at,
                ))
                await add(session, TransaccionPasarela(
                    id_pago=payment.id_pago,
                    proveedor="EFECTIVO",
                    external_payment_id=f"{SEED_PREFIX}:{tenant.slug}:{sale_number:03d}",
                    estado="SUCCEEDED",
                    monto=sale.total,
                    moneda="BOB",
                    respuesta_resumen={"synthetic": True, "seed": SEED_PREFIX},
                    fecha_creacion=sold_at,
                    fecha_confirmacion=sold_at,
                ))
            await session.commit()
            return {"clientes": len(clients), "ventas": SALES_PER_TENANT, "omitida": 0}
    finally:
        clear_tenant_context()


async def async_main() -> int:
    args = build_parser().parse_args()
    if not args.yes:
        print("Se crearán 6 clientes y 30 ventas históricas en cada empresa demo.")
        confirmation = await asyncio.to_thread(input, "Escribe CARGAR VENTAS DEMO para confirmar: ")
        if confirmation.strip() != "CARGAR VENTAS DEMO":
            print("Operación cancelada.")
            return 1
    try:
        async with async_session_factory() as session:
            tenants = list((await session.scalars(
                select(Tenant).where(Tenant.slug.in_(DEMO_SLUGS))
                .execution_options(include_all_tenants=True)
            )).all())
        by_slug = {tenant.slug: tenant for tenant in tenants}
        missing = [slug for slug in DEMO_SLUGS if slug not in by_slug]
        if missing:
            raise SeedError("Faltan empresas demo: " + ", ".join(missing))
        for slug in DEMO_SLUGS:
            result = await seed_tenant(by_slug[slug])
            status = "omitida (ya cargada)" if result["omitida"] else (
                f"{result['clientes']} clientes, {result['ventas']} ventas"
            )
            print(f"  {slug}: {status}")
    except (SeedError, SQLAlchemyError, ValueError) as exc:
        print(f"No se completó la carga: {exc}")
        return 1
    finally:
        await engine.dispose()
    print("Carga comercial demo completada.")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
