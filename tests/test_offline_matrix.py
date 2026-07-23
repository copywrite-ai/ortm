from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).parents[1] / "tools" / "run_offline_matrix.py"
SPEC = importlib.util.spec_from_file_location("run_offline_matrix", TOOL_PATH)
assert SPEC and SPEC.loader
matrix_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix_tool)


class OfflineMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = {
            "schema_version": 1,
            "name": "test-matrix",
            "base_scenario": "base.json",
            "seed": 7,
            "repetitions": 2,
            "warmup_runs": 0,
            "variants": [
                {"name": "baseline"},
                {"name": "fps30", "video": {"fps": 30, "key_int": 60}},
            ],
        }
        self.base = {
            "name": "base",
            "video": {"fps": 60, "key_int": 120, "bitrate_kbps": 2500},
            "marker": {"cell": 12, "background_alpha": 0.15},
            "cases": [{"name": "flat", "background": "flat"}],
        }

    def test_deep_merge_preserves_unmodified_sections(self) -> None:
        scenario = matrix_tool.build_scenario(
            self.matrix, self.base, self.matrix["variants"][1], 2
        )
        self.assertEqual(scenario["video"]["fps"], 30)
        self.assertEqual(scenario["video"]["key_int"], 60)
        self.assertEqual(scenario["video"]["bitrate_kbps"], 2500)
        self.assertEqual(scenario["marker"]["cell"], 12)
        self.assertEqual(scenario["matrix"]["repetition"], 2)

    def test_execution_plan_is_complete_and_deterministic(self) -> None:
        first = matrix_tool.execution_plan(self.matrix)
        second = matrix_tool.execution_plan(self.matrix)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertEqual(
            {(item["variant"], item["repetition"]) for item in first},
            {("baseline", 1), ("baseline", 2), ("fps30", 1), ("fps30", 2)},
        )
        self.assertEqual([item["order"] for item in first], [1, 2, 3, 4])

    def test_load_matrix_rejects_duplicate_variants(self) -> None:
        self.matrix["variants"][1]["name"] = "baseline"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "matrix.json"
            path.write_text(json.dumps(self.matrix), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                matrix_tool.load_matrix(path)

    def test_committed_formal_matrices_have_fixed_ten_second_runs(self) -> None:
        root = Path(__file__).parents[1]
        paths = sorted((root / "benchmarks/matrices").glob("*-formal.json"))
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            matrix = matrix_tool.load_matrix(path)
            base = matrix_tool.load_base_scenario(path, matrix)
            self.assertEqual(matrix["repetitions"], 5, msg=str(path))
            self.assertEqual(matrix["warmup_runs"], 1, msg=str(path))
            for variant in matrix["variants"]:
                scenario = matrix_tool.build_scenario(matrix, base, variant, 1)
                video = scenario["video"]
                self.assertEqual(
                    video["frames"] / video["fps"],
                    10,
                    msg=f"{path.name}:{variant['name']} must use ten seconds",
                )

    def test_aggregate_combines_repetitions_at_frame_level(self) -> None:
        case = {
            "name": "flat",
            "background": "flat",
            "expected_frames": 2,
            "successful_frames": 1,
            "actual_bitrate_kbps": 1000,
        }
        samples = [
            {
                "case": "flat",
                "background": "flat",
                "ok": True,
                "identity_match": True,
                "decode_ms": 1.0,
                "contrast": 100,
                "finder_errors": 0,
                "timing_errors": 0,
            },
            {
                "case": "flat",
                "background": "flat",
                "ok": False,
                "identity_match": False,
                "decode_ms": 2.0,
                "contrast": None,
                "finder_errors": None,
                "timing_errors": None,
            },
        ]
        records = [
            {"variant": "baseline", "summary": {"cases": [case]}, "samples": samples},
            {"variant": "baseline", "summary": {"cases": [case]}, "samples": samples},
        ]
        aggregate = matrix_tool.aggregate_runs(records)[0]
        self.assertEqual(aggregate["expected_frames"], 4)
        self.assertEqual(aggregate["successful_frames"], 2)
        self.assertEqual(aggregate["success_percent"], 50)
        self.assertEqual(aggregate["decode_ms"]["median"], 1.5)
        self.assertEqual(aggregate["contrast"]["count"], 2)

    def test_resume_rejects_changed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            matrix_tool.write_or_validate_input_manifest(
                output, self.matrix, self.base, resume=False
            )
            matrix_tool.write_or_validate_input_manifest(
                output, self.matrix, self.base, resume=True
            )
            changed = {**self.matrix, "seed": 99}
            with self.assertRaisesRegex(ValueError, "differs"):
                matrix_tool.write_or_validate_input_manifest(
                    output, changed, self.base, resume=True
                )


if __name__ == "__main__":
    unittest.main()
