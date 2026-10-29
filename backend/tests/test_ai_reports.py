import pytest
from pydantic import ValidationError

from app.modules.reports.ai import GroqReportInterpreter, LocalReportInterpreter
from app.modules.reports.schemas import AIReportPlan


@pytest.mark.asyncio
async def test_local_interpreter_understands_inventory_period_and_critical_stock() -> None:
    plan = await LocalReportInterpreter().interpret(
        "Muéstrame el inventario crítico de los últimos 30 días"
    )

    assert plan.tipo_reporte == "INVENTARIO"
    assert plan.dias == 30
    assert plan.solo_criticos is True


@pytest.mark.asyncio
async def test_local_interpreter_understands_customers_and_year() -> None:
    plan = await LocalReportInterpreter().interpret("Mejores clientes del año")

    assert plan.tipo_reporte == "CLIENTES"
    assert plan.dias == 365


@pytest.mark.asyncio
async def test_local_interpreter_requests_period_for_ambiguous_sales() -> None:
    plan = await LocalReportInterpreter().interpret("Muéstrame las ventas")

    assert plan.tipo_reporte == "VENTAS"
    assert plan.necesita_aclaracion is True
    assert plan.pregunta_aclaracion


def test_report_plan_accepts_complete_exact_period() -> None:
    plan = AIReportPlan(
        tipo_reporte="PRODUCTOS",
        fecha_desde="2026-09-01",
        fecha_hasta="2026-09-30",
        agrupacion="PRODUCTO",
        visualizacion="BARRAS",
        limite=10,
    )

    assert plan.fecha_desde.isoformat() == "2026-09-01"
    assert plan.fecha_hasta.isoformat() == "2026-09-30"


def test_report_plan_rejects_partial_exact_period() -> None:
    with pytest.raises(ValidationError):
        AIReportPlan(tipo_reporte="VENTAS", fecha_desde="2026-09-01")


def test_groq_output_parser_reads_structured_response() -> None:
    payload = {
        "choices": [{
            "message": {
                "text": (
                    '{"tipo_reporte":"VENTAS","dias":7,'
                    '"limite":20,"solo_criticos":false}'
                ),
                "content": (
                    '{"tipo_reporte":"VENTAS","dias":7,'
                    '"limite":20,"solo_criticos":false}'
                ),
            }
        }]
    }

    text = GroqReportInterpreter._output_text(payload)

    assert '"VENTAS"' in text
