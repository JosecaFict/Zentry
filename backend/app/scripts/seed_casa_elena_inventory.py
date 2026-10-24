"""Carga un catálogo y una compra inicial coherentes para Casa Elena.

Uso desde ``backend`` en Railway::

    python -m app.scripts.seed_casa_elena_inventory

No crea imágenes. La carga se cancela si detecta una ejecución anterior.
"""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.db.tenant_context import clear_tenant_context, set_tenant_context
from app.modules.auth.models import Ciudad, Sucursal, Usuario
from app.modules.catalog.models import (
    Categoria,
    Color,
    HistorialPrecio,
    InventarioSucursal,
    Marca,
    MedidaTallaProducto,
    Producto,
    Talla,
    VarianteProducto,
)
from app.modules.inventory.models import (
    DetalleOrdenCompra,
    DetalleRecepcion,
    LoteInventario,
    MovimientoInventario,
    MovimientoLote,
    OrdenCompra,
    ProductoProveedor,
    Proveedor,
    RecepcionMercaderia,
)
from app.modules.platform.models import Tenant

TENANT_SLUG = "casa-elena"
SEED_MARKER = "CARGA CATALOGO SUPERIOR ZENTRY 2026-02"
PREVIOUS_SEED_MARKERS = (
    "CARGA INICIAL CASA ELENA 2026-01",
    "CARGA INICIAL ZENTRY 2026-01",
)
REMAINING_DEMO_SLUGS = (
    "nova-moda",
    "urban-style",
    "bella-boutique",
    "andina-fashion",
    "prisma-store",
    "elite-moda",
    "vertice",
    "magnolia",
    "altura-comercial",
)


class SeedError(RuntimeError):
    """Impide que se guarde una carga incompleta o duplicada."""


class AlreadySeededError(SeedError):
    """Indica que una empresa ya tiene la carga inicial."""


@dataclass(frozen=True, slots=True)
class Garment:
    code: str
    name: str
    category: str
    audience: str
    brand: str
    supplier: str
    colors: tuple[str, str]
    price: str
    cost: str
    stock: int
    description: str
    base_measurements: tuple[str | None, str | None, str | None, str | None]


SIZES = (("XS", 1), ("S", 2), ("M", 3), ("L", 4), ("XL", 5))
COLORS = {
    "Negro": "#111111",
    "Blanco": "#FFFFFF",
    "Azul marino": "#1E3A5F",
    "Beige": "#D8C3A5",
    "Rosa palo": "#D8A7B1",
    "Verde oliva": "#66734A",
    "Rojo vino": "#722F37",
    "Celeste": "#8EC5E8",
}
CATEGORIES = {
    "Poleras": "Poleras de uso diario para hombre y mujer.",
    "Polos": "Polos casuales con cuello para hombre y mujer.",
    "Blusas": "Blusas de uso casual y formal para mujer.",
    "Camisas": "Camisas casuales y formales para hombre y mujer.",
}
BRANDS = {
    "Zenda Basics": ("Bolivia", "Prendas básicas y versátiles de uso diario."),
    "Aura Mujer": ("Colombia", "Blusas y camisas femeninas contemporáneas."),
    "Lino Sur": ("Perú", "Camisas frescas con fibras ligeras."),
    "Norte Casual": ("Bolivia", "Poleras y polos urbanos para hombre y mujer."),
}
SUPPLIERS = {
    "Textiles Andinos": ("Textiles Andinos S.R.L.", "CE-PROV-001", "María Fernanda Ríos"),
    "Moda Latina": ("Importadora Moda Latina Ltda.", "CE-PROV-002", "Carolina Suárez"),
    "Confecciones Oriente": (
        "Confecciones Oriente S.R.L.",
        "CE-PROV-003",
        "Andrea Molina",
    ),
}
GARMENTS = (
    Garment(
        "PO01",
        "Polera Esencial Mujer",
        "Poleras",
        "MUJER",
        "Zenda Basics",
        "Textiles Andinos",
        ("Blanco", "Negro"),
        "149",
        "70",
        7,
        "Polera de algodón suave y corte femenino regular.",
        ("36", "44", "60", "18"),
    ),
    Garment(
        "PO02",
        "Polera Esencial Hombre",
        "Poleras",
        "HOMBRE",
        "Zenda Basics",
        "Textiles Andinos",
        ("Blanco", "Azul marino"),
        "149",
        "70",
        7,
        "Polera de algodón suave y corte masculino regular.",
        ("42", "51", "70", "21"),
    ),
    Garment(
        "PO03",
        "Polera Oversize Mujer",
        "Poleras",
        "MUJER",
        "Norte Casual",
        "Confecciones Oriente",
        ("Beige", "Verde oliva"),
        "179",
        "84",
        6,
        "Polera amplia de hombro caído para mujer.",
        ("48", "56", "67", "22"),
    ),
    Garment(
        "PO04",
        "Polera Oversize Hombre",
        "Poleras",
        "HOMBRE",
        "Norte Casual",
        "Confecciones Oriente",
        ("Negro", "Verde oliva"),
        "179",
        "84",
        6,
        "Polera amplia de hombro caído para hombre.",
        ("52", "60", "75", "25"),
    ),
    Garment(
        "PL01",
        "Polo Clásico Mujer",
        "Polos",
        "MUJER",
        "Zenda Basics",
        "Textiles Andinos",
        ("Blanco", "Rosa palo"),
        "219",
        "105",
        5,
        "Polo piqué de corte femenino con cuello estructurado.",
        ("37", "46", "62", "19"),
    ),
    Garment(
        "PL02",
        "Polo Clásico Hombre",
        "Polos",
        "HOMBRE",
        "Zenda Basics",
        "Textiles Andinos",
        ("Blanco", "Azul marino"),
        "219",
        "105",
        5,
        "Polo piqué de corte masculino con cuello estructurado.",
        ("43", "52", "71", "22"),
    ),
    Garment(
        "PL03",
        "Polo Urban Mujer",
        "Polos",
        "MUJER",
        "Norte Casual",
        "Confecciones Oriente",
        ("Negro", "Rojo vino"),
        "239",
        "116",
        5,
        "Polo casual femenino de tejido liviano.",
        ("38", "48", "64", "20"),
    ),
    Garment(
        "PL04",
        "Polo Urban Hombre",
        "Polos",
        "HOMBRE",
        "Norte Casual",
        "Confecciones Oriente",
        ("Negro", "Verde oliva"),
        "239",
        "116",
        5,
        "Polo casual masculino de tejido liviano.",
        ("44", "54", "73", "23"),
    ),
    Garment(
        "BL01",
        "Blusa Siena",
        "Blusas",
        "MUJER",
        "Aura Mujer",
        "Moda Latina",
        ("Blanco", "Rosa palo"),
        "229",
        "112",
        6,
        "Blusa fluida de manga larga con cuello mao.",
        ("36", "46", "62", "58"),
    ),
    Garment(
        "BL02",
        "Blusa Alma",
        "Blusas",
        "MUJER",
        "Aura Mujer",
        "Moda Latina",
        ("Negro", "Beige"),
        "249",
        "121",
        5,
        "Blusa cruzada de manga tres cuartos.",
        ("37", "47", "60", "44"),
    ),
    Garment(
        "CM01",
        "Camisa Oxford Mujer",
        "Camisas",
        "MUJER",
        "Lino Sur",
        "Moda Latina",
        ("Blanco", "Celeste"),
        "279",
        "137",
        5,
        "Camisa clásica de corte femenino y manga larga.",
        ("38", "48", "66", "59"),
    ),
    Garment(
        "CM02",
        "Camisa Oxford Hombre",
        "Camisas",
        "HOMBRE",
        "Lino Sur",
        "Moda Latina",
        ("Blanco", "Celeste"),
        "289",
        "142",
        5,
        "Camisa clásica de corte masculino y manga larga.",
        ("45", "55", "76", "64"),
    ),
)


def _decimal(value: str | None, increment: Decimal = Decimal("0")) -> Decimal | None:
    return None if value is None else Decimal(value) + increment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Carga compras e inventario de demostración.")
    parser.add_argument("--yes", action="store_true", help="Omite la confirmación interactiva.")
    parser.add_argument(
        "--all-remaining",
        action="store_true",
        help="Carga las otras nueve empresas demo y omite Casa Elena.",
    )
    return parser


async def add(session, model):
    session.add(model)
    await session.flush()
    return model


async def get_or_add(session, model_type, condition, **values):
    existing = await session.scalar(select(model_type).where(condition))
    return existing if existing is not None else await add(session, model_type(**values))


def tenant_prefix(slug: str) -> str:
    """Produce un prefijo estable para identidades que son globalmente únicas."""
    return "".join(character for character in slug.upper() if character.isalnum())[:8]


async def run_seed(tenant_slug: str = TENANT_SLUG) -> tuple[str, dict[str, int]]:
    async with async_session_factory() as session:
        tenant = await session.scalar(
            select(Tenant)
            .where(Tenant.slug == tenant_slug)
            .execution_options(include_all_tenants=True)
        )
        if tenant is None:
            raise SeedError(f"No existe la empresa con slug {tenant_slug}.")

        prefix = tenant_prefix(tenant.slug)

        set_tenant_context(tenant.id_tenant)
        try:
            await apply_audit_context(
                session,
                AuditContext(
                    tenant_id=tenant.id_tenant,
                    origen="SISTEMA",
                    user_agent="seed_demo_inventory",
                    request_id=f"seed-inventory-{tenant.slug}-v1",
                ),
            )
            previous_product_ids = list(
                (
                    await session.scalars(
                        select(Producto.id_producto)
                        .join(VarianteProducto)
                        .join(
                            DetalleOrdenCompra,
                            DetalleOrdenCompra.id_variante == VarianteProducto.id_variante,
                        )
                        .join(OrdenCompra)
                        .where(OrdenCompra.observacion.in_(PREVIOUS_SEED_MARKERS))
                        .distinct()
                    )
                ).all()
            )
            if previous_product_ids:
                await session.execute(
                    update(VarianteProducto)
                    .where(VarianteProducto.id_producto.in_(previous_product_ids))
                    .values(activo=False)
                )
                await session.execute(
                    update(Producto)
                    .where(Producto.id_producto.in_(previous_product_ids))
                    .values(activo=False)
                )
            previous = await session.scalar(
                select(OrdenCompra.id_orden_compra).where(OrdenCompra.observacion == SEED_MARKER)
            )
            if previous is not None:
                raise AlreadySeededError(f"{tenant.nombre} ya tiene la carga inicial.")

            city = await session.scalar(
                select(Ciudad).where(
                    func.lower(Ciudad.nombre) == "santa cruz de la sierra",
                    func.lower(Ciudad.departamento) == "santa cruz",
                    func.lower(Ciudad.pais) == "bolivia",
                )
            )
            if city is None:
                city = await add(
                    session,
                    Ciudad(
                        nombre="Santa Cruz de la Sierra", departamento="Santa Cruz", pais="Bolivia"
                    ),
                )
            branch = await session.scalar(
                select(Sucursal).where(Sucursal.nombre == "Sucursal Principal")
            )
            if branch is None:
                branch = await add(
                    session,
                    Sucursal(
                        id_ciudad=city.id_ciudad,
                        nombre="Sucursal Principal",
                        direccion="Av. San Martín, Equipetrol",
                        telefono=f"71{tenant.id_tenant:06d}"[-8:],
                        hora_apertura=time(9, 0),
                        hora_cierre=time(20, 0),
                    ),
                )

            admin_id = await session.scalar(
                select(Usuario.id_usuario).where(
                    Usuario.correo == f"admin+{tenant.slug}@zentrysaas.store"
                )
            )
            categories = {
                name: await get_or_add(
                    session,
                    Categoria,
                    Categoria.nombre == name,
                    nombre=name,
                    descripcion=description,
                )
                for name, description in CATEGORIES.items()
            }
            brands = {
                name: await get_or_add(
                    session,
                    Marca,
                    Marca.nombre == name,
                    nombre=name,
                    pais_origen=data[0],
                    descripcion=data[1],
                )
                for name, data in BRANDS.items()
            }
            sizes = {
                code: await get_or_add(
                    session,
                    Talla,
                    Talla.codigo == code,
                    codigo=code,
                    orden=order,
                )
                for code, order in SIZES
            }
            colors = {
                name: await get_or_add(
                    session,
                    Color,
                    Color.nombre == name,
                    nombre=name,
                    codigo_hex=hex_code,
                )
                for name, hex_code in COLORS.items()
            }
            suppliers = {}
            for index, (name, data) in enumerate(SUPPLIERS.items(), start=1):
                suppliers[name] = await get_or_add(
                    session,
                    Proveedor,
                    Proveedor.nombre_comercial == name,
                    id_ciudad=city.id_ciudad,
                    nombre_comercial=name,
                    razon_social=data[0],
                    nit=f"{prefix}-{data[1].removeprefix('CE-')}",
                    telefono=f"69{tenant.id_tenant:04d}{index:02d}"[-8:],
                    correo=f"ventas{index}+{tenant.slug}@proveedor-demo.test",
                    direccion=f"Parque Industrial, módulo {index}",
                    nombre_contacto=data[2],
                    telefono_contacto=f"68{tenant.id_tenant:04d}{index:02d}"[-8:],
                )

            purchase_lines: dict[str, list[tuple[VarianteProducto, Garment]]] = {
                name: [] for name in suppliers
            }
            product_count = variant_count = 0
            for garment in GARMENTS:
                product = await add(
                    session,
                    Producto(
                        id_categoria=categories[garment.category].id_categoria,
                        id_marca=brands[garment.brand].id_marca,
                        nombre=garment.name,
                        descripcion=garment.description,
                        publico_objetivo=garment.audience,
                        permite_vestidor=True,
                    ),
                )
                product_count += 1
                await add(
                    session,
                    HistorialPrecio(
                        id_producto=product.id_producto,
                        precio=Decimal(garment.price),
                        creado_por=admin_id,
                    ),
                )
                await add(
                    session,
                    ProductoProveedor(
                        id_producto=product.id_producto,
                        id_proveedor=suppliers[garment.supplier].id_proveedor,
                        codigo_proveedor=f"{garment.supplier[:2].upper()}-{garment.code}",
                    ),
                )
                for size_index, (size_code, _) in enumerate(SIZES):
                    growth = Decimal(size_index - 2)
                    shoulders, chest, length, sleeve = garment.base_measurements
                    await add(
                        session,
                        MedidaTallaProducto(
                            id_producto=product.id_producto,
                            id_talla=sizes[size_code].id_talla,
                            ancho_hombros_cm=_decimal(shoulders, growth),
                            ancho_pecho_cm=_decimal(chest, growth * 2),
                            largo_prenda_cm=_decimal(length, growth),
                            largo_manga_cm=_decimal(sleeve, growth / 2),
                        ),
                    )
                    for color_index, color_name in enumerate(garment.colors, start=1):
                        sku = f"{prefix}-{garment.code}-{size_code}-{color_index:02d}"
                        barcode = (
                            f"779{tenant.id_tenant:04d}{product_count:02d}"
                            f"{size_index + 1}{color_index}26"
                        )
                        variant = await add(
                            session,
                            VarianteProducto(
                                id_producto=product.id_producto,
                                id_talla=sizes[size_code].id_talla,
                                id_color=colors[color_name].id_color,
                                sku=sku,
                                codigo_barras=barcode,
                            ),
                        )
                        purchase_lines[garment.supplier].append((variant, garment))
                        variant_count += 1

            receipt_count = 0
            total_units = 0
            for supplier_index, (supplier_name, lines) in enumerate(
                purchase_lines.items(), start=1
            ):
                order = await add(
                    session,
                    OrdenCompra(
                        id_proveedor=suppliers[supplier_name].id_proveedor,
                        id_sucursal=branch.id_sucursal,
                        estado="RECIBIDA",
                        fecha_estimada=date.today() + timedelta(days=7),
                        observacion=SEED_MARKER,
                    ),
                )
                receipt = await add(
                    session,
                    RecepcionMercaderia(
                        id_orden_compra=order.id_orden_compra,
                        id_sucursal=branch.id_sucursal,
                        estado="CONFIRMADA",
                        observacion="Mercadería inicial recibida completa.",
                    ),
                )
                receipt_count += 1
                for line_index, (variant, garment) in enumerate(lines, start=1):
                    quantity = garment.stock
                    cost = Decimal(garment.cost)
                    await add(
                        session,
                        DetalleOrdenCompra(
                            id_orden_compra=order.id_orden_compra,
                            id_variante=variant.id_variante,
                            cantidad=quantity,
                            costo_unitario_estimado=cost,
                        ),
                    )
                    detail = await add(
                        session,
                        DetalleRecepcion(
                            id_recepcion=receipt.id_recepcion,
                            id_variante=variant.id_variante,
                            cantidad_recibida=quantity,
                            costo_unitario=cost,
                        ),
                    )
                    lot = await add(
                        session,
                        LoteInventario(
                            id_detalle_recepcion=detail.id_detalle_recepcion,
                            id_sucursal=branch.id_sucursal,
                            id_variante=variant.id_variante,
                            numero_lote=(f"{prefix}-2026-{supplier_index:02d}-{line_index:03d}"),
                            cantidad_inicial=quantity,
                            cantidad_disponible=0,
                            costo_unitario=cost,
                        ),
                    )
                    inventory = await add(
                        session,
                        InventarioSucursal(
                            id_sucursal=branch.id_sucursal,
                            id_variante=variant.id_variante,
                            stock_minimo=2,
                        ),
                    )
                    movement = await add(
                        session,
                        MovimientoInventario(
                            id_inventario=inventory.id_inventario,
                            tipo_movimiento="ENTRADA_PROVEEDOR",
                            cantidad=quantity,
                            referencia_tipo="RECEPCION",
                            referencia_id=receipt.id_recepcion,
                            motivo=f"Carga inicial de inventario {tenant.nombre}",
                        ),
                    )
                    await add(
                        session,
                        MovimientoLote(
                            id_movimiento=movement.id_movimiento,
                            id_lote=lot.id_lote,
                            cantidad=quantity,
                            costo_unitario=cost,
                        ),
                    )
                    total_units += quantity

            await session.commit()
            return tenant.nombre, {
                "proveedores": len(suppliers),
                "marcas": len(brands),
                "categorias": len(categories),
                "productos": product_count,
                "variantes": variant_count,
                "recepciones": receipt_count,
                "unidades": total_units,
            }
        except Exception:
            await session.rollback()
            raise
        finally:
            clear_tenant_context()


async def async_main() -> int:
    args = build_parser().parse_args()
    slugs = REMAINING_DEMO_SLUGS if args.all_remaining else (TENANT_SLUG,)
    if not args.yes:
        scope = "las otras nueve empresas demo" if args.all_remaining else "Casa Elena"
        print(f"Se cargarán compras, catálogo e inventario para {scope}; sin imágenes.")
        phrase = "CARGAR 9 EMPRESAS" if args.all_remaining else "CARGAR CASA ELENA"
        confirmation = await asyncio.to_thread(input, f"Escribe {phrase} para confirmar: ")
        if confirmation.strip() != phrase:
            print("Operación cancelada; no se guardó ningún cambio.")
            return 1
    completed: list[tuple[str, dict[str, int]]] = []
    skipped: list[str] = []
    try:
        for slug in slugs:
            try:
                result = await run_seed(slug)
                completed.append(result)
                print(f"Carga completada: {result[0]}")
            except AlreadySeededError as exc:
                skipped.append(str(exc))
                print(f"Omitida: {exc}")
            except (SeedError, SQLAlchemyError) as exc:
                print(f"No se pudo cargar {slug}: {exc}")
                return 1
    finally:
        await engine.dispose()
    print(f"\nEmpresas cargadas: {len(completed)}; omitidas: {len(skipped)}")
    for name, result in completed:
        print(
            f"  {name}: {result['productos']} productos, {result['variantes']} variantes, "
            f"{result['unidades']} unidades"
        )
    print("Imágenes: 0 por empresa (listas para que las subas desde el panel)")
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print("\nOperación cancelada; no se guardó ningún cambio.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
