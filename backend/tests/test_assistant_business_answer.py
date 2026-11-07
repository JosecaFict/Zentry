from app.modules.assistant.business_answer import business_answer


def test_product_report_uses_database_amount_in_bolivianos():
    answer = business_answer('PRODUCTOS', {
        'desde': '2026-09-01', 'hasta': '2026-09-30',
        'productos': [{'producto': 'Polo Ralph Lauren Classic Fit', 'categoria': 'POLO', 'unidades': 21, 'ingresos': '4200.00'}],
    })
    assert 'Bs 4.200,00' in answer
    assert 'Unidades vendidas: 21' in answer
    assert 'septiembre de 2026' in answer
    assert '2026-09-01' not in answer
    assert '**' not in answer
    assert '€' not in answer


def test_multi_product_table_does_not_include_internal_ids():
    answer = business_answer('PRODUCTOS', {'productos': [
        {'producto': 'Polo | azul\ncon *texto*', 'categoria': 'POLO', 'unidades': 21, 'ingresos': '4200.00'},
        {'producto': 'Camisa', 'categoria': 'CAMISA', 'unidades': 2, 'ingresos': '500.00'},
    ]})
    assert '| Producto | Unidades | Ingresos |' in answer
    assert 'Polo / azul con texto' in answer
    assert 'Bs 500,00' in answer


def test_empty_product_report_does_not_invent_a_winner():
    assert 'No encontré ventas' in business_answer('PRODUCTOS', {'productos': []})


def test_partial_month_keeps_exact_dates_in_readable_spanish():
    answer = business_answer('PRODUCTOS', {'desde': '2026-09-03', 'hasta': '2026-09-18', 'productos': []})
    assert '3 de septiembre de 2026 al 18 de septiembre de 2026' in answer
    assert '2026-09-' not in answer
