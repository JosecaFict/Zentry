"""Copia el catálogo público de Capricho Store y carga inventario de demostración."""

import argparse
import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.db.tenant_context import clear_tenant_context, database_scope, set_tenant_context
from app.integrations.cloudinary import CloudinaryError, CloudinaryStorage
from app.modules.auth.models import Sucursal
from app.modules.catalog.models import (
    Categoria,
    Coleccion,
    Color,
    HistorialPrecio,
    ImagenProducto,
    InventarioSucursal,
    Marca,
    MedidaTallaProducto,
    Producto,
    ProductoColeccion,
    ProductoTemporada,
    Talla,
    Temporada,
    VarianteProducto,
)
from app.modules.inventory.models import (
    DetalleRecepcion,
    LoteInventario,
    MovimientoInventario,
    MovimientoLote,
    ProductoProveedor,
    Proveedor,
    RecepcionMercaderia,
)
from app.modules.platform.models import Plan, Subscription, Tenant
from app.scripts.seed_demo_empresarial import DEMOS
from app.scripts.seed_demo_tenants import SeedError

UNITS_PER_PRODUCT = 30
MARKER = "Carga inicial catálogo Empresarial desde Capricho Store v1"
logger = logging.getLogger(__name__)
MASTER_DATA = (
    (Categoria, ("nombre",), ()),
    (Marca, ("nombre",), ()),
    (Color, ("nombre",), ()),
    (Talla, ("codigo",), ()),
    (Temporada, ("nombre", "anio", "fecha_inicio", "fecha_fin"), ()),
    (Coleccion, ("nombre", "id_temporada"), ("id_temporada",)),
)


def distribute_stock(variant_count: int, branch_index: int) -> list[int]:
    base, extra = divmod(UNITS_PER_PRODUCT, variant_count)
    return [
        base + ((index - branch_index) % variant_count < extra) for index in range(variant_count)
    ]


def copy_row(row, **overrides):
    columns = row.__table__.columns
    values = {
        column.key: getattr(row, column.key)
        for column in columns
        if not column.primary_key and column.key not in {"created_at", "updated_at"}
    }
    return type(row)(**(values | overrides))


async def rows(session, model, *filters):
    return list(
        await session.scalars(
            select(model)
            .where(*filters)
            .order_by(*model.__table__.primary_key.columns)
            .execution_options(include_all_tenants=True)
        )
    )


async def copy_masters(session, source_id, target_id):
    ids = {}
    for model, keys, foreign_keys in MASTER_DATA:
        pk = next(iter(model.__table__.primary_key.columns)).key
        source = await rows(session, model, model.id_tenant == source_id)
        existing = await rows(session, model, model.id_tenant == target_id)
        by_key = {tuple(getattr(row, key) for key in keys): row for row in existing}
        occupied_orders = {row.orden for row in existing} if model is Talla else set()
        for row in source:
            overrides = {key: ids.get((key, getattr(row, key))) for key in foreign_keys}
            key = tuple(overrides.get(name, getattr(row, name)) for name in keys)
            target = by_key.get(key)
            if target is None:
                if model is Talla:
                    order = row.orden
                    while order in occupied_orders:
                        order += 1
                    occupied_orders.add(order)
                    overrides["orden"] = order
                target = copy_row(row, id_tenant=target_id, **overrides)
                session.add(target)
                await session.flush()
                by_key[key] = target
            ids[pk, getattr(row, pk)] = getattr(target, pk)
    return ids


async def copy_images(session, storage, client, images, ids, uploaded):
    for image in images:
        url = urlsplit(image.secure_url)
        if url.scheme != "https" or url.netloc != "res.cloudinary.com":
            raise SeedError(f"La imagen {image.id_imagen} no tiene una URL de Cloudinary válida.")
        response = await client.get(image.secure_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0]
        if not content_type.startswith("image/") or not response.content:
            raise SeedError(f"Cloudinary no devolvió una imagen para {image.id_imagen}.")
        product_id = ids["id_producto", image.id_producto]
        asset = await storage.upload_product_image(
            product_id=product_id,
            content=response.content,
            filename=f"capricho-{image.id_imagen}.{image.formato or 'jpg'}",
            content_type=content_type,
        )
        uploaded.append(asset.public_id)
        session.add(
            copy_row(
                image,
                id_producto=product_id,
                id_color=ids.get(("id_color", image.id_color)),
                public_id=asset.public_id,
                secure_url=asset.secure_url,
                proveedor_storage="CLOUDINARY",
                formato=asset.formato,
                ancho_px=asset.ancho_px,
                alto_px=asset.alto_px,
            )
        )


async def load_stock(session, branches, variants_by_product, prices):
    for index, branch in enumerate(branches):
        receipt = RecepcionMercaderia(id_sucursal=branch.id_sucursal, observacion=MARKER)
        session.add(receipt)
        await session.flush()
        entries = [
            (variant, quantity, (prices[product_id] / 2).quantize(Decimal("0.01")))
            for product_id, variants in variants_by_product.items()
            for variant, quantity in zip(
                variants, distribute_stock(len(variants), index), strict=True
            )
            if quantity
        ]
        inventory = [
            InventarioSucursal(id_sucursal=branch.id_sucursal, id_variante=variant)
            for variant, _, _ in entries
        ]
        details = [
            DetalleRecepcion(
                id_recepcion=receipt.id_recepcion,
                id_variante=variant,
                cantidad_recibida=quantity,
                costo_unitario=cost,
            )
            for variant, quantity, cost in entries
        ]
        session.add_all(inventory + details)
        await session.flush()
        lots = []
        movements = []
        for detail, stock, (variant, quantity, cost) in zip(
            details, inventory, entries, strict=True
        ):
            lots.append(
                LoteInventario(
                    id_detalle_recepcion=detail.id_detalle_recepcion,
                    id_sucursal=branch.id_sucursal,
                    id_variante=variant,
                    numero_lote=f"EMP-{branch.id_sucursal}-{variant}",
                    cantidad_inicial=quantity,
                    cantidad_disponible=0,
                    costo_unitario=cost,
                )
            )
            movements.append(
                MovimientoInventario(
                    id_inventario=stock.id_inventario,
                    tipo_movimiento="ENTRADA_PROVEEDOR",
                    cantidad=quantity,
                    referencia_tipo="RECEPCION",
                    referencia_id=receipt.id_recepcion,
                    motivo=MARKER,
                )
            )
        session.add_all(lots + movements)
        await session.flush()
        session.add_all(
            [
                MovimientoLote(
                    id_movimiento=movement.id_movimiento,
                    id_lote=lot.id_lote,
                    cantidad=quantity,
                    costo_unitario=cost,
                )
                for movement, lot, (_, quantity, cost) in zip(movements, lots, entries, strict=True)
            ]
        )
        await session.flush()
        # Comprueba los efectos de ambos triggers antes de confirmar.
        expected = {variant: quantity for variant, quantity, _ in entries}
        for model, column in (
            (InventarioSucursal, InventarioSucursal.stock_fisico),
            (LoteInventario, LoteInventario.cantidad_disponible),
        ):
            amounts = await session.execute(
                select(model.id_variante, column).where(
                    model.id_sucursal == branch.id_sucursal,
                    model.id_variante.in_(expected),
                )
            )
            if dict(amounts.all()) != expected:
                raise SeedError(
                    f"El saldo de {model.__tablename__} no coincide en {branch.nombre}."
                )


async def seed(apply, client, uploaded):
    with database_scope("global"):
        async with async_session_factory() as session:
            if apply:
                await session.execute(text("SELECT pg_advisory_xact_lock(20261109, 41)"))
            source = await session.scalar(select(Tenant).where(Tenant.slug == "capricho-store"))
            if source is None:
                raise SeedError("No existe Capricho Store.")
            products = await rows(
                session, Producto, Producto.id_tenant == source.id_tenant, Producto.activo.is_(True)
            )
            product_ids = [product.id_producto for product in products]
            prices = {
                row.id_producto: row.precio
                for row in await rows(
                    session,
                    HistorialPrecio,
                    HistorialPrecio.id_producto.in_(product_ids),
                    HistorialPrecio.fecha_fin.is_(None),
                )
            }
            variants = await rows(
                session,
                VarianteProducto,
                VarianteProducto.id_producto.in_(product_ids),
                VarianteProducto.activo.is_(True),
            )
            variants_by_product = defaultdict(list)
            for variant in variants:
                variants_by_product[variant.id_producto].append(variant)
            if not products or any(
                not variants_by_product[p] or prices.get(p, 0) <= 0 for p in product_ids
            ):
                raise SeedError(
                    "Cada prenda activa necesita un precio vigente y una variante activa."
                )

            suppliers = await rows(session, Proveedor, Proveedor.id_tenant == source.id_tenant)
            images = await rows(
                session, ImagenProducto, ImagenProducto.id_producto.in_(product_ids)
            )
            links = {
                model: await rows(session, model, model.id_producto.in_(product_ids))
                for model in (
                    ProductoProveedor,
                    ProductoTemporada,
                    ProductoColeccion,
                    MedidaTallaProducto,
                )
            }
            targets = []
            for demo, count in DEMOS:
                target = await session.scalar(
                    select(Tenant)
                    .join(Subscription, Subscription.id_tenant == Tenant.id_tenant)
                    .join(Plan, Plan.id_plan == Subscription.id_plan)
                    .where(Tenant.slug == demo.slug, Plan.codigo == "EMPRESARIAL")
                )
                if target is None:
                    raise SeedError(f"{demo.nombre} debe tener asignado el plan Empresarial.")
                branches = await rows(
                    session,
                    Sucursal,
                    Sucursal.id_tenant == target.id_tenant,
                    Sucursal.activo.is_(True),
                )
                if len(branches) != count:
                    raise SeedError(f"{demo.nombre} debe tener {count} sucursales activas.")
                loaded = await rows(
                    session,
                    RecepcionMercaderia,
                    RecepcionMercaderia.id_tenant == target.id_tenant,
                    RecepcionMercaderia.observacion == MARKER,
                )
                if loaded:
                    if sorted(row.id_sucursal for row in loaded) != sorted(
                        branch.id_sucursal for branch in branches
                    ):
                        raise SeedError(f"La carga registrada de {demo.nombre} requiere revisión.")
                    print(f"{demo.nombre}: carga ya registrada.")
                    continue
                for model in (Producto, Proveedor, InventarioSucursal):
                    existing = await session.scalar(
                        select(model.__table__.c.id_tenant)
                        .where(model.id_tenant == target.id_tenant)
                        .limit(1)
                        .execution_options(include_all_tenants=True)
                    )
                    if existing is not None:
                        raise SeedError(f"{demo.nombre} ya tiene datos en {model.__tablename__}.")
                targets.append((target, branches))
                print(
                    f"{demo.nombre}: {len(suppliers)} proveedores, {len(products)} prendas, "
                    f"{len(images)} fotos y {count * len(products) * UNITS_PER_PRODUCT} unidades "
                    f"en {count} sucursales."
                )

            if not apply or not targets:
                return
            cloudinary_url = get_settings().cloudinary_url
            if images and not cloudinary_url:
                raise SeedError("Configura CLOUDINARY_URL antes de copiar las fotos.")
            storage = CloudinaryStorage(cloudinary_url) if images else None
            try:
                for target, branches in targets:
                    set_tenant_context(target.id_tenant)
                    await apply_audit_context(
                        session,
                        AuditContext(
                            tenant_id=target.id_tenant,
                            origen="SISTEMA",
                            user_agent="seed_empresarial_catalog",
                        ),
                    )
                    ids = await copy_masters(session, source.id_tenant, target.id_tenant)
                    for supplier in suppliers:
                        new = copy_row(
                            supplier,
                            id_tenant=target.id_tenant,
                            nit=f"DEMO-{target.id_tenant}-{supplier.id_proveedor}",
                            telefono=None,
                            correo=None,
                            direccion=None,
                            nombre_contacto=None,
                            telefono_contacto=None,
                            correo_contacto=None,
                        )
                        session.add(new)
                        await session.flush()
                        ids["id_proveedor", supplier.id_proveedor] = new.id_proveedor
                    for product in products:
                        new = copy_row(
                            product,
                            id_tenant=target.id_tenant,
                            id_categoria=ids["id_categoria", product.id_categoria],
                            id_marca=ids["id_marca", product.id_marca],
                        )
                        session.add(new)
                        await session.flush()
                        ids["id_producto", product.id_producto] = new.id_producto
                        session.add(
                            HistorialPrecio(
                                id_producto=new.id_producto, precio=prices[product.id_producto]
                            )
                        )
                    target_variants = defaultdict(list)
                    for variant in variants:
                        new = copy_row(
                            variant,
                            id_producto=ids["id_producto", variant.id_producto],
                            id_talla=ids["id_talla", variant.id_talla],
                            id_color=ids["id_color", variant.id_color],
                            sku=f"EMP-{target.id_tenant}-{variant.id_variante}",
                            codigo_barras=None,
                        )
                        session.add(new)
                        target_variants[variant.id_producto].append(new)
                    for model, foreign_key in (
                        (ProductoProveedor, "id_proveedor"),
                        (ProductoTemporada, "id_temporada"),
                        (ProductoColeccion, "id_coleccion"),
                        (MedidaTallaProducto, "id_talla"),
                    ):
                        session.add_all(
                            [
                                copy_row(
                                    row,
                                    id_producto=ids["id_producto", row.id_producto],
                                    **{foreign_key: ids[foreign_key, getattr(row, foreign_key)]},
                                )
                                for row in links[model]
                            ]
                        )
                    await session.flush()
                    if storage:
                        await copy_images(session, storage, client, images, ids, uploaded)
                    await load_stock(
                        session,
                        branches,
                        {
                            product_id: [item.id_variante for item in items]
                            for product_id, items in target_variants.items()
                        },
                        prices,
                    )
            except Exception:
                await session.rollback()
                if storage:
                    for public_id in uploaded:
                        await storage.destroy(public_id)
                raise
            finally:
                clear_tenant_context()
            await session.commit()
            print("Carga confirmada en ambas empresas.")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="Guarda la carga inicial.")
    args = parser.parse_args()
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            await seed(args.aplicar, client, [])
        if not args.aplicar:
            print("Vista previa. Agrega --aplicar para ejecutar la carga.")
    except (SeedError, CloudinaryError) as exc:
        raise SystemExit(str(exc)) from None
    except SQLAlchemyError as exc:
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None)
        logger.error("Error PostgreSQL: %s (SQLSTATE %s)", type(exc).__name__, sqlstate or "-")
        raise SystemExit("Falló la carga en PostgreSQL.") from None
    except httpx.HTTPError as exc:
        logger.error("Error al leer una foto de Capricho Store: %s", type(exc).__name__)
        raise SystemExit("Falló la descarga de una imagen desde Cloudinary.") from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
