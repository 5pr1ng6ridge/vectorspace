import argparse
import re
import sys
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageColor, ImageDraw, ImageFont


def parse_size(size_text: str) -> Tuple[int, int]:
    text = size_text.strip().lower()
    match = re.match(r"^(\d+)\s*[x\*,]\s*(\d+)$", text)
    if not match:
        raise ValueError("Invalid size format. Use format like 300x200.")

    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive integers.")
    return width, height


def parse_color(color_text: str) -> Tuple[int, int, int, int]:
    text = color_text.strip()

    # Allow bare hex like "ff6600"
    if re.fullmatch(r"[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", text):
        text = f"#{text}"

    try:
        rgb = ImageColor.getrgb(text)
    except ValueError as exc:
        raise ValueError("Invalid color. Use a hex color like #FF6600.") from exc

    if len(rgb) < 3:
        raise ValueError("Invalid color.")
    return rgb[0], rgb[1], rgb[2], 255


def load_font(size: int) -> ImageFont.ImageFont:
    # Try common fonts first, then fall back to PIL default font.
    for name in ("arial.ttf", "DejaVuSans.ttf", "msyh.ttc", "simhei.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, width: int, height: int) -> ImageFont.ImageFont:
    max_size = max(12, min(width, height) // 4)
    min_size = 10

    for size in range(max_size, min_size - 1, -1):
        font = load_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w = right - left
        text_h = bottom - top
        if text_w <= width * 0.8 and text_h <= height * 0.5:
            return font

    return load_font(min_size)


def create_placeholder_png(
    width: int,
    height: int,
    border_color: Tuple[int, int, int, int],
    output_path: Path,
    border_width: int | None = None,
) -> None:
    if border_width is None:
        border_width = max(1, min(width, height) // 40)
    if border_width <= 0:
        raise ValueError("Border width must be a positive integer.")

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=border_color, width=border_width)

    label = f"{width}x{height}"
    font = fit_font(draw, label, width, height)
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    text_w = right - left
    text_h = bottom - top
    pos = ((width - text_w) // 2, (height - text_h) // 2)
    draw.text(pos, label, fill=border_color, font=font)

    image.save(output_path, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a placeholder PNG with transparent center and solid border."
    )
    parser.add_argument("size", nargs="?", help="Size, e.g. 300x200")
    parser.add_argument("color", nargs="?", help="Color code, e.g. #FF6600")
    parser.add_argument("-o", "--output", help="Output png path")
    parser.add_argument("-b", "--border", type=int, default=None, help="Border width in pixels")
    args = parser.parse_args()

    size_input = args.size or input("Enter size (e.g. 300x200): ").strip()
    color_input = args.color or input("Enter color (e.g. #FF6600): ").strip()

    width, height = parse_size(size_input)
    color = parse_color(color_input)

    color_hex = f"{color[0]:02x}{color[1]:02x}{color[2]:02x}"
    output = Path(args.output) if args.output else Path(f"placeholder_{width}x{height}_{color_hex}.png")
    create_placeholder_png(width, height, color, output, border_width=args.border)
    print(f"Created: {output.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

