from app.scripts.seed_casa_elena_inventory import COLORS, GARMENTS, SIZES, SUPPLIERS


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
