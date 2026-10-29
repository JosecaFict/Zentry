from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.schemas import (
    BranchSalesItem,
    BranchSalesReport,
    CategoryRevenueItem,
    CategoryRevenueReport,
    CustomerPerformance,
    CustomerReport,
    InventoryItem,
    InventoryReport,
    ProductPerformance,
    ProductReport,
    SalesPoint,
    SalesReport,
)

ZERO = Decimal("0.00")


class ReportsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _range(date_from: date, date_to: date) -> tuple[datetime, datetime]:
        return (
            datetime.combine(date_from, time.min, tzinfo=UTC),
            datetime.combine(date_to, time.max, tzinfo=UTC),
        )

    @staticmethod
    def summarize_sales(date_from: date, date_to: date, rows: list[dict]) -> SalesReport:
        points = [SalesPoint(**row) for row in rows]
        total_sales = sum(row.ventas for row in points)
        total_units = sum(row.unidades for row in points)
        revenue = sum((row.ingresos for row in points), ZERO)
        return SalesReport(
            desde=date_from,
            hasta=date_to,
            total_ventas=total_sales,
            total_unidades=total_units,
            ingresos=revenue,
            ticket_promedio=(
                (revenue / total_sales).quantize(Decimal("0.01"))
                if total_sales
                else ZERO
            ),
            serie=points,
        )

    @staticmethod
    def summarize_inventory(rows: list[dict]) -> InventoryReport:
        items = [InventoryItem(**row) for row in rows]
        return InventoryReport(
            unidades_disponibles=sum(item.stock_disponible for item in items),
            valor_total=sum((item.valor_inventario for item in items), ZERO),
            items_criticos=sum(1 for item in items if item.critico),
            items=items,
        )

    async def sales(
        self, tenant_id: int, date_from: date, date_to: date, branch_id: int | None
    ) -> SalesReport:
        start, end = self._range(date_from, date_to)
        result = await self.session.execute(text("""
            SELECT v.fecha_venta::date AS fecha,
                   count(DISTINCT v.id_venta)::int AS ventas,
                   coalesce(sum(d.cantidad), 0)::int AS unidades,
                   coalesce(sum(d.subtotal), 0)::numeric(12,2) AS ingresos
              FROM capricho.venta v
              JOIN capricho.detalle_venta d ON d.id_venta = v.id_venta
             WHERE v.estado = 'PAGADA'
               AND v.id_tenant = :tenant_id
               AND v.fecha_venta BETWEEN :start AND :end
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
             GROUP BY v.fecha_venta::date
             ORDER BY fecha
        """), {
            "tenant_id": tenant_id,
            "start": start,
            "end": end,
            "branch_id": branch_id,
        })
        rows = result.mappings().all()
        return self.summarize_sales(date_from, date_to, rows)

    async def sales_by_branch(
        self,
        tenant_id: int,
        date_from: date,
        date_to: date,
        branch_id: int | None,
    ) -> BranchSalesReport:
        start, end = self._range(date_from, date_to)
        rows = (await self.session.execute(text("""
            SELECT s.id_sucursal, s.nombre AS sucursal,
                   count(DISTINCT v.id_venta)::int AS ventas,
                   coalesce(sum(d.cantidad), 0)::int AS unidades,
                   coalesce(sum(d.subtotal), 0)::numeric(12,2) AS ingresos
              FROM capricho.venta v
              JOIN capricho.sucursal s ON s.id_sucursal = v.id_sucursal
              JOIN capricho.detalle_venta d ON d.id_venta = v.id_venta
             WHERE v.estado = 'PAGADA'
               AND v.id_tenant = :tenant_id
               AND s.id_tenant = :tenant_id
               AND v.fecha_venta BETWEEN :start AND :end
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
             GROUP BY s.id_sucursal, s.nombre
             ORDER BY ingresos DESC, ventas DESC, s.nombre
        """), {
            "tenant_id": tenant_id,
            "start": start,
            "end": end,
            "branch_id": branch_id,
        })).mappings().all()
        total_revenue = sum((row["ingresos"] for row in rows), ZERO)
        total_sales = sum(row["ventas"] for row in rows)
        total_units = sum(row["unidades"] for row in rows)
        items = [
            BranchSalesItem(
                **row,
                participacion=(
                    (row["ingresos"] * Decimal("100") / total_revenue).quantize(
                        Decimal("0.01")
                    )
                    if total_revenue
                    else ZERO
                ),
            )
            for row in rows
        ]
        return BranchSalesReport(
            desde=date_from,
            hasta=date_to,
            total_ventas=total_sales,
            total_unidades=total_units,
            ingresos=total_revenue,
            sucursales=items,
        )

    async def products(
        self,
        tenant_id: int,
        date_from: date,
        date_to: date,
        branch_id: int | None,
        limit: int,
        category: str | None = None,
        product: str | None = None,
    ) -> ProductReport:
        start, end = self._range(date_from, date_to)
        result = await self.session.execute(text("""
            SELECT p.id_producto, p.nombre AS producto, c.nombre AS categoria,
                   sum(d.cantidad)::int AS unidades,
                   sum(d.subtotal)::numeric(12,2) AS ingresos
              FROM capricho.venta v
              JOIN capricho.detalle_venta d ON d.id_venta = v.id_venta
              JOIN capricho.variante_producto vp ON vp.id_variante = d.id_variante
              JOIN capricho.producto p ON p.id_producto = vp.id_producto
              JOIN capricho.categoria c ON c.id_categoria = p.id_categoria
             WHERE v.estado = 'PAGADA'
               AND v.id_tenant = :tenant_id
               AND v.fecha_venta BETWEEN :start AND :end
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
               AND (CAST(:category AS VARCHAR) IS NULL OR lower(c.nombre) = lower(:category))
               AND (CAST(:product AS VARCHAR) IS NULL OR lower(p.nombre) = lower(:product))
             GROUP BY p.id_producto, p.nombre, c.nombre
             ORDER BY ingresos DESC, unidades DESC, p.nombre
             LIMIT :limit
        """), {
            "tenant_id": tenant_id,
            "start": start,
            "end": end,
            "branch_id": branch_id,
            "category": category,
            "product": product,
            "limit": limit,
        })
        rows = result.mappings().all()
        return ProductReport(
            desde=date_from,
            hasta=date_to,
            productos=[
                ProductPerformance(posicion=index, **row)
                for index, row in enumerate(rows, start=1)
            ],
        )

    async def inventory(
        self,
        tenant_id: int,
        branch_id: int | None,
        critical_only: bool,
        category: str | None = None,
        product: str | None = None,
    ) -> InventoryReport:
        rows = (await self.session.execute(text("""
            SELECT vp.id_variante, p.nombre AS producto, c.nombre AS categoria,
                   t.codigo AS talla, co.nombre AS color, vp.sku, s.nombre AS sucursal,
                   i.stock_fisico, i.stock_reservado,
                   (i.stock_fisico - i.stock_reservado)::int AS stock_disponible,
                   i.stock_minimo,
                   coalesce(l.costo_promedio, 0)::numeric(12,2) AS costo_promedio,
                   ((i.stock_fisico - i.stock_reservado)
                       * coalesce(l.costo_promedio, 0))::numeric(14,2)
                       AS valor_inventario,
                   (i.stock_fisico - i.stock_reservado <= i.stock_minimo) AS critico
              FROM capricho.inventario_sucursal i
              JOIN capricho.sucursal s ON s.id_sucursal = i.id_sucursal
              JOIN capricho.variante_producto vp ON vp.id_variante = i.id_variante
              JOIN capricho.producto p ON p.id_producto = vp.id_producto
              JOIN capricho.categoria c ON c.id_categoria = p.id_categoria
              JOIN capricho.talla t ON t.id_talla = vp.id_talla
              JOIN capricho.color co ON co.id_color = vp.id_color
              LEFT JOIN LATERAL (
                  SELECT sum(li.cantidad_disponible * li.costo_unitario)
                             / nullif(sum(li.cantidad_disponible), 0) AS costo_promedio
                    FROM capricho.lote_inventario li
                   WHERE li.id_sucursal = i.id_sucursal
                     AND li.id_variante = i.id_variante
                     AND li.activo = true
              ) l ON true
             WHERE p.activo = true AND vp.activo = true
               AND i.id_tenant = :tenant_id
               AND p.id_tenant = :tenant_id
               AND c.id_tenant = :tenant_id
               AND (CAST(:branch_id AS BIGINT) IS NULL OR i.id_sucursal = :branch_id)
               AND (CAST(:category AS VARCHAR) IS NULL OR lower(c.nombre) = lower(:category))
               AND (CAST(:product AS VARCHAR) IS NULL OR lower(p.nombre) = lower(:product))
               AND (CAST(:critical_only AS BOOLEAN) = false
                    OR i.stock_fisico - i.stock_reservado <= i.stock_minimo)
             ORDER BY critico DESC, stock_disponible, p.nombre, vp.sku
        """), {
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "critical_only": critical_only,
            "category": category,
            "product": product,
        })).mappings().all()
        return self.summarize_inventory(rows)

    async def revenue_by_category(
        self,
        tenant_id: int,
        date_from: date,
        date_to: date,
        branch_id: int | None,
        category: str | None = None,
    ) -> CategoryRevenueReport:
        start, end = self._range(date_from, date_to)
        rows = (await self.session.execute(text("""
            SELECT c.id_categoria, c.nombre AS categoria,
                   coalesce(sum(d.cantidad), 0)::int AS unidades,
                   coalesce(sum(d.subtotal), 0)::numeric(12,2) AS ingresos
              FROM capricho.venta v
              JOIN capricho.detalle_venta d ON d.id_venta = v.id_venta
              JOIN capricho.variante_producto vp ON vp.id_variante = d.id_variante
              JOIN capricho.producto p ON p.id_producto = vp.id_producto
              JOIN capricho.categoria c ON c.id_categoria = p.id_categoria
             WHERE v.estado = 'PAGADA'
               AND v.id_tenant = :tenant_id
               AND p.id_tenant = :tenant_id
               AND c.id_tenant = :tenant_id
               AND v.fecha_venta BETWEEN :start AND :end
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
               AND (CAST(:category AS VARCHAR) IS NULL OR lower(c.nombre) = lower(:category))
             GROUP BY c.id_categoria, c.nombre
             ORDER BY ingresos DESC, unidades DESC, c.nombre
        """), {
            "tenant_id": tenant_id,
            "start": start,
            "end": end,
            "branch_id": branch_id,
            "category": category,
        })).mappings().all()
        total_revenue = sum((row["ingresos"] for row in rows), ZERO)
        total_units = sum(row["unidades"] for row in rows)
        items = [
            CategoryRevenueItem(
                **row,
                participacion=(
                    (row["ingresos"] * Decimal("100") / total_revenue).quantize(
                        Decimal("0.01")
                    )
                    if total_revenue
                    else ZERO
                ),
            )
            for row in rows
        ]
        return CategoryRevenueReport(
            desde=date_from,
            hasta=date_to,
            total_unidades=total_units,
            ingresos=total_revenue,
            categorias=items,
        )

    async def resolve_branch_id(self, tenant_id: int, branch_name: str) -> int | None:
        result = await self.session.execute(text("""
            SELECT id_sucursal
              FROM capricho.sucursal
             WHERE id_tenant = :tenant_id
               AND activo = true
               AND regexp_replace(lower(nombre), '^sucursal[[:space:]]+', '') =
                   regexp_replace(lower(:branch_name), '^sucursal[[:space:]]+', '')
             LIMIT 1
        """), {"tenant_id": tenant_id, "branch_name": branch_name.strip()})
        value = result.scalar_one_or_none()
        return int(value) if value is not None else None

    async def customers(
        self,
        tenant_id: int,
        date_from: date,
        date_to: date,
        branch_id: int | None,
        limit: int,
    ) -> CustomerReport:
        start, end = self._range(date_from, date_to)
        result = await self.session.execute(text("""
            SELECT c.id_cliente, concat_ws(' ', u.nombres, u.apellidos) AS cliente, u.correo,
                   count(DISTINCT v.id_venta)::int AS compras,
                   coalesce(sum(d.unidades), 0)::int AS unidades,
                   sum(v.total)::numeric(12,2) AS gasto_total,
                   avg(v.total)::numeric(12,2) AS ticket_promedio,
                   max(v.fecha_venta)::date AS ultima_compra
              FROM capricho.cliente c
              JOIN capricho.usuario u ON u.id_usuario = c.id_usuario
              JOIN capricho.venta v ON v.id_cliente = c.id_cliente AND v.estado = 'PAGADA'
              JOIN (
                  SELECT id_venta, sum(cantidad)::int AS unidades
                    FROM capricho.detalle_venta
                   GROUP BY id_venta
              ) d ON d.id_venta = v.id_venta
             WHERE v.fecha_venta BETWEEN :start AND :end
               AND v.id_tenant = :tenant_id
               AND c.id_tenant = :tenant_id
               AND u.id_tenant = :tenant_id
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
             GROUP BY c.id_cliente, u.nombres, u.apellidos, u.correo
             ORDER BY gasto_total DESC, compras DESC
             LIMIT :limit
        """), {
            "tenant_id": tenant_id,
            "start": start,
            "end": end,
            "branch_id": branch_id,
            "limit": limit,
        })
        rows = result.mappings().all()
        return CustomerReport(
            desde=date_from,
            hasta=date_to,
            clientes=[CustomerPerformance(**row) for row in rows],
        )
