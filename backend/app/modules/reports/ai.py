import json
import re
from datetime import date
from typing import Any, Protocol

import httpx

from app.modules.reports.schemas import AIReportPlan


class AIReportInterpreterError(RuntimeError):
    pass


class AIReportInterpreter(Protocol):
    async def interpret(
        self, question: str, reference_date: date | None = None
    ) -> AIReportPlan: ...


REPORT_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tipo_reporte": {
            "type": "string",
            "enum": [
                "VENTAS", "PRODUCTOS", "INVENTARIO", "CLIENTES",
                "INGRESOS_CATEGORIA", "RESUMEN",
            ],
        },
        "dias": {"type": "integer", "minimum": 1, "maximum": 731},
        "fecha_desde": {"type": ["string", "null"]},
        "fecha_hasta": {"type": ["string", "null"]},
        "sucursal": {"type": ["string", "null"]},
        "categoria": {"type": ["string", "null"]},
        "producto": {"type": ["string", "null"]},
        "agrupacion": {
            "type": "string",
            "enum": ["DIA", "SEMANA", "MES", "SUCURSAL", "CATEGORIA", "PRODUCTO", "NINGUNA"],
        },
        "visualizacion": {
            "type": "string",
            "enum": ["TABLA", "BARRAS", "LINEAS", "CIRCULAR", "INDICADORES"],
        },
        "ordenar_por": {
            "type": "string",
            "enum": ["INGRESOS", "UNIDADES", "VENTAS", "STOCK", "NOMBRE"],
        },
        "direccion": {"type": "string", "enum": ["ASC", "DESC"]},
        "limite": {"type": "integer", "minimum": 1, "maximum": 100},
        "solo_criticos": {"type": "boolean"},
        "necesita_aclaracion": {"type": "boolean"},
        "pregunta_aclaracion": {"type": ["string", "null"]},
    },
    "required": [
        "tipo_reporte", "dias", "fecha_desde", "fecha_hasta", "sucursal",
        "categoria", "producto", "agrupacion", "visualizacion", "ordenar_por",
        "direccion", "limite", "solo_criticos", "necesita_aclaracion",
        "pregunta_aclaracion",
    ],
}


class GroqReportInterpreter:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIReportInterpreterError(
                "Groq no devolvió una interpretación utilizable"
            ) from exc
        if not content:
            raise AIReportInterpreterError("Groq no devolvió una interpretación utilizable")
        return str(content)

    async def interpret(
        self, question: str, reference_date: date | None = None
    ) -> AIReportPlan:
        today = reference_date or date.today()
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Interpreta consultas de reportes comerciales en español. "
                        f"La fecha actual es {today.isoformat()}. "
                        "Elige exactamente un reporte permitido y devuelve solo el plan. "
                        "No generes SQL, código, IDs de tenant ni IDs de sucursal. "
                        "Puedes extraer el nombre escrito de una sucursal, categoría o producto; "
                        "el servidor comprobará que pertenezca a la empresa autenticada. "
                        "Usa VENTAS con agrupacion SUCURSAL para ventas o comparaciones por "
                        "sucursal; PRODUCTOS para rankings de productos; INVENTARIO para stock "
                        "y existencias; e INGRESOS_CATEGORIA para ingresos o participación por "
                        "categoría. "
                        "Convierte períodos explícitos a fechas ISO. Si solo hay un período "
                        "relativo, usa dias y deja ambas fechas en null. Para inventario actual "
                        "no hace falta un período. Si una solicitud de ventas, productos, clientes "
                        "o ingresos por categoría no permite determinar un período, marca "
                        "necesita_aclaracion y formula una pregunta concreta. No inventes filtros. "
                        "RESUMEN combina todos los reportes. Si no indican límite usa 20."
                    ),
                },
                {"role": "user", "content": question},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "zentry_report_plan",
                    "strict": True,
                    "schema": REPORT_PLAN_SCHEMA,
                },
            },
            "reasoning_effort": "low",
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            response.raise_for_status()
            return AIReportPlan.model_validate_json(self._output_text(response.json()))
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise AIReportInterpreterError(
                "No se pudo interpretar la consulta con Groq"
            ) from exc


class LocalReportInterpreter:
    """Intérprete determinista para desarrollo y pruebas, nunca para producción."""

    async def interpret(
        self, question: str, reference_date: date | None = None
    ) -> AIReportPlan:
        normalized = question.casefold()
        report_type = "RESUMEN"
        if any(word in normalized for word in ("inventario", "stock", "agot")):
            report_type = "INVENTARIO"
        elif "categor" in normalized and any(
            word in normalized for word in ("ingreso", "venta", "factur")
        ):
            report_type = "INGRESOS_CATEGORIA"
        elif any(word in normalized for word in ("producto", "prenda", "vendido")):
            report_type = "PRODUCTOS"
        elif any(word in normalized for word in ("cliente", "comprador")):
            report_type = "CLIENTES"
        elif any(word in normalized for word in ("venta", "ingreso", "ticket")):
            report_type = "VENTAS"

        days = 90
        match = re.search(r"(\d{1,3})\s*d[ií]as?", normalized)
        if match:
            days = min(max(int(match.group(1)), 1), 731)
        elif "semana" in normalized:
            days = 7
        elif "mes" in normalized:
            days = 30
        elif "año" in normalized or "anual" in normalized:
            days = 365

        explicit_period = bool(
            match
            or any(word in normalized for word in ("semana", "mes", "año", "anual", "hoy"))
        )
        needs_period = report_type in {
            "VENTAS", "PRODUCTOS", "CLIENTES", "INGRESOS_CATEGORIA", "RESUMEN"
        }
        needs_clarification = needs_period and not explicit_period
        grouping = "NINGUNA"
        if "sucursal" in normalized:
            grouping = "SUCURSAL"
        elif "categor" in normalized:
            grouping = "CATEGORIA"
        elif "semana" in normalized:
            grouping = "SEMANA"
        elif report_type == "VENTAS":
            grouping = "DIA"

        return AIReportPlan(
            tipo_reporte=report_type,
            dias=days,
            agrupacion=grouping,
            visualizacion=("LINEAS" if grouping in {"DIA", "SEMANA", "MES"} else "BARRAS"),
            limite=20,
            solo_criticos=any(word in normalized for word in ("crítico", "critico", "bajo")),
            necesita_aclaracion=needs_clarification,
            pregunta_aclaracion=(
                "¿De qué período deseas consultar la información?"
                if needs_clarification
                else None
            ),
        )
