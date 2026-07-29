"""Small image helpers shared by ORTM frame conformance tools."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def load_luma(path: Path) -> list[list[int]]:
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Pillow is required for PNG/JPEG input; install with "
            "`python3 -m pip install -e '.[image]'`"
        ) from error

    with Image.open(path) as image:
        luma = image.convert("L")
        width, height = luma.size
        pixels = list(luma.getdata())
    return [pixels[row * width : (row + 1) * width] for row in range(height)]


def save_luma(path: Path, frame: Sequence[Sequence[int]]) -> None:
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Pillow is required for PNG output; install with "
            "`python3 -m pip install -e '.[image]'`"
        ) from error

    height = len(frame)
    width = len(frame[0]) if height else 0
    image = Image.new("L", (width, height))
    image.putdata([value for row in frame for value in row])
    image.save(path)
