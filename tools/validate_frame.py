#!/usr/bin/env python3
"""Validate one final-resolution sender frame against a fixed ORTM profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from frame_image import load_luma
from ortm.codec import DecodeError
from ortm.raster import RasterProfile, decode_luma_frame

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "profiles" / "ortm-v0-fixed-720p.json"


def emit(result: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(result["status"])
    for key, value in result.items():
        if key != "status":
            print(f"{key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = json.loads(args.profile.read_text())
    expected_frame = config["frame"]
    raster = config["raster"]
    validation = config["validation"]

    try:
        frame = load_luma(args.input)
    except (OSError, RuntimeError) as error:
        emit({"status": "FAIL", "reason": "image-read-failed", "detail": str(error)}, as_json=args.json)
        return 2

    height = len(frame)
    width = len(frame[0]) if height else 0
    if width != expected_frame["width"] or height != expected_frame["height"]:
        emit(
            {
                "status": "FAIL",
                "reason": "resolution-mismatch",
                "actual_resolution": f"{width}x{height}",
                "expected_resolution": f'{expected_frame["width"]}x{expected_frame["height"]}',
            },
            as_json=args.json,
        )
        return 1

    nominal = RasterProfile(
        x=raster["x"],
        y=raster["y"],
        cell=raster["cell"],
        padding=raster["padding"],
    )
    try:
        decoded = decode_luma_frame(
            frame,
            nominal=nominal,
            scales=tuple(validation["scales"]),
            offsets=tuple(validation["offsets"]),
            min_contrast=validation["minContrast"],
        )
    except DecodeError as error:
        emit(
            {
                "status": "FAIL",
                "reason": error.reason,
                **error.details,
                "resolution": f"{width}x{height}",
                "profile": config["id"],
            },
            as_json=args.json,
        )
        return 1

    marker = decoded.marker
    if marker.finder_errors > validation["maxFinderErrors"] or marker.timing_errors > validation["maxTimingErrors"]:
        emit(
            {
                "status": "FAIL",
                "reason": "structure-error-limit",
                "finder_errors": marker.finder_errors,
                "timing_errors": marker.timing_errors,
            },
            as_json=args.json,
        )
        return 1

    emit(
        {
            "status": "PASS",
            "profile": config["id"],
            "resolution": f"{width}x{height}",
            "version": marker.version,
            "frame_seq": marker.frame_seq,
            "timestamp_ms": marker.timestamp_ms,
            "finder_errors": marker.finder_errors,
            "timing_errors": marker.timing_errors,
            "crc": "valid",
            "contrast": round(decoded.contrast, 2),
        },
        as_json=args.json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
