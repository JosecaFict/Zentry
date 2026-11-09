import re
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import Tenant

DEFAULT_ACCENT = "#064FE8"
MAX_LOGO_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class ReportBrand:
    name: str = "Zentry"
    accent: str = DEFAULT_ACCENT
    logo: bytes | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.accent or ""):
            object.__setattr__(self, "accent", DEFAULT_ACCENT)


async def _logo(url: str | None) -> bytes | None:
    if not url:
        return None
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "res.cloudinary.com"
            or "/image/upload/" not in parsed.path
        ):
            return None
        source = BytesIO()
        async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(64 * 1024):
                    if source.tell() + len(chunk) > MAX_LOGO_BYTES:
                        return None
                    source.write(chunk)
        source.seek(0)
        with Image.open(source) as image:
            if image.width * image.height > 8_000_000:
                return None
            logo = ImageOps.exif_transpose(image).convert("RGBA")
            logo.thumbnail((480, 240))
            output = BytesIO()
            logo.save(output, format="PNG")
            return output.getvalue()
    except (httpx.HTTPError, OSError, ValueError, Image.DecompressionBombError):
        return None


async def load_report_brand(
    session: AsyncSession, tenant_id: int, fallback: str = "Zentry"
) -> ReportBrand:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        return ReportBrand(fallback)
    return ReportBrand(tenant.nombre, tenant.color_primario, await _logo(tenant.logo_url))
