"""Generate the ASCII fitter's six-dimensional font shapes and preview masks.

Development-only Pillow rasterization; runtime fitting needs only numpy. Sampling
uses staggered circles from https://alexharri.com/blog/ascii-rendering. The same
circle integrals produce weights for bilinear reconstruction of the 2x3 input.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def build(font_path: Path, output: Path) -> None:
    """Write reproducible normalized shapes and small coverage masks.

    Args:
        font_path: Monospace TrueType/OpenType font to rasterize.
        output: Generated Python module destination (overwritten).
    """
    width, height = 32, 64
    font = ImageFont.truetype(str(font_path), 52)
    ascent, descent = font.getmetrics()
    y, x = np.mgrid[:height, :width].astype(np.float32)
    x = (x + 0.5) / width
    y = (y + 0.5) / height
    circles = []
    for row in range(3):
        for col in range(2):
            # A 0.30-cell-width radius covers gaps without losing edge orientation.
            cx = 0.25 + col * 0.5
            cy = (row + 0.5) / 3 + (0.045 if col == 0 else -0.045)
            mask = ((x - cx) ** 2 + (2 * (y - cy)) ** 2) < 0.30**2
            circles.append(mask / mask.sum())
    circles = np.asarray(circles, dtype=np.float32)
    masks, vectors = [], []
    for code in range(32, 127):
        image = Image.new("L", (width, height))
        draw = ImageDraw.Draw(image)
        char = chr(code)
        draw.text(
            ((width - font.getlength(char)) / 2, (height - ascent - descent) / 2),
            char,
            font=font,
            fill=255,
        )
        coverage = np.asarray(image, dtype=np.float32) / 255
        vectors.append((circles * coverage).sum(axis=(1, 2)))
        masks.append(np.asarray(image.resize((8, 16), Image.Resampling.BOX)).tolist())
    vectors = np.asarray(vectors)
    vectors /= vectors.max(axis=0)
    # Integrate the six bilinear input basis functions over the identical circles.
    sx = np.clip(x * 2 - 0.5, 0, 1)
    sy = np.clip(y * 3 - 0.5, 0, 2)
    weights = []
    for row in range(3):
        for col in range(2):
            basis = np.maximum(1 - abs(sy - row), 0) * np.maximum(1 - abs(sx - col), 0)
            weights.append((circles * basis).sum(axis=(1, 2)).tolist())
    header = (
        '"""Generated ASCII shape data for glyph fitting and honest font previews.\n\n'
        f"Generator: tools/build_glyph_shapes.py; font: {font_path.name}.\n"
        'Do not edit by hand; regeneration requires development-only Pillow.\n"""\n\n'
    )
    output.write_text(
        header
        + f"FONT = {font_path.name!r}\n\n"
        + "SHAPES = (\n"
        + "".join(f"    {tuple(round(float(v), 6) for v in row)!r},\n" for row in vectors)
        + ")\n\n"
        + "SAMPLE_WEIGHTS = (\n"
        + "".join(f"    {tuple(round(v, 6) for v in row)!r},\n" for row in weights)
        + ")\n\n"
        + "MASKS = (\n"
        + "".join(
            "    (\n" + "".join(f"        {tuple(row)!r},\n" for row in mask) + "    ),\n"
            for mask in masks
        )
        + ")\n"
    )


def main() -> None:
    """Generate the data using --font or the system's preferred monospace font."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--out", type=Path, default=Path("src/agentic_av/viz/_ascii_shapes.py"))
    args = parser.parse_args()
    font = args.font or Path(
        subprocess.check_output(["fc-match", "monospace", "-f", "%{file}"], text=True)
    )
    build(font, args.out)


if __name__ == "__main__":
    main()
