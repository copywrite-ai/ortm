#!/usr/bin/env python3
"""Run a randomized, repeated matrix of offline ORTM codec benchmarks."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import random
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")
TOOLS_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = TOOLS_DIR.parent
OFFLINE_RUNNER = TOOLS_DIR / "run_offline_benchmark.py"


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


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_matrix(path: Path) -> dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    if int(matrix.get("schema_version", 0)) != 1:
        raise ValueError("matrix.schema_version must be 1")
    allowed_matrix_keys = {
        "schema_version",
        "name",
        "description",
        "base_scenario",
        "seed",
        "repetitions",
        "warmup_runs",
        "variants",
    }
    unknown_matrix_keys = set(matrix) - allowed_matrix_keys
    if unknown_matrix_keys:
        raise ValueError(f"matrix has unknown keys: {sorted(unknown_matrix_keys)}")
    for key in ("name", "base_scenario", "variants"):
        if key not in matrix:
            raise ValueError(f"matrix is missing {key!r}")
    if not SAFE_NAME.fullmatch(str(matrix["name"])):
        raise ValueError("matrix.name is not a safe file name")
    repetitions = int(matrix.get("repetitions", 1))
    warmup_runs = int(matrix.get("warmup_runs", 0))
    if repetitions <= 0:
        raise ValueError("matrix.repetitions must be positive")
    if warmup_runs < 0:
        raise ValueError("matrix.warmup_runs must be non-negative")
    if not isinstance(matrix["variants"], list) or not matrix["variants"]:
        raise ValueError("matrix.variants must not be empty")
    names = []
    for variant in matrix["variants"]:
        unknown_variant_keys = set(variant) - {"name", "description", "video", "marker", "cases"}
        if unknown_variant_keys:
            raise ValueError(
                f"variant {variant.get('name', '')!r} has unknown keys: "
                f"{sorted(unknown_variant_keys)}"
            )
        name = str(variant.get("name", ""))
        if not SAFE_NAME.fullmatch(name):
            raise ValueError(f"variant name is not a safe file name: {name!r}")
        for section in ("video", "marker"):
            if section in variant and not isinstance(variant[section], dict):
                raise ValueError(f"variant {name}.{section} must be an object")
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError("matrix variant names must be unique")
    return matrix


def load_base_scenario(matrix_path: Path, matrix: dict[str, Any]) -> dict[str, Any]:
    path = (matrix_path.parent / str(matrix["base_scenario"])).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"base scenario does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_scenario(
    matrix: dict[str, Any],
    base: dict[str, Any],
    variant: dict[str, Any],
    repetition: int,
    *,
    warmup: bool = False,
) -> dict[str, Any]:
    override = {key: value for key, value in variant.items() if key not in ("name", "description")}
    scenario = deep_merge(base, override)
    suffix = f"warmup-{repetition:02d}" if warmup else f"r{repetition:02d}"
    scenario["name"] = f"{matrix['name']}-{variant['name']}-{suffix}"
    scenario["description"] = variant.get("description", matrix.get("description", ""))
    scenario["matrix"] = {
        "name": matrix["name"],
        "variant": variant["name"],
        "repetition": repetition,
        "warmup": warmup,
        "seed": int(matrix.get("seed", 0)),
    }
    return scenario


def execution_plan(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [
        {"variant": variant["name"], "repetition": repetition}
        for variant in matrix["variants"]
        for repetition in range(1, int(matrix.get("repetitions", 1)) + 1)
    ]
    random.Random(int(matrix.get("seed", 0))).shuffle(tasks)
    for order, task in enumerate(tasks, start=1):
        task["order"] = order
    return tasks


def runner_environment() -> dict[str, str]:
    environment = os.environ.copy()
    python_path = str(REPOSITORY_ROOT / "src/python")
    if environment.get("PYTHONPATH"):
        python_path = f"{python_path}{os.pathsep}{environment['PYTHONPATH']}"
    environment["PYTHONPATH"] = python_path
    return environment


def run_one(
    scenario: dict[str, Any],
    output: Path,
    *,
    ffmpeg: str,
    keep_bitstreams: bool,
) -> tuple[int, list[str]]:
    output.mkdir(parents=True, exist_ok=True)
    scenario_path = output / "scenario.json"
    scenario_path.write_text(json.dumps(scenario, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = [
        sys.executable,
        str(OFFLINE_RUNNER),
        "--scenario",
        str(scenario_path),
        "--output",
        str(output / "result"),
        "--ffmpeg",
        ffmpeg,
        "--overwrite",
    ]
    if keep_bitstreams:
        command.append("--keep-bitstreams")
    with (output / "runner.log").open("w", encoding="utf-8") as log_file:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=runner_environment(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    return completed.returncode, command


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def flatten_run_rows(
    variant: str,
    repetition: int,
    order: int,
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    video = summary["scenario"]["video"]
    marker = summary["scenario"]["marker"]
    rows = []
    for case in summary["cases"]:
        rows.append({
            "variant": variant,
            "repetition": repetition,
            "execution_order": order,
            "case": case["name"],
            "background": case["background"],
            "width": video["width"],
            "height": video["height"],
            "fps": video["fps"],
            "frames": video["frames"],
            "target_bitrate_kbps": video["bitrate_kbps"],
            "actual_bitrate_kbps": case["actual_bitrate_kbps"],
            "key_int": video["key_int"],
            "background_alpha": marker["background_alpha"],
            "cell_alpha": marker["cell_alpha"],
            "finder_layout": marker.get("finder_layout", "four"),
            "expected_frames": case["expected_frames"],
            "successful_frames": case["successful_frames"],
            "success_percent": case["success_percent"],
            "decode_median_ms": case["decode_ms"]["median"],
            "decode_p95_ms": case["decode_ms"]["p95"],
            "decode_p99_ms": case["decode_ms"]["p99"],
            "contrast_median": case["contrast"]["median"],
            "finder_errors_max": case["finder_errors"]["max"],
            "timing_errors_max": case["timing_errors"]["max"],
            "failures": json.dumps(case["failures"], sort_keys=True),
        })
    return rows


def aggregate_runs(run_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {"samples": [], "cases": []}
    )
    for record in run_records:
        for case in record["summary"]["cases"]:
            key = (record["variant"], case["name"], case["background"])
            groups[key]["cases"].append(case)
        for sample in record["samples"]:
            key = (record["variant"], sample["case"], sample["background"])
            groups[key]["samples"].append(sample)

    aggregates = []
    for (variant, case_name, background), group in sorted(groups.items()):
        cases = group["cases"]
        samples = group["samples"]
        expected = sum(int(case["expected_frames"]) for case in cases)
        successful = sum(int(case["successful_frames"]) for case in cases)
        valid = [sample for sample in samples if sample["ok"] and sample["identity_match"]]
        aggregates.append({
            "variant": variant,
            "case": case_name,
            "background": background,
            "repetitions": len(cases),
            "expected_frames": expected,
            "successful_frames": successful,
            "success_percent": 100 * successful / expected if expected else None,
            "actual_bitrate_kbps": distribution(case["actual_bitrate_kbps"] for case in cases),
            "decode_ms": distribution(sample["decode_ms"] for sample in samples),
            "contrast": distribution(sample["contrast"] for sample in valid),
            "finder_errors": distribution(sample["finder_errors"] for sample in valid),
            "timing_errors": distribution(sample["timing_errors"] for sample in valid),
        })
    return aggregates


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_aggregate_csv(path: Path, aggregates: list[dict[str, Any]]) -> None:
    rows = []
    for item in aggregates:
        rows.append({
            "variant": item["variant"],
            "case": item["case"],
            "background": item["background"],
            "repetitions": item["repetitions"],
            "expected_frames": item["expected_frames"],
            "successful_frames": item["successful_frames"],
            "success_percent": item["success_percent"],
            "bitrate_median_kbps": item["actual_bitrate_kbps"]["median"],
            "bitrate_p95_kbps": item["actual_bitrate_kbps"]["p95"],
            "decode_median_ms": item["decode_ms"]["median"],
            "decode_p95_ms": item["decode_ms"]["p95"],
            "decode_p99_ms": item["decode_ms"]["p99"],
            "contrast_median": item["contrast"]["median"],
            "finder_errors_max": item["finder_errors"]["max"],
            "timing_errors_max": item["timing_errors"]["max"],
        })
    write_csv(path, rows)


def prepare_output(path: Path, overwrite: bool, resume: bool) -> None:
    resolved = path.resolve()
    if resolved in (Path.cwd().resolve(), Path(resolved.anchor)):
        raise ValueError(f"refusing unsafe output directory: {resolved}")
    if path.exists():
        if overwrite:
            shutil.rmtree(path)
        elif not resume:
            raise FileExistsError(
                f"output already exists: {path}; use --overwrite or --resume"
            )
    path.mkdir(parents=True, exist_ok=True)


def write_or_validate_input_manifest(
    output: Path,
    matrix: dict[str, Any],
    base: dict[str, Any],
    *,
    resume: bool,
) -> None:
    path = output / "input.json"
    manifest = {"matrix": matrix, "base_scenario": base}
    if resume and path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise ValueError(
                "cannot resume: matrix or base scenario differs from output/input.json"
            )
        return
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--keep-bitstreams", action="store_true")
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument("--overwrite", action="store_true")
    output_mode.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not shutil.which(args.ffmpeg):
        parser.error(f"FFmpeg executable not found: {args.ffmpeg}")
    matrix = load_matrix(args.matrix)
    base = load_base_scenario(args.matrix, matrix)
    prepare_output(args.output, args.overwrite, args.resume)
    write_or_validate_input_manifest(
        args.output, matrix, base, resume=args.resume
    )
    variants = {variant["name"]: variant for variant in matrix["variants"]}

    for variant in matrix["variants"]:
        for repetition in range(1, int(matrix.get("warmup_runs", 0)) + 1):
            scenario = build_scenario(matrix, base, variant, repetition, warmup=True)
            output = args.output / "warmup" / variant["name"] / f"r{repetition:02d}"
            if args.resume and (output / "result" / "summary.json").exists():
                print(
                    f"[warmup reuse] variant={variant['name']} repetition={repetition}",
                    flush=True,
                )
                continue
            print(f"[warmup] variant={variant['name']} repetition={repetition}", flush=True)
            return_code, _ = run_one(
                scenario, output, ffmpeg=args.ffmpeg, keep_bitstreams=False
            )
            if return_code not in (0, 2):
                raise RuntimeError(f"warmup failed for {variant['name']}; see {output / 'runner.log'}")

    run_records = []
    run_rows = []
    infrastructure_failures = []
    plan = execution_plan(matrix)
    for task in plan:
        variant = variants[task["variant"]]
        scenario = build_scenario(matrix, base, variant, task["repetition"])
        output = args.output / "runs" / f"{task['order']:03d}-{task['variant']}-r{task['repetition']:02d}"
        summary_path = output / "result" / "summary.json"
        samples_path = output / "result" / "samples.jsonl"
        reused = args.resume and summary_path.exists() and samples_path.exists()
        if reused:
            print(
                f"[{task['order']:03d}/{len(plan):03d}] reuse variant={task['variant']} "
                f"repetition={task['repetition']}",
                flush=True,
            )
            return_code = 0
            command: list[str] = []
        else:
            print(
                f"[{task['order']:03d}/{len(plan):03d}] variant={task['variant']} "
                f"repetition={task['repetition']}",
                flush=True,
            )
            return_code, command = run_one(
                scenario,
                output,
                ffmpeg=args.ffmpeg,
                keep_bitstreams=args.keep_bitstreams,
            )
        if return_code not in (0, 2) or not summary_path.exists() or not samples_path.exists():
            infrastructure_failures.append({
                **task,
                "return_code": return_code,
                "output": str(output),
            })
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        samples = read_jsonl(samples_path)
        record = {
            **task,
            "return_code": return_code,
            "output": str(output),
            "command": command,
            "reused": reused,
            "summary": summary,
            "samples": samples,
        }
        run_records.append(record)
        run_rows.extend(flatten_run_rows(
            task["variant"], task["repetition"], task["order"], summary
        ))

    aggregates = aggregate_runs(run_records)
    write_csv(args.output / "runs.csv", run_rows)
    write_aggregate_csv(args.output / "aggregate.csv", aggregates)
    with (args.output / "runs.jsonl").open("w", encoding="utf-8") as output_file:
        for record in run_records:
            compact = {key: value for key, value in record.items() if key != "samples"}
            output_file.write(json.dumps(compact, sort_keys=True) + "\n")

    expected = sum(item["expected_frames"] for item in aggregates)
    successful = sum(item["successful_frames"] for item in aggregates)
    result = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "matrix": matrix,
        "execution_plan": plan,
        "completed_runs": len(run_records),
        "infrastructure_failures": infrastructure_failures,
        "aggregates": aggregates,
        "overall": {
            "expected_frames": expected,
            "successful_frames": successful,
            "success_percent": 100 * successful / expected if expected else None,
        },
    }
    (args.output / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"matrix completed={len(run_records)}/{len(plan)} "
        f"success={result['overall']['success_percent']} output={args.output}",
        flush=True,
    )
    if infrastructure_failures:
        return 1
    return 0 if successful == expected else 2


if __name__ == "__main__":
    raise SystemExit(main())
