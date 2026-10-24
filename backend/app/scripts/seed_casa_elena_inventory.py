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

from sqlalchemy import func, select
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
SEED_MARKER = "CARGA INICIAL CASA ELENA 2026-01"


class SeedError(RuntimeError):
    """Impide que se guarde una carga incompleta o duplicada."""


@dataclass(frozen=True, slots=True)
class Garment:
    code: str
    name: str
    category: str
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
    "Blusas": "Blusas femeninas para uso casual y formal.",
    "Camisas": "Camisas femeninas de corte clásico y relajado.",
    "Vestidos": "Vestidos para ocasiones casuales y especiales.",
    "Pantalones": "Pantalones femeninos de distintos cortes.",
    "Faldas": "Faldas femeninas casuales y formales.",
    "Chaquetas": "Prendas exteriores y de media estación.",
}
BRANDS = {
    "Elena Studio": ("Bolivia", "Línea contemporánea exclusiva de Casa Elena."),
    "Aura Mujer": ("Colombia", "Diseños femeninos versátiles y urbanos."),
    "Lino Sur": ("Perú", "Prendas frescas con fibras naturales."),
    "Nativa Denim": ("Bolivia", "Denim y prendas casuales de producción regional."),
}
SUPPLIERS = {
    "Textiles Andinos": ("Textiles Andinos S.R.L.", "CE-PROV-001", "María Fernanda Ríos"),
    "Moda Latina": ("Importadora Moda Latina Ltda.", "CE-PROV-002", "Carolina Suárez"),
    "Denim Bolivia": ("Confecciones Denim Bolivia S.R.L.", "CE-PROV-003", "Andrea Molina"),
}
GARMENTS = (
    Garment(
        "BL01",
        "Blusa Siena",
        "Blusas",
        "Elena Studio",
        "Textiles Andinos",
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
        "Camisa Clara",
        "Camisas",
        "Lino Sur",
        "Textiles Andinos",
        ("Blanco", "Celeste"),
        "279",
        "137",
        5,
        "Camisa de lino suave con botones nacarados.",
        ("38", "48", "66", "59"),
    ),
    Garment(
        "CM02",
        "Camisa Olivia",
        "Camisas",
        "Elena Studio",
        "Textiles Andinos",
        ("Verde oliva", "Beige"),
        "269",
        "132",
        4,
        "Camisa relajada con bolsillos frontales.",
        ("39", "50", "68", "57"),
    ),
    Garment(
        "VE01",
        "Vestido Aurora",
        "Vestidos",
        "Aura Mujer",
        "Moda Latina",
        ("Rojo vino", "Negro"),
        "459",
        "226",
        4,
        "Vestido midi cruzado con cintura ajustable.",
        ("36", "45", "118", "25"),
    ),
    Garment(
        "VE02",
        "Vestido Magnolia",
        "Vestidos",
        "Elena Studio",
        "Moda Latina",
        ("Rosa palo", "Beige"),
        "429",
        "211",
        4,
        "Vestido camisero midi de caída ligera.",
        ("37", "47", "115", "23"),
    ),
    Garment(
        "PA01",
        "Pantalón Victoria",
        "Pantalones",
        "Aura Mujer",
        "Moda Latina",
        ("Negro", "Beige"),
        "349",
        "171",
        6,
        "Pantalón sastre de tiro alto y pierna recta.",
        (None, "36", "102", None),
    ),
    Garment(
        "PA02",
        "Jean Emilia",
        "Pantalones",
        "Nativa Denim",
        "Denim Bolivia",
        ("Azul marino", "Negro"),
        "379",
        "189",
        7,
        "Jean de tiro alto con corte recto.",
        (None, "35", "104", None),
    ),
    Garment(
        "FA01",
        "Falda Julieta",
        "Faldas",
        "Elena Studio",
        "Textiles Andinos",
        ("Negro", "Rojo vino"),
        "289",
        "142",
        5,
        "Falda midi plisada con pretina cómoda.",
        (None, "34", "78", None),
    ),
    Garment(
        "FA02",
        "Falda Serena",
        "Faldas",
        "Lino Sur",
        "Textiles Andinos",
        ("Beige", "Verde oliva"),
        "299",
        "147",
        5,
        "Falda evasé de lino con bolsillos laterales.",
        (None, "35", "75", None),
    ),
    Garment(
        "CH01",
        "Blazer Renata",
        "Chaquetas",
        "Aura Mujer",
        "Moda Latina",
        ("Negro", "Beige"),
        "549",
        "269",
        3,
        "Blazer estructurado de un botón y corte moderno.",
        ("39", "48", "70", "60"),
    ),
    Garment(
        "CH02",
        "Chaqueta Amelia",
        "Chaquetas",
        "Nativa Denim",
        "Denim Bolivia",
        ("Azul marino", "Blanco"),
        "489",
        "241",
        4,
        "Chaqueta denim corta de acabado suave.",
        ("40", "49", "55", "58"),
    ),
)


def _decimal(value: str | None, increment: Decimal = Decimal("0")) -> Decimal | None:
    return None if value is None else Decimal(value) + increment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Carga compras e inventario para Casa Elena.")
    parser.add_argument("--yes", action="store_true", help="Omite la confirmación interactiva.")
    return parser


async def add(session, model):
    session.add(model)
    await session.flush()
    return model


async def run_seed() -> dict[str, int]:
    async with async_session_factory() as session:
        tenant = await session.scalar(
            select(Tenant)
            .where(Tenant.slug == TENANT_SLUG)
            .execution_options(include_all_tenants=True)
        )
        if tenant is None:
            raise SeedError("No existe la empresa Casa Elena (slug casa-elena).")

        set_tenant_context(tenant.id_tenant)
        try:
            await apply_audit_context(
                session,
                AuditContext(
                    tenant_id=tenant.id_tenant,
                    origen="SISTEMA",
                    user_agent="seed_casa_elena_inventory",
                    request_id="seed-casa-elena-inventory-v1",
                ),
            )
            previous = await session.scalar(
                select(OrdenCompra.id_orden_compra).where(OrdenCompra.observacion == SEED_MARKER)
            )
            if previous is not None:
                raise SeedError("La carga inicial de Casa Elena ya fue ejecutada.")

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
                        telefono="71001001",
                        hora_apertura=time(9, 0),
                        hora_cierre=time(20, 0),
                    ),
                )

            admin_id = await session.scalar(
                select(Usuario.id_usuario).where(
                    Usuario.correo == "admin+casa-elena@zentrysaas.store"
                )
            )
            categories = {
                name: await add(session, Categoria(nombre=name, descripcion=description))
                for name, description in CATEGORIES.items()
            }
            brands = {
                name: await add(
                    session,
                    Marca(nombre=name, pais_origen=data[0], descripcion=data[1]),
                )
                for name, data in BRANDS.items()
            }
            sizes = {
                code: await add(session, Talla(codigo=code, orden=order)) for code, order in SIZES
            }
            colors = {
                name: await add(session, Color(nombre=name, codigo_hex=hex_code))
                for name, hex_code in COLORS.items()
            }
            suppliers = {}
            for index, (name, data) in enumerate(SUPPLIERS.items(), start=1):
                suppliers[name] = await add(
                    session,
                    Proveedor(
                        id_ciudad=city.id_ciudad,
                        nombre_comercial=name,
                        razon_social=data[0],
                        nit=data[1],
                        telefono=f"6900200{index}",
                        correo=f"ventas{index}@proveedor-demo.test",
                        direccion=f"Parque Industrial, módulo {index}",
                        nombre_contacto=data[2],
                        telefono_contacto=f"6900300{index}",
                    ),
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
                        publico_objetivo="MUJER",
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
                        sku = f"CE-{garment.code}-{size_code}-{color_index:02d}"
                        barcode = f"779{product_count:03d}{size_index + 1:02d}{color_index:02d}26"
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
                            numero_lote=f"CE-2026-{supplier_index:02d}-{line_index:03d}",
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
                            motivo="Carga inicial de inventario Casa Elena",
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
            return {
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
    if not args.yes:
        print(
            "Se cargarán compras, catálogo e inventario para Casa Elena; "
            "las imágenes quedarán vacías."
        )
        confirmation = await asyncio.to_thread(input, "Escribe CARGAR CASA ELENA para confirmar: ")
        if confirmation.strip() != "CARGAR CASA ELENA":
            print("Operación cancelada; no se guardó ningún cambio.")
            return 1
    try:
        result = await run_seed()
    except (SeedError, SQLAlchemyError) as exc:
        print(f"No se realizó la carga: {exc}")
        return 1
    finally:
        await engine.dispose()
    print("\nCarga de Casa Elena completada correctamente:")
    for label, value in result.items():
        print(f"  {label.capitalize()}: {value}")
    print("  Imágenes: 0 (listas para que las subas desde el panel)")
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print("\nOperación cancelada; no se guardó ningún cambio.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
