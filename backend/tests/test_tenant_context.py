from app.db.tenant_context import clear_tenant_context, current_tenant_id, set_tenant_context


def test_tenant_context_can_be_set_and_cleared() -> None:
    clear_tenant_context()
    assert current_tenant_id() is None

    set_tenant_context(17)
    assert current_tenant_id() == 17

    clear_tenant_context()
    assert current_tenant_id() is None
