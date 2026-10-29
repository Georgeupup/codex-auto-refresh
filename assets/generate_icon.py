"""Generate the app's original woven-clock icon at common Windows sizes."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
SCALE = 4
SIZE = 256 * SCALE
RESAMPLE = Image.Resampling.LANCZOS


def box(coords):
    return tuple(round(value * SCALE) for value in coords)


def point(coords):
    return tuple(round(value * SCALE) for value in coords)


def width(value):
    return round(value * SCALE)


def make_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (SIZE, SIZE))
    pixels = gradient.load()
    top = (18, 157, 139)
    bottom = (5, 95, 89)
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        color = tuple(round(a * (1 - ratio) + b * ratio) for a, b in zip(top, bottom)) + (255,)
        for x in range(SIZE):
            pixels[x, y] = color
    mask = Image.new("L", (SIZE, SIZE))
    ImageDraw.Draw(mask).rounded_rectangle(box((4, 4, 252, 252)), radius=width(54), fill=255)
    image.paste(gradient, (0, 0), mask)

    # Six separate rounded loops suggest a woven chat symbol without copying it.
    for angle in range(0, 360, 60):
        loop = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(loop)
        draw.rounded_rectangle(
            box((96, 28, 160, 157)), radius=width(32),
            outline=(225, 255, 247, 255), width=width(17),
        )
        image.alpha_composite(loop.rotate(angle, resample=Image.Resampling.BICUBIC, center=point((128, 128))))

    draw = ImageDraw.Draw(image)
    # Alarm bells and feet remain legible at taskbar icon sizes.
    draw.arc(box((75, 66, 114, 105)), 195, 335, fill=(255, 193, 89), width=width(9))
    draw.arc(box((142, 66, 181, 105)), 205, 345, fill=(255, 193, 89), width=width(9))
    draw.line((point((96, 169)), point((84, 184))), fill=(255, 193, 89), width=width(9))
    draw.line((point((160, 169)), point((172, 184))), fill=(255, 193, 89), width=width(9))
    draw.ellipse(box((81, 81, 175, 175)), fill=(250, 255, 252), outline=(5, 81, 76), width=width(8))
    draw.line((point((128, 128)), point((143, 103))), fill=(4, 83, 78), width=width(8), joint="curve")
    draw.line((point((128, 128)), point((106, 115))), fill=(4, 83, 78), width=width(8), joint="curve")
    draw.ellipse(box((122, 122, 134, 134)), fill=(247, 167, 65))
    return image.resize((256, 256), RESAMPLE)


if __name__ == "__main__":
    icon = make_icon()
    icon.save(ROOT / "logo.png")
    icon.resize((32, 32), RESAMPLE).save(ROOT / "logo_32.png")
    icon.save(ROOT / "logo.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
