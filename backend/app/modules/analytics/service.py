from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.ml import forecast_demand, segment_customers
from app.modules.analytics.schemas import AnalyticsDashboard


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dashboard(
        self, *, tenant_id: int, branch_id: int | None, branch_name: str | None
    ) -> AnalyticsDashboard:
        today = date.today()
        date_from = today - timedelta(days=181)
        start = datetime.combine(date_from, time.min, tzinfo=UTC)
        end = datetime.combine(today, time.max, tzinfo=UTC)
        weekly = (
            (
                await self.session.execute(
                    text("""
            SELECT date_trunc('week', v.fecha_venta)::date AS semana,
                   coalesce(sum(d.cantidad), 0)::int AS unidades,
                   coalesce(sum(d.subtotal), 0)::numeric(14,2) AS ingresos
              FROM capricho.venta v
              JOIN capricho.detalle_venta d ON d.id_venta = v.id_venta
             WHERE v.id_tenant = :tenant_id AND v.estado = 'PAGADA'
               AND v.fecha_venta BETWEEN :start AND :end
               AND v.fecha_venta < date_trunc('week', CURRENT_DATE)
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
             GROUP BY date_trunc('week', v.fecha_venta)::date
             ORDER BY semana
        """),
                    {"tenant_id": tenant_id, "branch_id": branch_id, "start": start, "end": end},
                )
            )
            .mappings()
            .all()
        )
        customers = (
            (
                await self.session.execute(
                    text("""
            SELECT c.id_cliente,
                   (CURRENT_DATE - max(v.fecha_venta)::date)::int AS recencia,
                   count(DISTINCT v.id_venta)::int AS frecuencia,
                   coalesce(sum(v.total), 0)::numeric(14,2) AS gasto
              FROM capricho.cliente c
              JOIN capricho.venta v ON v.id_cliente = c.id_cliente
             WHERE c.id_tenant = :tenant_id AND v.id_tenant = :tenant_id
               AND v.estado = 'PAGADA' AND v.fecha_venta BETWEEN :start AND :end
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
             GROUP BY c.id_cliente
             ORDER BY c.id_cliente
        """),
                    {"tenant_id": tenant_id, "branch_id": branch_id, "start": start, "end": end},
                )
            )
            .mappings()
            .all()
        )
        if branch_id is not None and branch_name is None:
            branch_name = (
                await self.session.execute(
                    text("""
                SELECT nombre FROM capricho.sucursal
                 WHERE id_tenant = :tenant_id AND id_sucursal = :branch_id AND activo = true
            """),
                    {"tenant_id": tenant_id, "branch_id": branch_id},
                )
            ).scalar_one_or_none()
        return AnalyticsDashboard(
            generado_en=today,
            periodo_desde=date_from,
            periodo_hasta=today,
            sucursal=branch_name or "Todas las sucursales",
            prediccion_demanda=forecast_demand(list(weekly), generated_on=today),
            segmentacion_clientes=segment_customers(list(customers)),
        )
