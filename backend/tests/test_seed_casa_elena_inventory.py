from app.scripts.seed_casa_elena_inventory import (
    COLORS,
    GARMENTS,
    REMAINING_DEMO_SLUGS,
    SIZES,
    SUPPLIERS,
    internal_ean13,
    tenant_prefix,
)


def test_casa_elena_seed_dataset_is_consistent() -> None:
    assert len(GARMENTS) == 12
    assert len({item.code for item in GARMENTS}) == len(GARMENTS)
    assert len({item.name for item in GARMENTS}) == len(GARMENTS)
    assert all(len(item.colors) == 2 for item in GARMENTS)
    assert all(color in COLORS for item in GARMENTS for color in item.colors)
    assert all(item.supplier in SUPPLIERS for item in GARMENTS)
    assert {item.category for item in GARMENTS} == {"Poleras", "Polos", "Blusas", "Camisas"}
    assert {item.audience for item in GARMENTS} == {"HOMBRE", "MUJER"}
    assert all(item.audience == "MUJER" for item in GARMENTS if item.category == "Blusas")


def test_casa_elena_seed_produces_expected_variant_count() -> None:
    expected_variants = sum(len(item.colors) * len(SIZES) for item in GARMENTS)

    assert expected_variants == 120
    assert sum(item.stock * len(item.colors) * len(SIZES) for item in GARMENTS) == 670


def test_remaining_tenants_have_distinct_global_prefixes() -> None:
    prefixes = [tenant_prefix(slug) for slug in REMAINING_DEMO_SLUGS]

    assert len(REMAINING_DEMO_SLUGS) == 9
    assert len(prefixes) == len(set(prefixes))
    assert "casa-elena" not in REMAINING_DEMO_SLUGS


def test_internal_barcodes_are_valid_and_unique_between_tenants() -> None:
    codes = {
        internal_ean13(tenant_id, product, size, color)
        for tenant_id in range(1, 11)
        for product in range(1, 13)
        for size in range(1, 6)
        for color in range(1, 3)
    }

    assert len(codes) == 1200
    assert all(len(code) == 13 and code.startswith("29") for code in codes)


def test_new_catalog_sku_namespace_does_not_reuse_legacy_codes() -> None:
    prefixes = [tenant_prefix(slug) for slug in REMAINING_DEMO_SLUGS]
    skus = {
        f"{prefix}-SUP2-{garment.code}-{size}-01"
        for prefix in prefixes
        for garment in GARMENTS
        for size, _ in SIZES
    }

    assert len(skus) == len(prefixes) * len(GARMENTS) * len(SIZES)
    assert all("-SUP2-" in sku for sku in skus)
