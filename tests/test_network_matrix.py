from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).parents[1] / "tools" / "run_network_matrix.py"
SPEC = importlib.util.spec_from_file_location("run_network_matrix", TOOL_PATH)
assert SPEC and SPEC.loader
network = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(network)


class NetworkMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter_config = {
            "type": "docker-netem-tunnel-monitor-v1",
            "netem_container": "publisher",
            "netem_device": "eth0",
            "monitor_container": "monitor",
            "snapshot_url": "http://127.0.0.1:9010/api/snapshot",
            "stream": "fish_front",
        }

    def test_netem_command_is_structured_and_unit_explicit(self) -> None:
        adapter = network.DockerNetemAdapter(self.adapter_config)
        command = adapter.apply_command({
            "delay_ms": 50,
            "jitter_ms": 10,
            "loss_percent": 0.5,
            "rate_mbps": 3,
        })
        self.assertEqual(command[:3], ["docker", "exec", "publisher"])
        self.assertIn("50ms", command)
        self.assertIn("10ms", command)
        self.assertIn("0.5%", command)
        self.assertIn("3mbit", command)

    def test_snapshot_normalization_separates_readiness_and_clock_quality(self) -> None:
        raw = {
            "updatedAt": "2026-07-23T00:00:00Z",
            "derived": {"streams": {"fish_front": {
                "readers": 1,
                "viewer": {
                    "status": "playing", "ice": "connected", "ortm": 75,
                    "ortmRaw": 80, "clockUncertainty": 25,
                    "rtcPacketsLost": 2, "ortmDecodeAttempts": 10,
                },
                "publisher": {"encodedBitrateKbps": 2500, "actualFps": 60},
            }}},
        }
        sample = network.normalize_snapshot(
            raw,
            stream_name="fish_front",
            condition="clear",
            repetition=1,
            max_clock_uncertainty_ms=20,
        )
        self.assertTrue(sample["ready"])
        self.assertFalse(sample["clock_valid"])
        self.assertEqual(sample["ortm_ms"], 75)
        self.assertEqual(sample["publisher_bitrate_kbps"], 2500)

    def test_aggregate_reports_counter_delta_per_run(self) -> None:
        samples = [
            {"ready": True, "clock_valid": True, **{key: None for key in network.METRICS}, **{key: 0 for key in network.COUNTERS}},
            {"ready": True, "clock_valid": True, **{key: None for key in network.METRICS}, **{key: 0 for key in network.COUNTERS}},
        ]
        samples[0]["ortm_ms"] = 50
        samples[1]["ortm_ms"] = 70
        samples[1]["rtc_packets_lost"] = 3
        summary = network.summarize_samples(samples)
        records = [{"condition": "loss", "summary": summary, "samples": samples}]
        aggregate = network.aggregate_runs(records)[0]
        self.assertEqual(aggregate["metrics"]["ortm_ms"]["median"], 60)
        self.assertEqual(aggregate["run_counter_deltas"]["rtc_packets_lost"]["median"], 3)

    def test_run_quality_requires_each_sample_fraction(self) -> None:
        quality = network.evaluate_run_quality(
            {"samples": 10, "ready_samples": 9, "clock_valid_samples": 7},
            minimum_ready_fraction=0.8,
            minimum_clock_valid_fraction=0.8,
        )
        self.assertFalse(quality["ok"])
        self.assertEqual(quality["failures"], ["clock_valid_fraction"])

    def test_clock_sensitive_metrics_exclude_invalid_clock_samples(self) -> None:
        base = {
            "ready": True,
            **{key: None for key in network.METRICS},
            **{key: 0 for key in network.COUNTERS},
        }
        samples = [
            {**base, "clock_valid": True, "ortm_ms": 50, "rtc_fps": 60},
            {**base, "clock_valid": False, "ortm_ms": 5000, "rtc_fps": 30},
        ]
        summary = network.summarize_samples(samples)
        self.assertEqual(summary["metrics"]["ortm_ms"]["count"], 1)
        self.assertEqual(summary["metrics"]["ortm_ms"]["median"], 50)
        self.assertEqual(summary["metrics"]["rtc_fps"]["count"], 2)

    def test_guard_file_is_checked_before_netem_changes(self) -> None:
        config = {**self.adapter_config, "guard_pid_file": "/tmp/netem.pid"}
        adapter = network.DockerNetemAdapter(config)
        calls = []

        def fake_run(command, *, check=True):
            calls.append(command)
            return network.subprocess.CompletedProcess(command, 1, "guard present")

        adapter._run = fake_run
        with self.assertRaisesRegex(RuntimeError, "netem guard"):
            adapter.ensure_no_guard()
        self.assertEqual(calls[0][-4:], ["test", "!", "-f", "/tmp/netem.pid"])

    def test_network_metric_contract_includes_stall_diagnostics(self) -> None:
        self.assertIn("rtc_receive_decode_gap_frames", network.METRICS)
        self.assertIn("rvfc_gap_ms", network.METRICS)
        self.assertIn("rtc_freeze_duration_interval_ms", network.METRICS)
        self.assertIn("rtc_pause_duration_interval_ms", network.METRICS)
        self.assertNotIn("rtc_freeze_duration_interval_ms", network.COUNTERS)

    def test_committed_matrices_load_and_formal_policy_is_fixed(self) -> None:
        root = Path(__file__).parents[1]
        path_validation = network.load_matrix(
            root / "benchmarks/network/tunnel-direct-path-validation.json"
        )
        smoke = network.load_matrix(root / "benchmarks/network/tunnel-direct-single-factor-smoke.json")
        formal = network.load_matrix(root / "benchmarks/network/tunnel-direct-single-factor-formal.json")
        self.assertEqual(path_validation["observation_seconds"], 8)
        self.assertEqual(smoke["repetitions"], 1)
        self.assertEqual(formal["repetitions"], 5)
        self.assertEqual(formal["observation_seconds"], 60)
        self.assertEqual(formal["sample_interval_seconds"], 2)
        self.assertEqual(len(formal["conditions"]), 20)

    def test_resume_manifest_rejects_changed_matrix(self) -> None:
        matrix = {"name": "example"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "input.json"
            network.write_or_validate_manifest(path, matrix, resume=False)
            network.write_or_validate_manifest(path, matrix, resume=True)
            with self.assertRaisesRegex(ValueError, "differs"):
                network.write_or_validate_manifest(path, {"name": "changed"}, resume=True)


if __name__ == "__main__":
    unittest.main()
