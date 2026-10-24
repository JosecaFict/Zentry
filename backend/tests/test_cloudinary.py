from app.db.tenant_context import clear_tenant_context, set_tenant_context
from app.integrations.cloudinary import CloudinaryStorage


def test_tenant_logo_public_id_is_recovered_only_from_its_branding_folder() -> None:
    storage = CloudinaryStorage("cloudinary://key:secret@zentry-cloud")
    set_tenant_context(17)
    try:
        public_id = storage.public_id_from_url(
            "https://res.cloudinary.com/zentry-cloud/image/upload/"
            "v1790000000/zentry/tenants/17/branding/logo_ab12cd.png"
        )
        assert public_id == "zentry/tenants/17/branding/logo_ab12cd"
        assert (
            storage.public_id_from_url(
                "https://res.cloudinary.com/zentry-cloud/image/upload/"
                "v1790000000/zentry/tenants/18/branding/logo.png"
            )
            is None
        )
        assert storage.public_id_from_url("https://example.com/logo.png") is None
    finally:
        clear_tenant_context()
