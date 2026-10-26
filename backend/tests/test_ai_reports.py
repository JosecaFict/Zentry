import pytest

from app.modules.reports.ai import GroqReportInterpreter, LocalReportInterpreter


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
