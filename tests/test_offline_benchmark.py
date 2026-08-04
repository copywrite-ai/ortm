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
                "border_alpha": 1.0,
            },
            "cases": [{"name": "flat", "background": "flat"}],
        }

    def test_renderer_round_trip_for_each_background(self) -> None:
        renderer = benchmark.FrameRenderer(self.scenario)
        profile = RasterProfile()
        for index, background in enumerate(("flat", "stripes", "moving-checker", "snow")):
            frame = renderer.render(background, index, 100 + index, 1000 + index)
            decoded = decode_luma_frame(
                benchmark.frame_rows(frame, renderer.width, renderer.height),
                nominal=profile,
            )
            self.assertEqual(decoded.marker.frame_seq, 100 + index)
            self.assertEqual(decoded.marker.timestamp_ms, 1000 + index)

    def test_sparse_marker_decodes_on_moving_background(self) -> None:
        self.scenario["marker"].update({
            "background_alpha": 0,
            "cell_alpha": 0.70,
            "border_alpha": 0,
        })
        renderer = benchmark.FrameRenderer(self.scenario)
        frame = renderer.render("moving-checker", 7, 321, 123456)
        decoded = decode_luma_frame(
            benchmark.frame_rows(frame, renderer.width, renderer.height),
            nominal=RasterProfile(),
        )
        self.assertEqual(decoded.marker.frame_seq, 321)
        self.assertEqual(decoded.marker.timestamp_ms, 123456)

    def test_snow_background_is_deterministic_and_changes_per_frame(self) -> None:
        renderer = benchmark.FrameRenderer(self.scenario)
        first = renderer.background_frame("snow", 10)
        self.assertEqual(first, renderer.background_frame("snow", 10))
        self.assertNotEqual(first, renderer.background_frame("snow", 11))

    def test_three_finder_marker_decodes_with_matching_layout(self) -> None:
        self.scenario["marker"].update({
            "background_alpha": 0,
            "cell_alpha": 0.70,
            "border_alpha": 0,
            "finder_layout": "three",
        })
        renderer = benchmark.FrameRenderer(self.scenario)
        frame = renderer.render("snow", 3, 987, 654321)
        decoded = decode_luma_frame(
            benchmark.frame_rows(frame, renderer.width, renderer.height),
            nominal=RasterProfile(),
            finder_layout="three",
        )
        self.assertEqual(decoded.marker.frame_seq, 987)
        self.assertEqual(decoded.marker.timestamp_ms, 654321)

    def test_two_top_marker_decodes_with_matching_layout(self) -> None:
        self.scenario["marker"].update({
            "background_alpha": 0,
            "cell_alpha": 0.70,
            "border_alpha": 0,
            "finder_layout": "two-top",
        })
        renderer = benchmark.FrameRenderer(self.scenario)
        frame = renderer.render("snow", 4, 1234, 7654321)
        decoded = decode_luma_frame(
            benchmark.frame_rows(frame, renderer.width, renderer.height),
            nominal=RasterProfile(),
            finder_layout="two-top",
        )
        self.assertEqual(decoded.marker.frame_seq, 1234)
        self.assertEqual(decoded.marker.timestamp_ms, 7654321)

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

    def test_codec_profiles_use_reproducible_encoders_and_containers(self) -> None:
        expected = {
            "h264": ("libx264", ".h264", "h264"),
            "vp8": ("libvpx", ".ivf", "ivf"),
            "vp9": ("libvpx-vp9", ".ivf", "ivf"),
            "av1": ("libsvtav1", ".ivf", "ivf"),
        }
        for codec, values in expected.items():
            video = {**self.scenario["video"], "codec": codec}
            settings = benchmark.codec_settings(video)
            self.assertEqual(
                (settings["encoder"], settings["extension"], settings["muxer"]),
                values,
            )
        av1_arguments = benchmark.codec_settings({
            **self.scenario["video"], "codec": "av1"
        })["arguments"]
        self.assertIn("-maxrate", av1_arguments)
        self.assertEqual(av1_arguments[av1_arguments.index("-preset") + 1], "11")
        self.assertEqual(
            av1_arguments[av1_arguments.index("-svtav1-params") + 1],
            "pred-struct=1",
        )

    def test_scenario_defaults_to_h264_and_rejects_unknown_codec(self) -> None:
        self.assertEqual(benchmark.codec_name(self.scenario["video"]), "h264")
        self.scenario["video"]["codec"] = "unknown"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "scenario.json"
            path.write_text(json.dumps(self.scenario), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported codec"):
                benchmark.load_scenario(path)


if __name__ == "__main__":
    unittest.main()
