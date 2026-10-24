from collections import Counter

from app.scripts.seed_demo_tenants import DEMO_PASSWORD, DEMO_TENANTS, add_one_month


def test_demo_tenants_have_unique_credentials_and_balanced_plans() -> None:
    assert len(DEMO_TENANTS) == 10
    assert len({item.slug for item in DEMO_TENANTS}) == 10
    assert len({item.correo for item in DEMO_TENANTS}) == 10
    assert Counter(item.plan_codigo for item in DEMO_TENANTS) == {
        "BASICO": 5,
        "PROFESIONAL": 5,
    }
    assert DEMO_PASSWORD == "Admin123*"


def test_add_one_month_handles_year_boundary() -> None:
    from datetime import date

    assert add_one_month(date(2026, 10, 24)) == date(2026, 11, 24)
    assert add_one_month(date(2026, 12, 24)) == date(2027, 1, 24)
