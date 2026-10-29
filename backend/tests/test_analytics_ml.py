from datetime import date, timedelta

from app.modules.analytics.ml import forecast_demand, segment_customers


def test_forecast_demand_projects_four_weeks_and_reports_quality():
    start = date(2026, 5, 4)
    rows = [
        {
            "semana": start + timedelta(days=7 * index),
            "unidades": 20 + index * 2,
            "ingresos": 2000 + index * 150,
        }
        for index in range(16)
    ]

    result = forecast_demand(rows, generated_on=date(2026, 10, 29))

    assert result.modelo == "Regresión lineal temporal"
    assert result.semanas_entrenamiento == 16
    assert result.r2_unidades == 1
    assert result.tendencia_por_semana == 2
    assert len(result.pronostico) == 4
    assert result.pronostico[0].unidades_estimadas == 52


def test_forecast_demand_is_explicit_when_history_is_insufficient():
    result = forecast_demand(
        [{"semana": date(2026, 10, 1), "unidades": 3, "ingresos": 100}],
        generated_on=date(2026, 10, 29),
    )
    assert result.confianza == "BAJA"
    assert result.pronostico == []
    assert result.advertencia


def test_segmentation_produces_three_explainable_rfm_cohorts():
    rows = [
        {"recencia": 2, "frecuencia": 18, "gasto": 9500},
        {"recencia": 4, "frecuencia": 15, "gasto": 8000},
        {"recencia": 18, "frecuencia": 8, "gasto": 4100},
        {"recencia": 25, "frecuencia": 6, "gasto": 3000},
        {"recencia": 80, "frecuencia": 2, "gasto": 900},
        {"recencia": 120, "frecuencia": 1, "gasto": 400},
    ]

    result = segment_customers(rows)

    assert result.modelo == "K-means RFM"
    assert result.clientes_analizados == 6
    assert [segment.segmento for segment in result.segmentos] == [
        "LEALES",
        "POTENCIALES",
        "EN_RIESGO",
    ]
    assert sum(segment.clientes for segment in result.segmentos) == 6
    assert result.segmentos[0].gasto_promedio > result.segmentos[-1].gasto_promedio


def test_segmentation_handles_identical_profiles_without_empty_cluster_failure():
    rows = [{"recencia": 10, "frecuencia": 4, "gasto": 1200} for _ in range(6)]
    result = segment_customers(rows)
    assert len(result.segmentos) == 3
    assert all(segment.clientes == 2 for segment in result.segmentos)
