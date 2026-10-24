from app.scripts.seed_demo_sales import (
    CUSTOMER_PASSWORD,
    CUSTOMERS_PER_TENANT,
    DEMO_SLUGS,
    SALES_PER_TENANT,
    customer_email,
)


def test_demo_sales_seed_has_expected_scope() -> None:
    assert len(DEMO_SLUGS) == 10
    assert len(set(DEMO_SLUGS)) == 10
    assert CUSTOMERS_PER_TENANT == 6
    assert SALES_PER_TENANT == 30
    assert CUSTOMER_PASSWORD == "Cliente123*"


def test_customer_credentials_are_unique_between_tenants() -> None:
    emails = {
        customer_email(slug, number)
        for slug in DEMO_SLUGS
        for number in range(1, CUSTOMERS_PER_TENANT + 1)
    }

    assert len(emails) == 60
    assert "cliente01+casa-elena@zentrysaas.store" in emails
    assert "cliente06+altura-comercial@zentrysaas.store" in emails
