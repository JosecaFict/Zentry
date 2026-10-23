from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
PUBLIC_IMAGES = ROOT.parents[2] / "frontend-web" / "public" / "images"
INK = "#10141C"
COBALT = "#064FE8"
MIST = "#B8C2D1"
WHITE = "#FFFFFF"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size=size)


def draw_mark(canvas: Image.Image, origin: tuple[int, int], cell: int, gap: int) -> None:
    draw = ImageDraw.Draw(canvas)
    x, y = origin
    radius = int(cell * 0.2)
    colors = (INK, COBALT, COBALT, MIST)
    positions = (
        (x, y),
        (x + cell + gap, y),
        (x, y + cell + gap),
        (x + cell + gap, y + cell + gap),
    )
    for position, color in zip(positions, colors, strict=True):
        px, py = position
        draw.rounded_rectangle((px, py, px + cell, py + cell), radius=radius, fill=color)

    pad = int(cell * 0.27)
    left = x + pad
    right = x + cell - pad
    top = y + pad
    bottom = y + cell - pad
    stroke = max(8, int(cell * 0.12))
    draw.line((left, top, right, top, left, bottom, right, bottom), fill=WHITE, width=stroke, joint="curve")


def primary_logo(text_color: str = INK) -> Image.Image:
    canvas = Image.new("RGBA", (1800, 520), (0, 0, 0, 0))
    draw_mark(canvas, (70, 86), 150, 30)
    draw = ImageDraw.Draw(canvas)
    draw.text((475, 142), "Zentry", font=font(190), fill=text_color, spacing=0)
    return canvas


def symbol_logo() -> Image.Image:
    canvas = Image.new("RGBA", (620, 620), (0, 0, 0, 0))
    draw_mark(canvas, (70, 70), 220, 40)
    return canvas


def save(image: Image.Image, name: str, public_name: str) -> None:
    image.save(ROOT / name, format="PNG", optimize=True)
    PUBLIC_IMAGES.mkdir(parents=True, exist_ok=True)
    image.save(PUBLIC_IMAGES / public_name, format="PNG", optimize=True)


save(primary_logo(), "zentry-modular-transparent.png", "zentry-logo.png")
save(primary_logo(WHITE), "zentry-modular-white-transparent.png", "zentry-logo-white.png")
save(symbol_logo(), "zentry-modular-symbol-transparent.png", "zentry-mark.png")
