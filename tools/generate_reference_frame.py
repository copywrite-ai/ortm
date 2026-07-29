#!/usr/bin/env python3
"""Generate a deterministic ORTM frame for sender conformance checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from frame_image import save_luma
from ortm.raster import RasterProfile, render_luma_frame

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "ortm-v0-fixed-720p.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures" / "ortm-v0-fixed-720p.png")
    parser.add_argument("--frame-seq", type=int, default=4660)
    parser.add_argument("--timestamp-ms", type=lambda value: int(value, 0), default=0x89ABCDEF)
    args = parser.parse_args()

    config = json.loads(args.profile.read_text())
    raster = config["raster"]
    frame_config = config["frame"]
    frame = render_luma_frame(
        args.frame_seq,
        args.timestamp_ms & 0xFFFFFFFF,
        width=frame_config["width"],
        height=frame_config["height"],
        profile=RasterProfile(
            x=raster["x"],
            y=raster["y"],
            cell=raster["cell"],
            padding=raster["padding"],
        ),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_luma(args.output, frame)
    print(f"WROTE {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
