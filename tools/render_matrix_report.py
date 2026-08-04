#!/usr/bin/env python3
"""Render a concise Markdown report from an offline matrix summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def number(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def describe_variant(variant: dict[str, Any]) -> str:
    if variant.get("description"):
        return str(variant["description"])
    overrides = {
        key: variant[key]
        for key in ("video", "marker", "cases")
        if key in variant
    }
    return f"Overrides `{json.dumps(overrides, sort_keys=True, separators=(',', ':'))}`."


def interpretation(summary: dict[str, Any]) -> list[str]:
    matrix = summary["matrix"]
    aggregates = summary["aggregates"]
    overall = summary["overall"]
    variant_names = {variant["name"] for variant in matrix["variants"]}
    codec_names = {
        variant.get("video", {}).get("codec")
        for variant in matrix["variants"]
        if variant.get("video", {}).get("codec")
    }
    decode_p95 = [
        item["decode_ms"]["p95"]
        for item in aggregates
        if item["decode_ms"]["p95"] is not None
    ]

    if overall["successful_frames"] == overall["expected_frames"]:
        lines = [
            "- Every declared condition decoded successfully; no finder, timing,",
            "  CRC, or frame-identity failures were observed in measured frames.",
        ]
    else:
        lines = [
            f"- Overall frame recovery was {number(overall['success_percent'])}%;",
            "  failures are part of the measured robustness boundary.",
        ]
    if decode_p95:
        lines.extend([
            f"- ORTM decode p95 ranged from {number(min(decode_p95), 3)} ms to",
            f"  {number(max(decode_p95), 3)} ms across aggregate conditions.",
        ])
    lines.extend([
        "- Actual bitrate depends strongly on source content. Target bitrate must not",
        "  be reported as measured encoded bitrate.",
    ])
    if len(codec_names) > 1:
        lines.extend([
            "- Codec profiles produced different actual rate-control behavior while",
            "  preserving ORTM in this matrix. This is a survivability result, not a",
            "  claim of equivalent visual quality or encoder efficiency.",
        ])
    if "render-opaque" in variant_names:
        lines.extend([
            "- The opaque marker raises contrast but also changes encoder workload by",
            "  replacing a large image area with stable content. It is not a free quality",
            "  improvement and obscures more of the video.",
            "- The current low-impact rendering profile remains the practical default;",
            "  the alpha variants establish robustness headroom rather than a latency win.",
        ])
    if matrix.get("name") == "finder-layout-formal":
        lines.extend([
            "- Omitting the bottom-right finder reduced encoded cells from 195 to",
            "  179 (8.2%); retaining only the two top finders reduced them to 163",
            "  (16.4%). No recovery failure was observed in this matrix.",
            "- Decode p95 and actual bitrate remained effectively unchanged; the",
            "  expected benefit is lower visual salience, not throughput or latency.",
            "- The sparse finder images require an explicitly layout-aware decoder and",
            "  must not be presented as backward-compatible ORTM v0 imagery.",
            "- The two-top finders are collinear. This layout is intended only for fixed",
            "  ROI use and sacrifices geometric evidence needed for robust rotation,",
            "  perspective, and full-image detection.",
        ])
    return lines


def limitations(summary: dict[str, Any]) -> list[str]:
    matrix = summary["matrix"]
    if matrix.get("name") == "finder-layout-formal":
        return [
            "- This run does not validate clock synchronization or optical accuracy.",
            "- It uses fixed 720p geometry and a fixed-ROI decoder; it does not measure",
            "  full-image detection, false positives, rotation, scale, or perspective.",
            "- It does not cover camera content, packet loss, jitter, WebRTC buffering,",
            "  browser presentation, or TURN relay behavior.",
            "- The next step is a live camera/WebRTC comparison, followed by controlled",
            "  translation, scale, rotation, and perspective stress tests.",
        ]
    resolutions = {
        (variant.get("video", {}).get("width"), variant.get("video", {}).get("height"))
        for variant in matrix["variants"]
        if variant.get("video", {}).get("width") and variant.get("video", {}).get("height")
    }
    marker_geometries = {
        tuple(variant.get("marker", {}).get(key) for key in ("x", "y", "cell", "padding"))
        for variant in matrix["variants"]
        if variant.get("marker")
    }
    lines = [
        "- This run does not validate clock synchronization or optical accuracy.",
        "- It does not cover packet loss, jitter, bandwidth transitions, WebRTC",
        "  buffering, browser presentation, or TURN relay behavior.",
    ]
    if len(resolutions) > 1:
        if len(marker_geometries) > 1:
            lines.extend([
                "- This matrix scales marker position, cell, and padding together. It",
                "  validates the combined resolution-normalized profile but does not",
                "  isolate the contribution of each geometry parameter.",
            ])
        else:
            lines.extend([
                "- This matrix keeps marker pixels fixed across resolutions. It does not",
                "  test a resolution-normalized marker whose position, cell, and padding",
                "  scale with the video dimensions.",
            ])
    else:
        lines.extend([
            "- Resolution requires a separate declared matrix because the current",
            "  408-pixel outer marker cannot fit in a 360p frame; changing resolution",
            "  and marker geometry together would confound the two effects.",
        ])
    if len(resolutions) > 1 and len(marker_geometries) > 1:
        lines.extend([
            "- The next rigorous stages are controlled network impairment and",
            "  comparison with an optical reference.",
        ])
    else:
        lines.extend([
            "- The next rigorous stages are resolution-normalized geometry, controlled",
            "  network impairment, and comparison with an optical reference.",
        ])
    return lines


def render_report(summary: dict[str, Any], artifact_path: str) -> str:
    matrix = summary["matrix"]
    overall = summary["overall"]
    aggregates = summary["aggregates"]
    variants = {variant["name"]: variant for variant in matrix["variants"]}

    lines = [
        f"# {matrix['name']} Results",
        "",
        "## Scope",
        "",
        "This offline experiment measures ORTM v0 survivability and ORTM decoder cost",
        "after a real FFmpeg encode/decode cycle. It does not use a network,",
        "a WebRTC receiver, or a display, so these results are not G2G latency",
        "measurements.",
        "",
        "## Method",
        "",
        f"- Seed: `{matrix.get('seed', 0)}`",
        f"- Measured repetitions per variant: {matrix.get('repetitions', 1)}",
        f"- Warm-up runs per variant: {matrix.get('warmup_runs', 0)}",
        f"- Completed measured runs: {summary['completed_runs']}",
        f"- Decoded frames: {overall['successful_frames']} / {overall['expected_frames']} "
        f"({number(overall['success_percent'])}%)",
        f"- Raw artifact directory: `{artifact_path}`",
        "",
        "Condition order was deterministically randomized. Aggregates combine all",
        "frame-level samples from separate execution repetitions. Source frames are",
        "deterministic, so repeated failures at the same frame are reproducible",
        "content-dependent events, not independent random samples.",
        "",
        "## Results",
        "",
        "| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in aggregates:
        lines.append(
            f"| {item['variant']} | {item['background']} | "
            f"{number(item['success_percent'])}% | "
            f"{number(item['actual_bitrate_kbps']['median'])} kbps | "
            f"{number(item['decode_ms']['p95'], 3)} ms | "
            f"{number(item['decode_ms']['max'], 3)} ms | "
            f"{number(item['contrast']['median'], 2)} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        *interpretation(summary),
        "",
        "## Declared Variants",
        "",
    ])
    for name, variant in variants.items():
        lines.append(f"- `{name}`: {describe_variant(variant)}")

    lines.extend([
        "",
        "## Limitations And Next Experiments",
        "",
        *limitations(summary),
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-path")
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    artifact_path = args.artifact_path or str(args.summary.parent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(summary, artifact_path), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
