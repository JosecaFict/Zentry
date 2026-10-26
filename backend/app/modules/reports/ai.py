import json
import re
from typing import Any, Protocol

import httpx

from app.modules.reports.schemas import AIReportPlan


class AIReportInterpreterError(RuntimeError):
    pass


class AIReportInterpreter(Protocol):
    async def interpret(self, question: str) -> AIReportPlan: ...


REPORT_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "tipo_reporte": {
            "type": "string",
            "enum": ["VENTAS", "PRODUCTOS", "INVENTARIO", "CLIENTES", "RESUMEN"],
        },
        "dias": {"type": "integer", "minimum": 1, "maximum": 731},
        "limite": {"type": "integer", "minimum": 1, "maximum": 100},
        "solo_criticos": {"type": "boolean"},
    },
    "required": ["tipo_reporte", "dias", "limite", "solo_criticos"],
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

    async def interpret(self, question: str) -> AIReportPlan:
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Interpreta consultas de reportes comerciales en español. "
                        "Elige exactamente un reporte permitido. No generes SQL, código, "
                        "IDs de tenant ni sucursales. RESUMEN combina todos los reportes. "
                        "Si no indican período usa 90 días y límite 20."
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

    async def interpret(self, question: str) -> AIReportPlan:
        normalized = question.casefold()
        report_type = "RESUMEN"
        if any(word in normalized for word in ("inventario", "stock", "agot")):
            report_type = "INVENTARIO"
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

        return AIReportPlan(
            tipo_reporte=report_type,
            dias=days,
            limite=20,
            solo_criticos=any(word in normalized for word in ("crítico", "critico", "bajo")),
        )
