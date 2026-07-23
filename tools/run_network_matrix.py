#!/usr/bin/env python3
"""Run randomized ORTM live-network impairment matrices via Docker netem."""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import re
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")
METRICS = (
    "ortm_ms",
    "ortm_raw_ms",
    "ortm_net_ms",
    "upstream_ms",
    "upstream_net_ms",
    "browser_ms",
    "sample_age_ms",
    "frame_stall_ms",
    "rtc_jitter_ms",
    "rtc_jb_target_ms",
    "rtc_freeze_duration_interval_ms",
    "rtc_pause_duration_interval_ms",
    "rtc_receive_decode_gap_frames",
    "rtc_frame_interval_ms",
    "rtc_fps",
    "rtc_recv_fps",
    "rtc_decode_fps",
    "rtc_bitrate_kbps",
    "rvfc_gap_ms",
    "rvfc_lead_ms",
    "rvfc_presentation_age_ms",
    "ortm_decode_success_rate",
    "clock_offset_ms",
    "clock_rtt_ms",
    "clock_uncertainty_ms",
    "publisher_bitrate_kbps",
    "publisher_fps",
    "publisher_overlay_to_send_ms",
)
CLOCK_SENSITIVE_METRICS = {
    "ortm_ms",
    "ortm_raw_ms",
    "ortm_net_ms",
    "upstream_ms",
    "upstream_net_ms",
}
COUNTERS = (
    "rtc_packets_lost",
    "rtc_freeze_count",
    "rtc_pause_count",
    "rtc_drop_count",
    "rvfc_presented",
    "ortm_decode_attempts",
    "ortm_decode_successes",
    "ortm_decode_failures",
    "ortm_crc_failures",
    "ortm_structure_failures",
    "ortm_low_contrast_failures",
    "ortm_latency_range_failures",
)


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    data = list(values)
    return {
        "count": len(data),
        "min": min(data) if data else None,
        "median": percentile(data, 0.5),
        "p95": percentile(data, 0.95),
        "p99": percentile(data, 0.99),
        "max": max(data) if data else None,
    }


def load_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    if int(matrix.get("schema_version", 0)) != 1:
        raise ValueError("matrix.schema_version must be 1")
    allowed = {
        "schema_version", "name", "description", "seed", "repetitions",
        "warmup_seconds", "observation_seconds", "sample_interval_seconds",
        "adapter", "conditions",
    }
    unknown = set(matrix) - allowed
    if unknown:
        raise ValueError(f"matrix has unknown keys: {sorted(unknown)}")
    if not SAFE_NAME.fullmatch(str(matrix.get("name", ""))):
        raise ValueError("matrix.name is not a safe file name")
    for key in ("adapter", "conditions"):
        if key not in matrix:
            raise ValueError(f"matrix is missing {key!r}")
    for key in ("repetitions", "observation_seconds", "sample_interval_seconds"):
        if float(matrix.get(key, 0)) <= 0:
            raise ValueError(f"matrix.{key} must be positive")
    if float(matrix.get("warmup_seconds", 0)) < 0:
        raise ValueError("matrix.warmup_seconds must be non-negative")
    adapter = matrix["adapter"]
    if adapter.get("type") != "docker-netem-tunnel-monitor-v1":
        raise ValueError("unsupported adapter.type")
    for key in (
        "netem_container", "netem_device", "monitor_container",
        "snapshot_url", "stream",
    ):
        if not str(adapter.get(key, "")).strip():
            raise ValueError(f"adapter.{key} is required")
    for key in ("minimum_ready_fraction", "minimum_clock_valid_fraction"):
        value = finite_number(adapter.get(key, 0.8))
        if value is None or not 0 <= value <= 1:
            raise ValueError(f"adapter.{key} must be between 0 and 1")
    conditions = matrix["conditions"]
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("matrix.conditions must not be empty")
    names = []
    for condition in conditions:
        unknown_condition = set(condition) - {"name", "description", "impairment"}
        if unknown_condition:
            raise ValueError(
                f"condition {condition.get('name', '')!r} has unknown keys: "
                f"{sorted(unknown_condition)}"
            )
        name = str(condition.get("name", ""))
        if not SAFE_NAME.fullmatch(name):
            raise ValueError(f"condition name is not safe: {name!r}")
        validate_impairment(condition.get("impairment", {}))
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("condition names must be unique")
    return matrix


def validate_impairment(impairment: dict[str, Any]) -> None:
    allowed = {"clear", "delay_ms", "jitter_ms", "loss_percent", "rate_mbps"}
    unknown = set(impairment) - allowed
    if unknown:
        raise ValueError(f"impairment has unknown keys: {sorted(unknown)}")
    if impairment.get("clear"):
        if len(impairment) != 1:
            raise ValueError("clear impairment cannot include netem parameters")
        return
    delay = finite_number(impairment.get("delay_ms", 0))
    jitter = finite_number(impairment.get("jitter_ms", 0))
    loss = finite_number(impairment.get("loss_percent", 0))
    rate = finite_number(impairment.get("rate_mbps"))
    if delay is None or delay < 0:
        raise ValueError("impairment.delay_ms must be non-negative")
    if jitter is None or jitter < 0:
        raise ValueError("impairment.jitter_ms must be non-negative")
    if loss is None or not 0 <= loss <= 100:
        raise ValueError("impairment.loss_percent must be between 0 and 100")
    if rate is not None and rate <= 0:
        raise ValueError("impairment.rate_mbps must be positive")
    if not any(value > 0 for value in (delay, jitter, loss)) and rate is None:
        raise ValueError("non-clear impairment must configure at least one parameter")


def execution_plan(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    plan = [
        {"condition": condition["name"], "repetition": repetition}
        for condition in matrix["conditions"]
        for repetition in range(1, int(matrix["repetitions"]) + 1)
    ]
    random.Random(int(matrix.get("seed", 0))).shuffle(plan)
    return [{"order": index, **item} for index, item in enumerate(plan, 1)]


class DockerNetemAdapter:
    def __init__(self, config: dict[str, Any], docker: str = "docker") -> None:
        self.config = config
        self.docker = docker

    def _run(self, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def clear(self) -> str:
        command = [
            self.docker, "exec", self.config["netem_container"], "tc", "qdisc",
            "del", "dev", self.config["netem_device"], "root",
        ]
        completed = self._run(command, check=False)
        return completed.stdout

    def ensure_no_guard(self) -> None:
        guard_pid_file = self.config.get("guard_pid_file")
        if not guard_pid_file:
            return
        command = [
            self.docker, "exec", self.config["netem_container"],
            "test", "!", "-f", str(guard_pid_file),
        ]
        completed = self._run(command, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"netem guard is active or stale at {guard_pid_file}; "
                "clear it before running the matrix"
            )

    def apply_command(self, impairment: dict[str, Any]) -> list[str]:
        if impairment.get("clear"):
            return []
        command = [
            self.docker, "exec", self.config["netem_container"], "tc", "qdisc",
            "replace", "dev", self.config["netem_device"], "root", "netem",
        ]
        delay = finite_number(impairment.get("delay_ms", 0)) or 0
        jitter = finite_number(impairment.get("jitter_ms", 0)) or 0
        loss = finite_number(impairment.get("loss_percent", 0)) or 0
        rate = finite_number(impairment.get("rate_mbps"))
        if delay > 0 or jitter > 0:
            command.extend(["delay", f"{delay:g}ms"])
            if jitter > 0:
                command.extend([f"{jitter:g}ms", "distribution", "normal"])
        if loss > 0:
            command.extend(["loss", f"{loss:g}%"])
        if rate is not None:
            command.extend(["rate", f"{rate:g}mbit"])
        return command

    def apply(self, impairment: dict[str, Any]) -> tuple[list[str], str]:
        self.clear()
        command = self.apply_command(impairment)
        if not command:
            return command, "netem cleared\n"
        completed = self._run(command)
        return command, completed.stdout

    def show(self) -> str:
        command = [
            self.docker, "exec", self.config["netem_container"], "tc", "-s", "qdisc",
            "show", "dev", self.config["netem_device"],
        ]
        return self._run(command).stdout

    def snapshot(self) -> dict[str, Any]:
        command = [
            self.docker, "exec", self.config["monitor_container"], "wget", "-qO-",
            self.config["snapshot_url"],
        ]
        completed = self._run(command)
        return json.loads(completed.stdout)


def normalize_snapshot(
    raw: dict[str, Any],
    *,
    stream_name: str,
    condition: str,
    repetition: int,
    max_clock_uncertainty_ms: float,
) -> dict[str, Any]:
    stream = raw.get("derived", {}).get("streams", {}).get(stream_name, {}) or {}
    viewer = stream.get("viewer", {}) or {}
    publisher = stream.get("publisher", {}) or {}
    uncertainty = finite_number(viewer.get("clockUncertainty"))
    ice = str(viewer.get("ice") or "")
    status = str(viewer.get("status") or "")
    ready = (
        int(stream.get("readers") or 0) > 0
        and status == "playing"
        and ice in {"connected", "completed"}
        and finite_number(viewer.get("ortm")) is not None
    )
    sample = {
        "observed_at": raw.get("updatedAt"),
        "condition": condition,
        "repetition": repetition,
        "ready": ready,
        "clock_valid": uncertainty is not None and uncertainty <= max_clock_uncertainty_ms,
        "readers": int(stream.get("readers") or 0),
        "viewer_status": status,
        "ice": ice,
        "resolution": viewer.get("resolution"),
        "ortm_ms": finite_number(viewer.get("ortm")),
        "ortm_raw_ms": finite_number(viewer.get("ortmRaw")),
        "ortm_net_ms": finite_number(viewer.get("ortmNet")),
        "upstream_ms": finite_number(viewer.get("upstream")),
        "upstream_net_ms": finite_number(viewer.get("upstreamNet")),
        "browser_ms": finite_number(viewer.get("browser")),
        "sample_age_ms": finite_number(viewer.get("ortmSampleAge")),
        "frame_stall_ms": finite_number(viewer.get("ortmFrameStall")),
        "rtc_jitter_ms": finite_number(viewer.get("rtcJitter")),
        "rtc_jb_target_ms": finite_number(viewer.get("rtcJbTarget")),
        "rtc_receive_decode_gap_frames": finite_number(viewer.get("rtcRecvGap")),
        "rtc_frame_interval_ms": finite_number(viewer.get("rtcFrameInt")),
        "rtc_fps": finite_number(viewer.get("rtcFps")),
        "rtc_recv_fps": finite_number(viewer.get("rtcRecvFps")),
        "rtc_decode_fps": finite_number(viewer.get("rtcDecFps")),
        "rtc_bitrate_kbps": finite_number(viewer.get("rtcBitrate")),
        "rvfc_gap_ms": finite_number(viewer.get("rvfcGap")),
        "rvfc_lead_ms": finite_number(viewer.get("rvfcLead")),
        "rvfc_presentation_age_ms": finite_number(viewer.get("rvfcPresentationAge")),
        "ortm_decode_success_rate": finite_number(viewer.get("ortmDecodeSuccessRate")),
        "clock_offset_ms": finite_number(viewer.get("clockOffset")),
        "clock_rtt_ms": finite_number(viewer.get("clockRtt")),
        "clock_uncertainty_ms": uncertainty,
        "publisher_bitrate_kbps": finite_number(publisher.get("encodedBitrateKbps")),
        "publisher_fps": finite_number(publisher.get("actualFps")),
        "publisher_overlay_to_send_ms": finite_number(publisher.get("overlayToSendAvgMs")),
        "rtc_packets_lost": finite_number(viewer.get("rtcPacketsLost")),
        "rtc_freeze_count": finite_number(viewer.get("rtcFreezeCount")),
        "rtc_freeze_duration_interval_ms": finite_number(viewer.get("rtcFreezeDur")),
        "rtc_pause_count": finite_number(viewer.get("rtcPauseCount")),
        "rtc_pause_duration_interval_ms": finite_number(viewer.get("rtcPauseDur")),
        "rtc_drop_count": finite_number(viewer.get("rtcDrop")),
        "rvfc_presented": finite_number(viewer.get("rvfcPresented")),
        "ortm_decode_attempts": finite_number(viewer.get("ortmDecodeAttempts")),
        "ortm_decode_successes": finite_number(viewer.get("ortmDecodeSuccesses")),
        "ortm_decode_failures": finite_number(viewer.get("ortmDecodeFailures")),
        "ortm_crc_failures": finite_number(viewer.get("ortmCrcFailures")),
        "ortm_structure_failures": finite_number(viewer.get("ortmStructureFailures")),
        "ortm_low_contrast_failures": finite_number(viewer.get("ortmLowContrastFailures")),
        "ortm_latency_range_failures": finite_number(viewer.get("ortmLatencyRangeFailures")),
    }
    return sample


def counter_delta(samples: list[dict[str, Any]], key: str) -> float | None:
    values = [sample[key] for sample in samples if sample.get(key) is not None]
    if len(values) < 2:
        return None
    return max(0.0, values[-1] - values[0])


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    ready = [sample for sample in samples if sample["ready"]]
    clock_valid = [sample for sample in ready if sample["clock_valid"]]
    return {
        "samples": len(samples),
        "ready_samples": len(ready),
        "clock_valid_samples": len(clock_valid),
        "metrics": {
            key: distribution(
                sample[key]
                for sample in (
                    clock_valid if key in CLOCK_SENSITIVE_METRICS else ready
                )
                if sample.get(key) is not None
            )
            for key in METRICS
        },
        "counter_deltas": {key: counter_delta(ready, key) for key in COUNTERS},
    }


def evaluate_run_quality(
    summary: dict[str, Any],
    *,
    minimum_ready_fraction: float,
    minimum_clock_valid_fraction: float,
) -> dict[str, Any]:
    count = int(summary["samples"])
    ready_fraction = summary["ready_samples"] / count if count else 0.0
    clock_valid_fraction = summary["clock_valid_samples"] / count if count else 0.0
    failures = []
    if ready_fraction < minimum_ready_fraction:
        failures.append("ready_fraction")
    if clock_valid_fraction < minimum_clock_valid_fraction:
        failures.append("clock_valid_fraction")
    return {
        "ok": not failures,
        "ready_fraction": ready_fraction,
        "clock_valid_fraction": clock_valid_fraction,
        "minimum_ready_fraction": minimum_ready_fraction,
        "minimum_clock_valid_fraction": minimum_clock_valid_fraction,
        "failures": failures,
    }


def prepare_output(path: Path, *, overwrite: bool, resume: bool) -> None:
    resolved = path.resolve()
    if resolved in (Path.cwd().resolve(), Path(resolved.anchor)):
        raise ValueError(f"refusing unsafe output directory: {resolved}")
    if path.exists():
        if overwrite:
            shutil.rmtree(path)
        elif not resume:
            raise FileExistsError(f"output already exists: {path}; use --overwrite or --resume")
    path.mkdir(parents=True, exist_ok=True)


def write_or_validate_manifest(path: Path, matrix: dict[str, Any], *, resume: bool) -> None:
    manifest = {"matrix": matrix}
    if resume and path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("cannot resume: matrix differs from output/input.json")
        return
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def wait_until_ready(
    adapter: DockerNetemAdapter,
    matrix: dict[str, Any],
    task: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    config = matrix["adapter"]
    deadline = time.monotonic() + float(config.get("ready_timeout_seconds", 60))
    max_uncertainty = float(config.get("max_clock_uncertainty_ms", 20))
    with (output / "readiness.jsonl").open("w", encoding="utf-8") as log:
        while True:
            raw = adapter.snapshot()
            sample = normalize_snapshot(
                raw,
                stream_name=config["stream"],
                condition=task["condition"],
                repetition=task["repetition"],
                max_clock_uncertainty_ms=max_uncertainty,
            )
            log.write(json.dumps(sample, sort_keys=True) + "\n")
            log.flush()
            if sample["ready"]:
                return sample
            if time.monotonic() >= deadline:
                raise TimeoutError("viewer did not become ready before timeout")
            time.sleep(min(2.0, float(matrix["sample_interval_seconds"])))


def sample_condition(
    adapter: DockerNetemAdapter,
    matrix: dict[str, Any],
    task: dict[str, Any],
    output: Path,
) -> list[dict[str, Any]]:
    config = matrix["adapter"]
    interval = float(matrix["sample_interval_seconds"])
    sample_count = math.ceil(float(matrix["observation_seconds"]) / interval)
    started = time.monotonic()
    samples = []
    with (output / "raw-snapshots.jsonl").open("w", encoding="utf-8") as raw_log, (
        output / "samples.jsonl"
    ).open("w", encoding="utf-8") as sample_log:
        for sample_index in range(sample_count):
            wait = started + sample_index * interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            raw = adapter.snapshot()
            sample = normalize_snapshot(
                raw,
                stream_name=config["stream"],
                condition=task["condition"],
                repetition=task["repetition"],
                max_clock_uncertainty_ms=float(config.get("max_clock_uncertainty_ms", 20)),
            )
            raw_log.write(json.dumps(raw, sort_keys=True) + "\n")
            sample_log.write(json.dumps(sample, sort_keys=True) + "\n")
            raw_log.flush()
            sample_log.flush()
            samples.append(sample)
    return samples


def aggregate_runs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["condition"]].append(record)
    result = []
    for condition, runs in sorted(groups.items()):
        samples = [sample for run in runs for sample in run["samples"]]
        summary = summarize_samples(samples)
        result.append({
            "condition": condition,
            "repetitions": len(runs),
            **summary,
            "run_counter_deltas": {
                key: distribution(
                    value
                    for run in runs
                    if (value := run["summary"]["counter_deltas"].get(key)) is not None
                )
                for key in COUNTERS
            },
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--dry-run", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--overwrite", action="store_true")
    mode.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    matrix = load_matrix(args.matrix)
    conditions = {condition["name"]: condition for condition in matrix["conditions"]}
    plan = execution_plan(matrix)
    if args.dry_run:
        adapter = DockerNetemAdapter(matrix["adapter"], docker=args.docker)
        print(json.dumps({
            "matrix": matrix["name"],
            "plan": plan,
            "commands": {
                name: adapter.apply_command(condition["impairment"])
                for name, condition in conditions.items()
            },
        }, indent=2, sort_keys=True))
        return 0
    if not shutil.which(args.docker):
        parser.error(f"Docker executable not found: {args.docker}")

    prepare_output(args.output, overwrite=args.overwrite, resume=args.resume)
    write_or_validate_manifest(args.output / "input.json", matrix, resume=args.resume)
    adapter = DockerNetemAdapter(matrix["adapter"], docker=args.docker)
    records = []
    failures = []
    quality_failures = []
    adapter.ensure_no_guard()
    try:
        adapter.clear()
        for task in plan:
            condition = conditions[task["condition"]]
            output = args.output / "runs" / (
                f"{task['order']:03d}-{task['condition']}-r{task['repetition']:02d}"
            )
            result_path = output / "result.json"
            samples_path = output / "samples.jsonl"
            if args.resume and result_path.exists() and samples_path.exists():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                samples = [json.loads(line) for line in samples_path.read_text(encoding="utf-8").splitlines() if line]
                records.append({**task, "summary": result["summary"], "samples": samples})
                quality = result.get("quality") or evaluate_run_quality(
                    result["summary"],
                    minimum_ready_fraction=float(
                        matrix["adapter"].get("minimum_ready_fraction", 0.8)
                    ),
                    minimum_clock_valid_fraction=float(
                        matrix["adapter"].get("minimum_clock_valid_fraction", 0.8)
                    ),
                )
                if not quality["ok"]:
                    quality_failures.append({**task, "quality": quality})
                print(f"[{task['order']:03d}/{len(plan):03d}] reuse {task['condition']} r{task['repetition']}", flush=True)
                continue
            output.mkdir(parents=True, exist_ok=True)
            print(f"[{task['order']:03d}/{len(plan):03d}] apply {task['condition']} r{task['repetition']}", flush=True)
            started_at = datetime.now(UTC).isoformat()
            try:
                command, apply_output = adapter.apply(condition["impairment"])
                (output / "apply.log").write_text(apply_output + adapter.show(), encoding="utf-8")
                wait_until_ready(adapter, matrix, task, output)
                warmup = float(matrix.get("warmup_seconds", 0))
                if warmup > 0:
                    time.sleep(warmup)
                samples = sample_condition(adapter, matrix, task, output)
                summary = summarize_samples(samples)
                quality = evaluate_run_quality(
                    summary,
                    minimum_ready_fraction=float(
                        matrix["adapter"].get("minimum_ready_fraction", 0.8)
                    ),
                    minimum_clock_valid_fraction=float(
                        matrix["adapter"].get("minimum_clock_valid_fraction", 0.8)
                    ),
                )
                result = {
                    **task,
                    "started_at": started_at,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "condition_config": copy.deepcopy(condition),
                    "apply_command": command,
                    "summary": summary,
                    "quality": quality,
                }
                result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                records.append({**task, "summary": summary, "samples": samples})
                if not quality["ok"]:
                    quality_failures.append({**task, "quality": quality})
            except Exception as error:
                failures.append({**task, "error": str(error)})
                (output / "error.txt").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
            finally:
                try:
                    (output / "qdisc-after.log").write_text(
                        adapter.show(), encoding="utf-8"
                    )
                except Exception as error:
                    (output / "qdisc-after-error.txt").write_text(
                        f"{type(error).__name__}: {error}\n", encoding="utf-8"
                    )
                adapter.clear()
                time.sleep(float(matrix["sample_interval_seconds"]))
    finally:
        adapter.clear()

    aggregates = aggregate_runs(records)
    result = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "matrix": matrix,
        "execution_plan": plan,
        "completed_runs": len(records),
        "infrastructure_failures": failures,
        "quality_failures": quality_failures,
        "aggregates": aggregates,
    }
    (args.output / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"matrix completed={len(records)}/{len(plan)} "
        f"infra_failures={len(failures)} "
        f"quality_failures={len(quality_failures)} "
        f"output={args.output}",
        flush=True,
    )
    if failures:
        return 1
    return 2 if quality_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
