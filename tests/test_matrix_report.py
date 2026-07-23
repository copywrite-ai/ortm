from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).parents[1] / "tools" / "render_matrix_report.py"
SPEC = importlib.util.spec_from_file_location("render_matrix_report", TOOL_PATH)
assert SPEC and SPEC.loader
report_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report_tool)


class MatrixReportTest(unittest.TestCase):
    def test_report_labels_offline_results_and_formats_aggregates(self) -> None:
        summary = {
            "matrix": {
                "name": "example",
                "seed": 7,
                "repetitions": 2,
                "warmup_runs": 1,
                "variants": [{"name": "baseline", "description": "Reference"}],
            },
            "completed_runs": 2,
            "overall": {
                "expected_frames": 20,
                "successful_frames": 20,
                "success_percent": 100,
            },
            "aggregates": [{
                "variant": "baseline",
                "background": "flat",
                "success_percent": 100,
                "actual_bitrate_kbps": {"median": 1234.567},
                "decode_ms": {"p95": 1.23456, "max": 2.34567},
                "contrast": {"median": 166},
            }],
        }
        report = report_tool.render_report(summary, "benchmark-results/example")
        normalized = " ".join(report.split())
        self.assertIn("not G2G latency measurements", normalized)
        self.assertIn("20 / 20 (100.00%)", report)
        self.assertIn("1234.57 kbps", report)
        self.assertIn("1.235 ms", report)
        self.assertIn("2.346 ms", report)
        self.assertIn("`baseline`: Reference", report)

    def test_variant_without_description_reports_exact_overrides(self) -> None:
        variant = {"name": "fps30", "video": {"fps": 30, "frames": 300}}
        self.assertEqual(
            report_tool.describe_variant(variant),
            'Overrides `{"video":{"fps":30,"frames":300}}`.',
        )

    def test_codec_matrix_interpretation_does_not_claim_visual_equivalence(self) -> None:
        summary = {
            "matrix": {
                "variants": [
                    {"name": "h264", "video": {"codec": "h264"}},
                    {"name": "vp9", "video": {"codec": "vp9"}},
                ]
            },
            "overall": {
                "expected_frames": 10,
                "successful_frames": 10,
                "success_percent": 100,
            },
            "aggregates": [{"decode_ms": {"p95": 2.5, "max": 3.5}}],
        }
        result = " ".join(report_tool.interpretation(summary))
        self.assertIn("survivability result", result)
        self.assertIn("claim of equivalent visual quality", result)
        self.assertNotIn("opaque marker", result)


if __name__ == "__main__":
    unittest.main()
