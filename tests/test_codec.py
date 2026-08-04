from __future__ import annotations

import json
import unittest
from pathlib import Path

from ortm.codec import (
    PAYLOAD_CELLS,
    FINDER_LAYOUT_THREE,
    FINDER_LAYOUT_TWO_TOP,
    DecodeError,
    crc16_ccitt_false,
    decode_grid,
    encode_grid,
    encoded_cells,
    frame_age_ms,
    grid_rows,
    rows_to_grid,
)

ROOT = Path(__file__).resolve().parents[1]


class CodecTest(unittest.TestCase):
    def test_standard_crc_check_value(self) -> None:
        self.assertEqual(crc16_ccitt_false(b"123456789"), 0x29B1)

    def test_golden_vectors(self) -> None:
        document = json.loads((ROOT / "vectors" / "ortm-v0.json").read_text(encoding="ascii"))
        for vector in document["vectors"]:
            with self.subTest(vector=vector["name"]):
                grid = encode_grid(vector["frame_seq"], vector["timestamp_ms"])
                self.assertEqual(grid_rows(grid), vector["grid"])
                decoded = decode_grid(rows_to_grid(vector["grid"]))
                self.assertEqual(decoded.version, vector["version"])
                self.assertEqual(decoded.frame_seq, vector["frame_seq"])
                self.assertEqual(decoded.timestamp_ms, vector["timestamp_ms"])
                self.assertEqual(f"{decoded.crc16:04x}", vector["crc16_hex"])

    def test_payload_corruption_is_rejected_by_crc(self) -> None:
        grid = encode_grid(123, 0x12345678)
        row, col = PAYLOAD_CELLS[20]
        grid[row][col] ^= 1
        with self.assertRaisesRegex(DecodeError, "crc-mismatch"):
            decode_grid(grid)

    def test_structure_corruption_is_rejected(self) -> None:
        grid = encode_grid(123, 0x12345678)
        damaged = 0
        for row in range(4):
            for col in range(4):
                grid[row][col] ^= 1
                damaged += 1
                if damaged == 9:
                    break
            if damaged == 9:
                break
        with self.assertRaisesRegex(DecodeError, "structure-mismatch"):
            decode_grid(grid)

    def test_timestamp_rollover(self) -> None:
        self.assertEqual(frame_age_ms(3, 0xFFFFFFFA), 9)

    def test_implausible_age_is_rejected(self) -> None:
        with self.assertRaisesRegex(DecodeError, "latency-out-of-range"):
            frame_age_ms(6000, 0)

    def test_sequence_rollover_values_are_valid(self) -> None:
        self.assertEqual(decode_grid(encode_grid(0xFFFF, 1)).frame_seq, 0xFFFF)
        self.assertEqual(decode_grid(encode_grid(0, 2)).frame_seq, 0)

    def test_unsupported_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(DecodeError, "unsupported-version"):
            decode_grid(encode_grid(1, 2, version=1))

    def test_three_finder_layout_requires_layout_aware_decoder(self) -> None:
        grid = encode_grid(
            321,
            0x12345678,
            finder_layout=FINDER_LAYOUT_THREE,
        )
        with self.assertRaisesRegex(DecodeError, "structure-mismatch"):
            decode_grid(grid)

        decoded = decode_grid(grid, finder_layout=FINDER_LAYOUT_THREE)
        self.assertEqual(decoded.frame_seq, 321)
        self.assertEqual(decoded.timestamp_ms, 0x12345678)
        self.assertEqual(len(encoded_cells(FINDER_LAYOUT_THREE)), len(encoded_cells()) - 16)

    def test_two_top_layout_requires_layout_aware_decoder(self) -> None:
        grid = encode_grid(
            654,
            0x89ABCDEF,
            finder_layout=FINDER_LAYOUT_TWO_TOP,
        )
        with self.assertRaisesRegex(DecodeError, "structure-mismatch"):
            decode_grid(grid)

        decoded = decode_grid(grid, finder_layout=FINDER_LAYOUT_TWO_TOP)
        self.assertEqual(decoded.frame_seq, 654)
        self.assertEqual(decoded.timestamp_ms, 0x89ABCDEF)
        self.assertEqual(len(encoded_cells(FINDER_LAYOUT_TWO_TOP)), len(encoded_cells()) - 32)


if __name__ == "__main__":
    unittest.main()
