from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.ml import forecast_demand, segment_customers
from app.modules.analytics.schemas import AnalyticsDashboard

PERIOD_CONFIG = {
    "SEMANAL": {"days": 7, "bucket": "day", "granularity": "DIA", "horizon": 7},
    "MENSUAL": {"days": 30, "bucket": "week", "granularity": "SEMANA", "horizon": 4},
    "TRIMESTRAL": {"days": 90, "bucket": "week", "granularity": "SEMANA", "horizon": 12},
    "SEMESTRAL": {"days": 181, "bucket": "month", "granularity": "MES", "horizon": 6},
}


def _add_months(value: date, months: int) -> date:
    absolute_month = value.year * 12 + value.month - 1 + months
    return date(absolute_month // 12, absolute_month % 12 + 1, 1)


def _future_dates(today: date, *, granularity: str, horizon: int) -> list[date]:
    if granularity == "DIA":
        return [today + timedelta(days=offset) for offset in range(1, horizon + 1)]
    if granularity == "SEMANA":
        next_monday = today + timedelta(days=7 - today.weekday())
        return [next_monday + timedelta(days=7 * offset) for offset in range(horizon)]
    first_next_month = _add_months(today.replace(day=1), 1)
    return [_add_months(first_next_month, offset) for offset in range(horizon)]


def _forecast_objective(granularity: str) -> str:
    labels = {"DIA": "día", "SEMANA": "semana", "MES": "mes"}
    return f"Unidades vendidas por {labels[granularity]}"


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dashboard(
        self,
        *,
        tenant_id: int,
        branch_id: int | None,
        branch_name: str | None,
        periodo: str,
    ) -> AnalyticsDashboard:
        today = date.today()
        config = PERIOD_CONFIG[periodo]
        bucket = config["bucket"]
        granularity = config["granularity"]
        horizon = config["horizon"]
        date_from = today - timedelta(days=config["days"])
        start = datetime.combine(date_from, time.min, tzinfo=UTC)
        end = datetime.combine(today, time.max, tzinfo=UTC)
        history = (
            (
                await self.session.execute(
                    text(f"""
            SELECT date_trunc('{bucket}', v.fecha_venta)::date AS fecha,
                   coalesce(sum(d.cantidad), 0)::int AS unidades,
                   coalesce(sum(d.subtotal), 0)::numeric(14,2) AS ingresos
              FROM capricho.venta v
              JOIN capricho.detalle_venta d ON d.id_venta = v.id_venta
             WHERE v.id_tenant = :tenant_id AND v.estado = 'PAGADA'
               AND v.fecha_venta BETWEEN :start AND :end
               AND v.fecha_venta < date_trunc('{bucket}', CURRENT_DATE)
               AND (CAST(:branch_id AS BIGINT) IS NULL OR v.id_sucursal = :branch_id)
             GROUP BY date_trunc('{bucket}', v.fecha_venta)::date
             ORDER BY fecha
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
            periodo=periodo,
            prediccion_demanda=forecast_demand(
                list(history),
                generated_on=today,
                future_dates=_future_dates(today, granularity=granularity, horizon=horizon),
                granularidad=granularity,
                objetivo=_forecast_objective(granularity),
            ),
            segmentacion_clientes=segment_customers(list(customers)),
        )
