#!/usr/bin/env python3
"""Generate committed ORTM v0 conformance vectors."""

from __future__ import annotations

import json
from pathlib import Path

from ortm.codec import crc_input, crc16_ccitt_false, encode_grid, grid_rows

CASES = (
    ("zero", 0, 0),
    ("sample", 0x1234, 0x89ABCDEF),
    ("timestamp-wrap-edge", 42, 0xFFFFFFFA),
    ("maximum", 0xFFFF, 0xFFFFFFFF),
)


def main() -> None:
    vectors = {
        "format": "ORTM-v0",
        "bit_order": "msb-first",
        "crc": "CRC-16/CCITT-FALSE",
        "vectors": [],
    }
    for name, frame_seq, timestamp_ms in CASES:
        crc_bytes = crc_input(0, frame_seq, timestamp_ms)
        vectors["vectors"].append(
            {
                "name": name,
                "version": 0,
                "frame_seq": frame_seq,
                "timestamp_ms": timestamp_ms,
                "crc_input_hex": crc_bytes.hex(),
                "crc16_hex": f"{crc16_ccitt_false(crc_bytes):04x}",
                "grid": grid_rows(encode_grid(frame_seq, timestamp_ms)),
            }
        )
    output = Path(__file__).resolve().parents[1] / "vectors" / "ortm-v0.json"
    output.write_text(json.dumps(vectors, indent=2) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
