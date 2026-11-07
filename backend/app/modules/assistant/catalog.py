"""Read-only, tenant-scoped product facts for the shopping advisor."""

import re
import unicodedata
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assistant.schemas import AssistantProduct
from app.modules.commerce.repository import CommerceRepository

COLORS = (
    "verde",
    "azul",
    "rojo",
    "negro",
    "blanco",
    "gris",
    "amarillo",
    "rosa",
    "rosado",
    "morado",
    "violeta",
    "naranja",
    "beige",
    "marron",
    "cafe",
    "celeste",
    "turquesa",
)


def normalized_words(value: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(re.findall(r"[a-z]+", without_accents))


def requested_color(question: str) -> str | None:
    words = normalized_words(question)
    return next((color for color in COLORS if re.search(rf"\b{color}\b", words)), None)


def matches_color(product: AssistantProduct, color: str) -> bool:
    return any(re.search(rf"\b{color}\b", normalized_words(name)) for name in product.colores)


def shopping_filters(
    question: str,
) -> tuple[str | None, Decimal | None, Decimal | None, str | None]:
    normalized = question.casefold()
    category = next(
        (
            code
            for word, code in (
                ("polera", "POLERA"),
                ("camiseta", "POLERA"),
                ("camisa", "CAMISA"),
                ("polo", "POLO"),
                ("blusa", "BLUSA"),
            )
            if word in normalized
        ),
        None,
    )
    size_match = re.search(r"\btalla\s+([a-z0-9]{1,4})\b", normalized)
    size = size_match.group(1).upper() if size_match else None
    minimum = maximum = None
    if any(word in normalized for word in ("precio", "presupuesto", "bs", "boliviano", "cuesta")):
        amounts = [
            Decimal(value.replace(",", "."))
            for value in re.findall(r"(?<!\d)\d{2,5}(?:[.,]\d{1,2})?(?!\d)", normalized)
        ]
        if len(amounts) >= 2:
            minimum, maximum = sorted(amounts[:2])
        elif amounts:
            if any(
                word in normalized for word in ("máximo", "maximo", "hasta", "menos de", "tope")
            ):
                maximum = amounts[0]
            elif any(word in normalized for word in ("mínimo", "minimo", "desde", "más de")):
                minimum = amounts[0]
            else:
                maximum = amounts[0]
    return category, minimum, maximum, size


class ShoppingCatalog:
    def __init__(self, session: AsyncSession, tenant_id: int) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def available(
        self, *, category: str | None = None, ids: list[int] | None = None
    ) -> list[AssistantProduct]:
        rows = (
            (
                await self.session.execute(
                    text("""
            SELECT p.id_producto, p.nombre, c.nombre AS categoria,
                   m.nombre AS marca, hp.precio, p.permite_vestidor,
                   img.secure_url AS imagen_url,
                   array_agg(DISTINCT t.codigo) AS tallas,
                   array_agg(DISTINCT co.nombre) AS colores,
                   SUM(GREATEST(i.stock_fisico - i.stock_reservado, 0))::int AS disponible
              FROM capricho.producto p
              JOIN capricho.categoria c ON c.id_categoria = p.id_categoria
                  AND c.id_tenant = :tenant AND c.activo
              JOIN capricho.marca m ON m.id_marca = p.id_marca
                  AND m.id_tenant = :tenant AND m.activo
              JOIN capricho.historial_precio hp ON hp.id_producto = p.id_producto
                  AND hp.fecha_fin IS NULL
              JOIN capricho.variante_producto v ON v.id_producto = p.id_producto AND v.activo
              JOIN capricho.talla t ON t.id_talla = v.id_talla AND t.id_tenant = :tenant
              JOIN capricho.color co ON co.id_color = v.id_color AND co.id_tenant = :tenant
              JOIN capricho.inventario_sucursal i ON i.id_variante = v.id_variante
                  AND i.id_tenant = :tenant AND i.stock_fisico > i.stock_reservado
              LEFT JOIN LATERAL (
                  SELECT secure_url FROM capricho.imagen_producto im
                   WHERE im.id_producto = p.id_producto AND im.tipo = 'CATALOGO'
                   ORDER BY im.es_principal DESC, im.orden, im.id_imagen LIMIT 1
              ) img ON true
             WHERE p.id_tenant = :tenant AND p.activo
               AND (CAST(:category AS TEXT) IS NULL OR upper(c.nombre) = :category)
               AND (CAST(:ids AS BIGINT[]) IS NULL OR p.id_producto = ANY(CAST(:ids AS BIGINT[])))
             GROUP BY p.id_producto, p.nombre, c.nombre, m.nombre,
                      hp.precio, p.permite_vestidor, img.secure_url
            HAVING SUM(GREATEST(i.stock_fisico - i.stock_reservado, 0)) > 0
             ORDER BY p.id_producto LIMIT 300
        """),
                    {"tenant": self.tenant_id, "category": category, "ids": ids},
                )
            )
            .mappings()
            .all()
        )
        discounts = await CommerceRepository(self.session).get_active_discounts_for_products(
            [row["id_producto"] for row in rows]
        )
        products = []
        for row in rows:
            price = row["precio"]
            discount = discounts.get(row["id_producto"])
            if discount:
                price = (price * (Decimal("1") - discount[0] / Decimal("100"))).quantize(
                    Decimal("0.01")
                )
            products.append(
                AssistantProduct(
                    id_producto=row["id_producto"],
                    nombre=row["nombre"],
                    categoria=row["categoria"],
                    marca=row["marca"],
                    precio=price,
                    precio_original=row["precio"] if discount else None,
                    descuento_porcentaje=discount[0] if discount else None,
                    promocion_nombre=discount[2] if discount else None,
                    imagen_url=row["imagen_url"],
                    tallas=sorted(row["tallas"]),
                    colores=sorted(row["colores"]),
                    permite_vestidor=row["permite_vestidor"],
                )
            )
        return products

    async def for_question(
        self,
        question: str,
        prioritize_ids: list[int] | None = None,
        limit: int = 40,
        restrict_to_prior: bool = False,
    ) -> list[AssistantProduct]:
        category, minimum, maximum, size = shopping_filters(question)
        color = requested_color(question)
        products = await self.available(
            category=category,
            ids=prioritize_ids if restrict_to_prior and prioritize_ids else None,
        )
        if prioritize_ids and not restrict_to_prior:
            previous = await self.for_ids(prioritize_ids)
            known = {item.id_producto for item in previous}
            products = previous + [item for item in products if item.id_producto not in known]
        return [
            item
            for item in products
            if (category is None or item.categoria.upper() == category)
            and (minimum is None or item.precio >= minimum)
            and (maximum is None or item.precio <= maximum)
            and (size is None or size in item.tallas)
            and (color is None or matches_color(item, color))
        ][:limit]

    async def for_ids(self, ids: list[int]) -> list[AssistantProduct]:
        if not ids:
            return []
        products = {item.id_producto: item for item in await self.available(ids=ids[:300])}
        return [products[product_id] for product_id in ids[:300] if product_id in products]
