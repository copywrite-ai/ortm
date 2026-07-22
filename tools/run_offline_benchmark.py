#!/usr/bin/env python3
"""Run deterministic ORTM frames through an offline FFmpeg H.264 round trip."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from ortm.codec import ENCODED_CELLS, GRID_SIZE, UINT32_MASK, encode_grid
from ortm.raster import DecodeError, RasterProfile, decode_luma_frame


def load_scenario(path: Path) -> dict[str, Any]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    for key in ("name", "video", "marker", "cases"):
        if key not in scenario:
            raise ValueError(f"scenario is missing {key!r}")
    video = scenario["video"]
    marker = scenario["marker"]
    for key in ("width", "height", "fps", "frames", "bitrate_kbps", "key_int"):
        if int(video.get(key, 0)) <= 0:
            raise ValueError(f"video.{key} must be positive")
    if int(marker.get("cell", 0)) <= 0:
        raise ValueError("marker.cell must be positive")
    if int(marker.get("padding", -1)) < 0:
        raise ValueError("marker.padding must be non-negative")
    for key in ("background_alpha", "cell_alpha"):
        value = float(marker.get(key, -1))
        if not 0 <= value <= 1:
            raise ValueError(f"marker.{key} must be between 0 and 1")
    if not scenario["cases"]:
        raise ValueError("scenario.cases must not be empty")
    case_names = []
    for case in scenario["cases"]:
        name = str(case.get("name", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name):
            raise ValueError(f"case name is not a safe file name: {name!r}")
        if case.get("background") not in ("flat", "stripes", "moving-checker"):
            raise ValueError(f"unsupported background {case.get('background')!r}")
        case_names.append(name)
    if len(case_names) != len(set(case_names)):
        raise ValueError("scenario case names must be unique")
    return scenario


def blend_table(target: int, alpha: float) -> bytes:
    return bytes(round(target * alpha + source * (1 - alpha)) for source in range(256))


class FrameRenderer:
    def __init__(self, scenario: dict[str, Any]) -> None:
        video = scenario["video"]
        marker = scenario["marker"]
        self.width = int(video["width"])
        self.height = int(video["height"])
        self.fps = int(video["fps"])
        self.x = int(marker.get("x", 24))
        self.y = int(marker.get("y", 24))
        self.cell = int(marker.get("cell", 12))
        self.padding = int(marker.get("padding", 12))
        self.box_size = GRID_SIZE * self.cell + self.padding * 2
        if self.x < 0 or self.y < 0 or self.x + self.box_size > self.width or self.y + self.box_size > self.height:
            raise ValueError("marker does not fit inside configured video frame")
        self.background_table = blend_table(255, float(marker.get("background_alpha", 0.15)))
        cell_alpha = float(marker.get("cell_alpha", 0.65))
        self.black_table = blend_table(0, cell_alpha)
        self.white_table = blend_table(255, cell_alpha)

    def background_frame(self, name: str, frame_index: int) -> bytearray:
        if name == "flat":
            return bytearray([127]) * (self.width * self.height)

        frame = bytearray(self.width * self.height)
        if name == "stripes":
            row = bytes(25 if (x // 12) % 2 == 0 else 230 for x in range(self.width))
            for y in range(self.height):
                start = y * self.width
                frame[start : start + self.width] = row
            return frame

        if name == "moving-checker":
            shift_x = (frame_index * 3) % 32
            shift_y = (frame_index * 2) % 32
            rows = [
                bytes(
                    35 if (((x + shift_x) // 16) + ((y + shift_y) // 16)) % 2 == 0 else 220
                    for x in range(self.width)
                )
                for y in range(self.height)
            ]
            return bytearray(b"".join(rows))

        raise ValueError(f"unsupported background {name!r}")

    def render(self, background: str, frame_index: int, frame_seq: int, timestamp_ms: int) -> bytes:
        frame = self.background_frame(background, frame_index)
        for row in range(self.y, self.y + self.box_size):
            start = row * self.width + self.x
            end = start + self.box_size
            frame[start:end] = bytes(frame[start:end]).translate(self.background_table)

        grid = encode_grid(frame_seq, timestamp_ms)
        origin_x = self.x + self.padding
        origin_y = self.y + self.padding
        for row, col in ENCODED_CELLS:
            table = self.black_table if grid[row][col] else self.white_table
            left = origin_x + col * self.cell
            top = origin_y + row * self.cell
            for y in range(top, top + self.cell):
                start = y * self.width + left
                end = start + self.cell
                frame[start:end] = bytes(frame[start:end]).translate(table)

        for y in range(self.y, self.y + self.box_size):
            row_start = y * self.width
            if y < self.y + 2 or y >= self.y + self.box_size - 2:
                frame[row_start + self.x : row_start + self.x + self.box_size] = b"\0" * self.box_size
            else:
                frame[row_start + self.x : row_start + self.x + 2] = b"\0\0"
                right = row_start + self.x + self.box_size - 2
                frame[right : right + 2] = b"\0\0"
        return bytes(frame)


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
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


def frame_rows(frame: bytes, width: int, height: int) -> list[memoryview]:
    view = memoryview(frame)
    return [view[y * width : (y + 1) * width] for y in range(height)]


def ffmpeg_version(ffmpeg: str) -> str:
    completed = subprocess.run(
        [ffmpeg, "-version"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout.splitlines()[0]


def encoder_command(ffmpeg: str, video: dict[str, Any], output: Path) -> list[str]:
    width = int(video["width"])
    height = int(video["height"])
    fps = int(video["fps"])
    bitrate = int(video["bitrate_kbps"])
    key_int = int(video["key_int"])
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-frames:v",
        str(int(video["frames"])),
        "-c:v",
        "libx264",
        "-preset",
        str(video.get("preset", "ultrafast")),
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        f"{bitrate}k",
        "-maxrate",
        f"{bitrate}k",
        "-bufsize",
        f"{bitrate * 2}k",
        "-g",
        str(key_int),
        "-keyint_min",
        str(key_int),
        "-sc_threshold",
        "0",
        "-bf",
        "0",
        "-f",
        "h264",
        str(output),
    ]


def decoder_command(ffmpeg: str, frames: int, source: Path) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        str(source),
        "-an",
        "-frames:v",
        str(frames),
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "pipe:1",
    ]


def encode_case(
    ffmpeg: str,
    scenario: dict[str, Any],
    case: dict[str, Any],
    output: Path,
    renderer: FrameRenderer,
) -> tuple[list[str], float]:
    command = encoder_command(ffmpeg, scenario["video"], output)
    marker = scenario["marker"]
    frames = int(scenario["video"]["frames"])
    seq_start = int(marker.get("frame_seq_start", 0))
    timestamp_start = int(marker.get("timestamp_start_ms", 0))
    started = time.monotonic()
    log_path = output.with_suffix(".encoder.log")
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log_file)
        assert process.stdin is not None
        try:
            for index in range(frames):
                frame_seq = (seq_start + index) & 0xFFFF
                timestamp_ms = (timestamp_start + round(index * 1000 / renderer.fps)) & UINT32_MASK
                process.stdin.write(
                    renderer.render(case["background"], index, frame_seq, timestamp_ms)
                )
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"FFmpeg encoder failed for {case['name']}; see {log_path}")
    return command, time.monotonic() - started


def decode_case(
    ffmpeg: str,
    run_id: str,
    scenario: dict[str, Any],
    case: dict[str, Any],
    bitstream: Path,
) -> tuple[list[dict[str, Any]], list[str], float]:
    video = scenario["video"]
    marker_config = scenario["marker"]
    width = int(video["width"])
    height = int(video["height"])
    frames = int(video["frames"])
    frame_size = width * height
    seq_start = int(marker_config.get("frame_seq_start", 0))
    timestamp_start = int(marker_config.get("timestamp_start_ms", 0))
    nominal = RasterProfile(
        x=float(marker_config.get("x", 24)),
        y=float(marker_config.get("y", 24)),
        cell=float(marker_config.get("cell", 12)),
        padding=float(marker_config.get("padding", 12)),
    )
    command = decoder_command(ffmpeg, frames, bitstream)
    samples: list[dict[str, Any]] = []
    started = time.monotonic()
    log_path = bitstream.with_suffix(".decoder.log")
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log_file)
        assert process.stdout is not None
        output_index = 0
        while output_index < frames:
            frame = process.stdout.read(frame_size)
            if not frame:
                break
            if len(frame) != frame_size:
                raise RuntimeError(f"decoder returned a partial frame for {case['name']}")
            expected_seq = (seq_start + output_index) & 0xFFFF
            expected_timestamp = (
                timestamp_start + round(output_index * 1000 / int(video["fps"]))
            ) & UINT32_MASK
            decode_started = time.monotonic_ns()
            try:
                result = decode_luma_frame(frame_rows(frame, width, height), nominal=nominal)
                decode_ms = (time.monotonic_ns() - decode_started) / 1_000_000
                sample = {
                    "run_id": run_id,
                    "scenario": scenario["name"],
                    "case": case["name"],
                    "background": case["background"],
                    "output_frame_index": output_index,
                    "expected_frame_seq": expected_seq,
                    "expected_timestamp_ms": expected_timestamp,
                    "ok": True,
                    "reason": None,
                    "frame_seq": result.marker.frame_seq,
                    "timestamp_ms": result.marker.timestamp_ms,
                    "identity_match": result.marker.frame_seq == expected_seq
                    and result.marker.timestamp_ms == expected_timestamp,
                    "finder_errors": result.marker.finder_errors,
                    "timing_errors": result.marker.timing_errors,
                    "contrast": result.contrast,
                    "threshold": result.threshold,
                    "decode_ms": decode_ms,
                    "candidate": {
                        "x": result.profile.x,
                        "y": result.profile.y,
                        "cell": result.profile.cell,
                        "padding": result.profile.padding,
                    },
                }
            except DecodeError as error:
                decode_ms = (time.monotonic_ns() - decode_started) / 1_000_000
                sample = {
                    "run_id": run_id,
                    "scenario": scenario["name"],
                    "case": case["name"],
                    "background": case["background"],
                    "output_frame_index": output_index,
                    "expected_frame_seq": expected_seq,
                    "expected_timestamp_ms": expected_timestamp,
                    "ok": False,
                    "reason": error.reason,
                    "frame_seq": None,
                    "timestamp_ms": None,
                    "identity_match": False,
                    "finder_errors": error.details.get("finder_errors"),
                    "timing_errors": error.details.get("timing_errors"),
                    "contrast": error.details.get("contrast"),
                    "threshold": None,
                    "decode_ms": decode_ms,
                }
            samples.append(sample)
            output_index += 1
        process.stdout.close()
        return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"FFmpeg decoder failed for {case['name']}; see {log_path}")
    return samples, command, time.monotonic() - started


def summarize_case(
    scenario: dict[str, Any],
    case: dict[str, Any],
    samples: list[dict[str, Any]],
    bitstream: Path,
    encode_seconds: float,
    decode_seconds: float,
) -> dict[str, Any]:
    expected_frames = int(scenario["video"]["frames"])
    duration_seconds = expected_frames / int(scenario["video"]["fps"])
    encoded_bytes = bitstream.stat().st_size
    successes = [sample for sample in samples if sample["ok"] and sample["identity_match"]]
    failures = Counter(
        "identity-mismatch" if sample["ok"] else sample["reason"]
        for sample in samples
        if not (sample["ok"] and sample["identity_match"])
    )
    missing_frames = max(expected_frames - len(samples), 0)
    if missing_frames:
        failures["missing-output-frame"] += missing_frames
    digest = hashlib.sha256()
    with bitstream.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "name": case["name"],
        "background": case["background"],
        "expected_frames": expected_frames,
        "decoded_frames": len(samples),
        "successful_frames": len(successes),
        "success_percent": 100 * len(successes) / expected_frames,
        "failures": dict(sorted(failures.items())),
        "encoded_bytes": encoded_bytes,
        "encoded_sha256": digest.hexdigest(),
        "actual_bitrate_kbps": encoded_bytes * 8 / duration_seconds / 1000,
        "encode_wall_seconds": encode_seconds,
        "decode_wall_seconds": decode_seconds,
        "decode_ms": distribution(sample["decode_ms"] for sample in samples),
        "contrast": distribution(
            sample["contrast"] for sample in successes if sample["contrast"] is not None
        ),
        "finder_errors": distribution(
            sample["finder_errors"] for sample in successes if sample["finder_errors"] is not None
        ),
        "timing_errors": distribution(
            sample["timing_errors"] for sample in successes if sample["timing_errors"] is not None
        ),
    }


def prepare_output(path: Path, overwrite: bool) -> None:
    resolved = path.resolve()
    if resolved in (Path.cwd().resolve(), Path(resolved.anchor)):
        raise ValueError(f"refusing unsafe output directory: {resolved}")
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"output already exists: {path}; use --overwrite")
        shutil.rmtree(path)
    path.mkdir(parents=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--keep-bitstreams", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    ffmpeg = shutil.which(args.ffmpeg)
    if not ffmpeg:
        parser.error(f"FFmpeg executable not found: {args.ffmpeg}")
    scenario = load_scenario(args.scenario)
    prepare_output(args.output, args.overwrite)
    renderer = FrameRenderer(scenario)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    all_samples: list[dict[str, Any]] = []
    case_summaries = []
    commands = []

    for case in scenario["cases"]:
        print(f"[{case['name']}] encode", flush=True)
        bitstream = args.output / f"{case['name']}.h264"
        encode_cmd, encode_seconds = encode_case(ffmpeg, scenario, case, bitstream, renderer)
        print(f"[{case['name']}] decode", flush=True)
        samples, decode_cmd, decode_seconds = decode_case(
            ffmpeg, run_id, scenario, case, bitstream
        )
        summary = summarize_case(
            scenario, case, samples, bitstream, encode_seconds, decode_seconds
        )
        print(
            f"[{case['name']}] success={summary['success_percent']:.2f}% "
            f"bitrate={summary['actual_bitrate_kbps']:.1f}kbps",
            flush=True,
        )
        all_samples.extend(samples)
        case_summaries.append(summary)
        commands.append({"case": case["name"], "encoder": encode_cmd, "decoder": decode_cmd})
        if not args.keep_bitstreams:
            bitstream.unlink()

    samples_path = args.output / "samples.jsonl"
    with samples_path.open("w", encoding="utf-8") as output_file:
        for sample in all_samples:
            output_file.write(json.dumps(sample, sort_keys=True) + "\n")

    expected_total = sum(case["expected_frames"] for case in case_summaries)
    success_total = sum(case["successful_frames"] for case in case_summaries)
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "scenario": scenario,
        "toolchain": {"ffmpeg": ffmpeg_version(ffmpeg), "python": sys.version.split()[0]},
        "commands": commands,
        "cases": case_summaries,
        "overall": {
            "expected_frames": expected_total,
            "successful_frames": success_total,
            "success_percent": 100 * success_total / expected_total,
        },
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"overall success={summary['overall']['success_percent']:.2f}% "
        f"output={args.output}",
        flush=True,
    )
    return 0 if success_total == expected_total else 2


if __name__ == "__main__":
    raise SystemExit(main())
