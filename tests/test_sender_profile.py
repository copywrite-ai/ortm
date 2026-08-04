from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from ortm.codec import FINDER_SIZE, GRID_SIZE, TIMING_INDEX
from ortm.raster import RasterProfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "profiles" / "ortm-v0-fixed-720p.json"
MINIMAL_PROFILE_PATH = ROOT / "profiles" / "ortm-v0-minimal-720p.json"
FIXTURE_PATH = ROOT / "fixtures" / "ortm-v0-fixed-720p.png"


class SenderProfileTest(unittest.TestCase):
    def test_fixed_720p_profile_matches_reference_geometry(self) -> None:
        config = json.loads(PROFILE_PATH.read_text())
        frame = config["frame"]
        raster = config["raster"]
        rendering = config["rendering"]

        self.assertEqual(config["protocol"], "ORTM-v0")
        self.assertEqual((frame["width"], frame["height"]), (1280, 720))
        self.assertEqual(raster["gridSize"], GRID_SIZE)
        self.assertEqual(raster["finderSize"], FINDER_SIZE)
        self.assertEqual(raster["timingIndex"], TIMING_INDEX)
        self.assertEqual(
            RasterProfile(
                x=raster["x"],
                y=raster["y"],
                cell=raster["cell"],
                padding=raster["padding"],
            ),
            RasterProfile(),
        )
        self.assertEqual(raster["boxSize"], GRID_SIZE * raster["cell"] + 2 * raster["padding"])
        self.assertLessEqual(raster["x"] + raster["boxSize"], frame["width"])
        self.assertLessEqual(raster["y"] + raster["boxSize"], frame["height"])
        self.assertEqual(rendering["backgroundAlpha"], 0.15)
        self.assertEqual(rendering["cellAlpha"], 0.65)
        self.assertFalse(rendering["antialias"])

    def test_reference_fixture_is_a_1280x720_png(self) -> None:
        data = FIXTURE_PATH.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (1280, 720))

    def test_minimal_720p_profile_uses_validated_sparse_rendering(self) -> None:
        config = json.loads(MINIMAL_PROFILE_PATH.read_text())
        raster = config["raster"]
        rendering = config["rendering"]

        self.assertEqual(config["protocol"], "ORTM-v0")
        self.assertEqual((raster["x"], raster["y"]), (32, 32))
        self.assertEqual((raster["cell"], raster["padding"]), (8, 16))
        self.assertEqual(raster["boxSize"], 288)
        self.assertEqual(rendering["backgroundAlpha"], 0)
        self.assertEqual(rendering["cellAlpha"], 0.70)
        self.assertEqual(rendering["borderAlpha"], 0)


if __name__ == "__main__":
    unittest.main()
