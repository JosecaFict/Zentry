"""Money calculations for returns; never accept a client-provided price."""

from decimal import Decimal, ROUND_HALF_UP


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def returned_amount(paid: Decimal, sold: int, quantity: int, completed: int = 0) -> Decimal:
    """Cumulative rounding makes partial returns add up to the exact paid amount."""
    if sold <= 0 or quantity <= 0 or completed < 0 or completed + quantity > sold:
        raise ValueError("Cantidad de devolución inválida")
    return money(paid * (completed + quantity) / sold) - money(paid * completed / sold)


def allocate_paid_amounts(subtotals: list[Decimal], paid: Decimal) -> list[Decimal]:
    """Distribute a sale-level discount without creating or losing cents."""
    total = sum(subtotals, Decimal(0))
    if total <= 0:
        return [Decimal(0) for _ in subtotals]
    cumulative = Decimal(0)
    allocated = Decimal(0)
    result = []
    for subtotal in subtotals:
        cumulative += subtotal
        next_total = money(paid * cumulative / total)
        result.append(next_total - allocated)
        allocated = next_total
    return result


def validate_exchange_choice(kind: str, original, replacement) -> None:
    same_product = original['id_producto'] == replacement['id_producto']
    if kind == 'CAMBIO_TALLA' and (not same_product or original['color'] != replacement['color'] or original['talla'] == replacement['talla']):
        raise ValueError('El cambio de talla debe conservar la misma prenda y color, con otra talla')
    if kind == 'CAMBIO_COLOR' and (not same_product or original['talla'] != replacement['talla'] or original['color'] == replacement['color']):
        raise ValueError('El cambio de color debe conservar la misma prenda y talla, con otro color')
