"""Export the woven alarm-clock artwork at common Windows icon sizes."""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parent
RESAMPLE = Image.Resampling.LANCZOS
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def make_icon() -> Image.Image:
    """Clip the generated master artwork to its rounded-square tile."""
    artwork = Image.open(ROOT / "logo_source.png").convert("RGBA")
    if artwork.width != artwork.height:
        raise ValueError("图标原图必须是正方形")

    scale = artwork.width / 1254
    mask = Image.new("L", artwork.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, artwork.width - 1, artwork.height - 1),
        radius=round(220 * scale),
        fill=255,
    )
    # Replace the master's light edge pixels before resizing so they cannot
    # create a white fringe around the transparent tile corners.
    inset = round(14 * scale)
    inner = Image.new("L", artwork.size, 0)
    ImageDraw.Draw(inner).rounded_rectangle(
        (inset, inset, artwork.width - 1 - inset, artwork.height - 1 - inset),
        radius=round(206 * scale),
        fill=255,
    )
    artwork.paste((2, 84, 55, 255), (0, 0, artwork.width, artwork.height), ImageChops.subtract(mask, inner))
    artwork.putalpha(mask)
    return artwork.resize((256, 256), RESAMPLE)


if __name__ == "__main__":
    icon = make_icon()
    icon.save(ROOT / "logo.png")
    icon.resize((32, 32), RESAMPLE).save(ROOT / "logo_32.png")
    icon.save(ROOT / "logo.ico", format="ICO", sizes=ICON_SIZES)
