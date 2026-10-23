from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.modules.platform.subscription_lifecycle import subscription_status


@pytest.mark.parametrize(
    ("days_until_end", "grace_offset", "expected"),
    [
        (20, 7, "ACTIVA"),
        (6, 7, "POR_VENCER"),
        (0, 7, "POR_VENCER"),
        (-1, 7, "GRACIA"),
        (-7, 7, "GRACIA"),
        (-8, 7, "SUSPENDIDA"),
    ],
)
def test_subscription_status_follows_paid_period(
    days_until_end: int, grace_offset: int, expected: str
) -> None:
    today = date(2026, 10, 22)
    end = today + timedelta(days=days_until_end)
    subscription = SimpleNamespace(
        fecha_fin=end,
        fecha_fin_gracia=end + timedelta(days=grace_offset),
    )

    assert subscription_status(subscription, today) == expected


def test_subscription_without_paid_period_is_suspended() -> None:
    subscription = SimpleNamespace(fecha_fin=None, fecha_fin_gracia=None)

    assert subscription_status(subscription, date(2026, 10, 22)) == "SUSPENDIDA"
