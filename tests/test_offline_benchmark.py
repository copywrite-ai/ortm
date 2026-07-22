from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from ortm.raster import RasterProfile, decode_luma_frame


TOOL_PATH = Path(__file__).parents[1] / "tools" / "run_offline_benchmark.py"
SPEC = importlib.util.spec_from_file_location("run_offline_benchmark", TOOL_PATH)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class OfflineBenchmarkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = {
            "name": "test",
            "video": {
                "width": 640,
                "height": 480,
                "fps": 30,
                "frames": 2,
                "bitrate_kbps": 1000,
                "key_int": 30,
            },
            "marker": {
                "x": 24,
                "y": 24,
                "cell": 12,
                "padding": 12,
                "background_alpha": 0.15,
                "cell_alpha": 0.65,
            },
            "cases": [{"name": "flat", "background": "flat"}],
        }

    def test_renderer_round_trip_for_each_background(self) -> None:
        renderer = benchmark.FrameRenderer(self.scenario)
        profile = RasterProfile()
        for index, background in enumerate(("flat", "stripes", "moving-checker")):
            frame = renderer.render(background, index, 100 + index, 1000 + index)
            decoded = decode_luma_frame(
                benchmark.frame_rows(frame, renderer.width, renderer.height),
                nominal=profile,
            )
            self.assertEqual(decoded.marker.frame_seq, 100 + index)
            self.assertEqual(decoded.marker.timestamp_ms, 1000 + index)

    def test_percentile_interpolates(self) -> None:
        self.assertEqual(benchmark.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertEqual(benchmark.percentile([1], 0.99), 1)
        self.assertIsNone(benchmark.percentile([], 0.5))

    def test_scenario_rejects_unsafe_case_name(self) -> None:
        self.scenario["cases"][0]["name"] = "../escape"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "scenario.json"
            path.write_text(json.dumps(self.scenario), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "safe file name"):
                benchmark.load_scenario(path)


if __name__ == "__main__":
    unittest.main()
