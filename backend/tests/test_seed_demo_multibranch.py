from datetime import date

from app.scripts.seed_demo_multibranch import (
    MONTHS,
    SALES_PER_MONTH,
    month_windows,
    target_branch_count,
)
from app.scripts.seed_demo_sales import DEMO_SLUGS


def test_branch_limits_follow_each_plan() -> None:
    basic = DEMO_SLUGS[:5]
    professional = DEMO_SLUGS[5:]

    assert {target_branch_count(slug, "BASICO") for slug in basic} == {2}
    assert all(3 <= target_branch_count(slug, "PROFESIONAL") <= 8 for slug in professional)
    assert len({target_branch_count(slug, "PROFESIONAL") for slug in professional}) > 1


def test_sales_cover_six_consecutive_months() -> None:
    windows = month_windows(date(2026, 10, 26))

    assert MONTHS == 6
    assert SALES_PER_MONTH * MONTHS == 180
    assert len(windows) == 6
    assert windows[0] == (date(2026, 5, 1), date(2026, 5, 31))
    assert windows[-1] == (date(2026, 10, 1), date(2026, 10, 26))
