from __future__ import annotations

from datetime import date
from math import sqrt
from statistics import fmean, pstdev

from app.modules.analytics.schemas import (
    CustomerSegment,
    CustomerSegmentation,
    DemandForecast,
    ForecastPoint,
)


def _linear_regression(values: list[float]) -> tuple[float, float, float, float]:
    """Return intercept, slope, MAE and R² for an ordinary least-squares line."""
    count = len(values)
    x_mean = (count - 1) / 2
    y_mean = fmean(values)
    denominator = sum((x - x_mean) ** 2 for x in range(count))
    slope = (
        sum((x - x_mean) * (y - y_mean) for x, y in enumerate(values)) / denominator
        if denominator
        else 0.0
    )
    intercept = y_mean - slope * x_mean
    predicted = [intercept + slope * x for x in range(count)]
    errors = [actual - estimate for actual, estimate in zip(values, predicted, strict=True)]
    mae = fmean(abs(error) for error in errors)
    total = sum((value - y_mean) ** 2 for value in values)
    residual = sum(error**2 for error in errors)
    r2 = 1 - residual / total if total else 1.0
    return intercept, slope, mae, r2


def forecast_demand(
    rows: list[dict],
    *,
    generated_on: date,
    future_dates: list[date],
    granularidad: str,
    objetivo: str,
) -> DemandForecast:
    units = [float(row["unidades"]) for row in rows]
    revenue = [float(row["ingresos"]) for row in rows]
    if len(units) < 4:
        return DemandForecast(
            modelo="Regresión lineal temporal",
            objetivo=objetivo,
            granularidad=granularidad,
            observaciones_entrenamiento=len(units),
            fecha_entrenamiento=generated_on,
            mae_unidades=0,
            r2_unidades=0,
            tendencia_por_periodo=0,
            confianza="BAJA",
            advertencia="Se requieren al menos cuatro periodos con ventas para proyectar demanda.",
            pronostico=[],
        )

    unit_intercept, unit_slope, mae, r2 = _linear_regression(units)
    revenue_intercept, revenue_slope, _, _ = _linear_regression(revenue)
    residual_sigma = pstdev(
        [value - (unit_intercept + unit_slope * index) for index, value in enumerate(units)]
    )
    margin = max(1.0, 1.96 * residual_sigma)
    points: list[ForecastPoint] = []
    for offset, forecast_date in enumerate(future_dates, start=1):
        x = len(units) - 1 + offset
        estimate = max(0, round(unit_intercept + unit_slope * x))
        points.append(
            ForecastPoint(
                fecha=forecast_date,
                unidades_estimadas=estimate,
                ingresos_estimados=round(max(0, revenue_intercept + revenue_slope * x), 2),
                intervalo_inferior=max(0, round(estimate - margin)),
                intervalo_superior=max(0, round(estimate + margin)),
            )
        )
    confidence = (
        "ALTA"
        if len(units) >= 20 and r2 >= 0.65
        else "MEDIA"
        if len(units) >= 12 and r2 >= 0.25
        else "BAJA"
    )
    warning = (
        None
        if confidence != "BAJA"
        else "La proyección es orientativa por la cantidad o variabilidad de los datos."
    )
    return DemandForecast(
        modelo="Regresión lineal temporal",
        objetivo=objetivo,
        granularidad=granularidad,
        observaciones_entrenamiento=len(units),
        fecha_entrenamiento=generated_on,
        mae_unidades=round(mae, 2),
        r2_unidades=round(r2, 3),
        tendencia_por_periodo=round(unit_slope, 2),
        confianza=confidence,
        advertencia=warning,
        pronostico=points,
    )


def _standardize(rows: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    columns = list(zip(*rows, strict=True))
    means = [fmean(column) for column in columns]
    deviations = [pstdev(column) or 1.0 for column in columns]
    return [
        tuple((value - means[index]) / deviations[index] for index, value in enumerate(row))
        for row in rows
    ]


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _kmeans(points: list[tuple[float, float, float]], clusters: int = 3) -> list[int]:
    order = sorted(range(len(points)), key=lambda idx: sum(points[idx]))
    centroids = [
        points[order[round(i * (len(order) - 1) / (clusters - 1))]] for i in range(clusters)
    ]
    assignments = [0] * len(points)
    for _ in range(30):
        updated = [
            min(range(clusters), key=lambda idx: _distance(point, centroids[idx]))
            for point in points
        ]
        if updated == assignments:
            break
        assignments = updated
        for cluster in range(clusters):
            members = [
                point
                for point, assigned in zip(points, assignments, strict=True)
                if assigned == cluster
            ]
            if members:
                centroids[cluster] = tuple(fmean(column) for column in zip(*members, strict=True))
    return assignments


def segment_customers(rows: list[dict]) -> CustomerSegmentation:
    if len(rows) < 3:
        return CustomerSegmentation(
            modelo="K-means RFM",
            variables=["recencia", "frecuencia", "valor monetario"],
            clientes_analizados=len(rows),
            segmentos=[],
        )
    raw = [(float(row["recencia"]), float(row["frecuencia"]), float(row["gasto"])) for row in rows]
    # Recency is inverted so a recent purchase raises the commercial score.
    points = _standardize([(-recency, frequency, monetary) for recency, frequency, monetary in raw])
    assigned = _kmeans(points)
    if len(set(assigned)) < 3:
        # Degenerate datasets (identical synthetic profiles) still receive stable
        # rank-based cohorts instead of failing or inventing empty clusters.
        ranked_indexes = sorted(range(len(points)), key=lambda idx: sum(points[idx]), reverse=True)
        assigned = [0] * len(points)
        for position, row_index in enumerate(ranked_indexes):
            assigned[row_index] = min(2, position * 3 // len(points))
    cluster_scores: dict[int, float] = {}
    for cluster in set(assigned):
        cluster_scores[cluster] = fmean(
            sum(point) for point, value in zip(points, assigned, strict=True) if value == cluster
        )
    ranked = sorted(cluster_scores, key=cluster_scores.get, reverse=True)
    names = {ranked[0]: "LEALES", ranked[1]: "POTENCIALES", ranked[2]: "EN_RIESGO"}
    descriptions = {
        "LEALES": "Compran con frecuencia, recientemente y concentran alto valor.",
        "POTENCIALES": "Mantienen actividad media y pueden aumentar su recurrencia.",
        "EN_RIESGO": "Llevan más tiempo sin comprar o muestran menor frecuencia.",
    }
    actions = {
        "LEALES": "Priorizar beneficios de fidelidad y lanzamientos relevantes.",
        "POTENCIALES": "Activar recomendaciones y recordatorios de recompra.",
        "EN_RIESGO": "Ejecutar una campaña de reactivación y medir su retorno.",
    }
    segments: list[CustomerSegment] = []
    for name in ("LEALES", "POTENCIALES", "EN_RIESGO"):
        members = [
            row for row, cluster in zip(rows, assigned, strict=True) if names[cluster] == name
        ]
        segments.append(
            CustomerSegment(
                segmento=name,
                descripcion=descriptions[name],
                clientes=len(members),
                porcentaje=round(len(members) * 100 / len(rows), 2),
                recencia_promedio_dias=round(fmean(float(row["recencia"]) for row in members), 1),
                frecuencia_promedio=round(fmean(float(row["frecuencia"]) for row in members), 1),
                gasto_promedio=round(fmean(float(row["gasto"]) for row in members), 2),
                accion_recomendada=actions[name],
            )
        )
    return CustomerSegmentation(
        modelo="K-means RFM",
        variables=["recencia", "frecuencia", "valor monetario"],
        clientes_analizados=len(rows),
        segmentos=segments,
    )
