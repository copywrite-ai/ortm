from __future__ import annotations

import unittest

from ortm.codec import PAYLOAD_CELLS, DecodeError
from ortm.raster import RasterProfile, decode_luma_frame, render_luma_frame


class RasterTest(unittest.TestCase):
    def test_nominal_raster_round_trip(self) -> None:
        frame = render_luma_frame(321, 0x12345678)
        result = decode_luma_frame(frame)
        self.assertEqual(result.marker.frame_seq, 321)
        self.assertEqual(result.marker.timestamp_ms, 0x12345678)
        self.assertEqual(result.profile, RasterProfile())

    def test_scale_translation_and_reduced_contrast(self) -> None:
        actual = RasterProfile(x=28, y=16, cell=11.4, padding=11.4)
        frame = render_luma_frame(
            777,
            0x89ABCDEF,
            profile=actual,
            background=115,
            black=40,
            white=210,
        )
        result = decode_luma_frame(frame)
        self.assertEqual(result.marker.frame_seq, 777)
        self.assertEqual(result.marker.timestamp_ms, 0x89ABCDEF)
        self.assertAlmostEqual(result.profile.cell, actual.cell)
        self.assertEqual(result.profile.y, actual.y)
        self.assertIn(result.profile.x, (24, actual.x))
        self.assertEqual(result.marker.finder_errors, 0)
        self.assertEqual(result.marker.timing_errors, 0)
        self.assertGreaterEqual(result.contrast, 100)

    def test_raster_payload_damage_is_rejected(self) -> None:
        profile = RasterProfile()
        frame = render_luma_frame(100, 200)
        row, col = PAYLOAD_CELLS[30]
        x0 = round(profile.x + profile.padding + col * profile.cell)
        x1 = round(profile.x + profile.padding + (col + 1) * profile.cell)
        y0 = round(profile.y + profile.padding + row * profile.cell)
        y1 = round(profile.y + profile.padding + (row + 1) * profile.cell)
        replacement = 255 if frame[y0 + 1][x0 + 1] < 128 else 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                frame[y][x] = replacement
        with self.assertRaisesRegex(DecodeError, "crc-mismatch"):
            decode_luma_frame(frame, scales=(1.0,), offsets=(0,))

    def test_low_contrast_is_rejected(self) -> None:
        frame = render_luma_frame(1, 2, black=120, white=140)
        with self.assertRaisesRegex(DecodeError, "low-contrast"):
            decode_luma_frame(frame, scales=(1.0,), offsets=(0,))


if __name__ == "__main__":
    unittest.main()
