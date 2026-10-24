from app.scripts.seed_casa_elena_inventory import (
    COLORS,
    GARMENTS,
    REMAINING_DEMO_SLUGS,
    SIZES,
    SUPPLIERS,
    tenant_prefix,
)


def test_casa_elena_seed_dataset_is_consistent() -> None:
    assert len(GARMENTS) == 12
    assert len({item.code for item in GARMENTS}) == len(GARMENTS)
    assert len({item.name for item in GARMENTS}) == len(GARMENTS)
    assert all(len(item.colors) == 2 for item in GARMENTS)
    assert all(color in COLORS for item in GARMENTS for color in item.colors)
    assert all(item.supplier in SUPPLIERS for item in GARMENTS)


def test_casa_elena_seed_produces_expected_variant_count() -> None:
    expected_variants = sum(len(item.colors) * len(SIZES) for item in GARMENTS)

    assert expected_variants == 120
    assert sum(item.stock * len(item.colors) * len(SIZES) for item in GARMENTS) == 580


def test_remaining_tenants_have_distinct_global_prefixes() -> None:
    prefixes = [tenant_prefix(slug) for slug in REMAINING_DEMO_SLUGS]

    assert len(REMAINING_DEMO_SLUGS) == 9
    assert len(prefixes) == len(set(prefixes))
    assert "casa-elena" not in REMAINING_DEMO_SLUGS
