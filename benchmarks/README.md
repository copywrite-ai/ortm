# Offline codec benchmark

The offline benchmark renders deterministic ORTM frames, sends them through a
real FFmpeg/libx264 encode/decode cycle, and decodes ORTM from the resulting
pixels. It does not open a network connection and does not measure G2G latency.

Background cases include flat content, static stripes, a moving checkerboard,
and deterministic per-frame `snow`. The snow case is a codec pressure test; it
is intentionally more complex than representative camera content.

Run the sparse 720p dynamic-background scenario with:

```bash
make benchmark-minimal-720p
```

The experimental finder-layout branch compares the standard four-corner layout
against a three-finder layout and a two-top layout. All variants preserve all
corner reservations and the complete v0 payload map:

```bash
make benchmark-finder-layout-formal
make benchmark-finder-layout-report
```

The sparse-finder markers require a layout-aware decoder and are not wire-image
compatible with an ORTM v0 decoder expecting all four finders. The two-top
variant is restricted to fixed-ROI use because its finders are collinear.

The committed baseline is a two-second smoke suite per background. It verifies
the harness and catches gross regressions; it is not long enough for a
publication-quality statistical claim. Formal runs must use the repetition and
observation policy in `docs/benchmark-plan.md`.

## Repeated matrices

Use the matrix runner to execute declared variants in a deterministic randomized
order and aggregate independent repetitions:

```bash
make benchmark-matrix-smoke
```

The smoke matrix runs three small variants twice. It validates orchestration and
aggregation, but it is not evidence about codec robustness.

The first formal H.264 matrix varies FPS, bitrate, key-frame interval, and
rendering alpha around the validated `960x540 / 60 fps / 2500 kbps` profile. It
uses one warm-up run and five measured repetitions per variant:

```bash
PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
  --matrix benchmarks/matrices/h264-core-formal.json \
  --output benchmark-results/h264-core-formal \
  --overwrite
```

Resume the same matrix after an interruption:

```bash
PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
  --matrix benchmarks/matrices/h264-core-formal.json \
  --output benchmark-results/h264-core-formal \
  --resume
```

`--resume` reuses complete runs and regenerates aggregate files. It refuses to
continue if the matrix or base scenario differs from the committed
`output/input.json` manifest.

Matrix execution produces:

- `summary.json`: matrix definition, randomized execution plan, failures, and
  frame-level aggregate distributions;
- `runs.jsonl`: one record per independent run;
- `runs.csv`: one row per run and background case;
- `aggregate.csv`: one row per variant and background across all repetitions;
- `runs/*`: generated scenarios, raw samples, FFmpeg diagnostics, and commands.
- `input.json`: immutable matrix and base-scenario manifest used for resume
  validation.

Render a reviewable Markdown report from a completed formal run:

```bash
make benchmark-matrix-report
```

The generated report records the method, aggregate table, interpretation, and
limitations. Raw result directories remain ignored because they are large;
commit the concise report when a result set is intentionally curated.

Curated result reports:

- [H.264 core formal matrix, 2026-07-22](../docs/results/h264-core-formal-2026-07-22.md)
- [Codec core formal matrix, 2026-07-23](../docs/results/codec-core-formal-2026-07-23.md)
- [Cell geometry formal matrix, 2026-07-23](../docs/results/geometry-cell-formal-2026-07-23.md)
- [Fixed-cell resolution formal matrix, 2026-07-23](../docs/results/resolution-fixed-cell6-formal-2026-07-23.md)
- [Resolution-normalized formal matrix, 2026-07-23](../docs/results/resolution-normalized-formal-2026-07-23.md)
- [Direct network impairment path validation, 2026-07-23](../docs/results/network-path-validation-2026-07-23.md)

The matrix schema is `benchmarks/schema/offline-matrix.schema.json`. A matrix
variant recursively overrides `video`, `marker`, or `cases` from its declared
base scenario.

## Codec matrix

The codec runner supports fixed, reproducible FFmpeg profiles for H.264, VP8,
VP9, and AV1. Verify local encoder availability and orchestration first:

```bash
make benchmark-codec-smoke
```

Then run the ten-second, five-repetition formal comparison:

```bash
PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
  --matrix benchmarks/matrices/codec-core-formal.json \
  --output benchmark-results/codec-core-formal \
  --overwrite
```

The formal matrix keeps resolution, FPS, target bitrate, key-frame interval,
marker geometry, rendering alpha, backgrounds, and observation duration fixed.
Only the codec profile changes. This isolates codec survivability but does not
claim equivalent visual quality or rate-control behavior between encoders.
SVT-AV1 uses `pred-struct=1` to select its low-delay prediction structure. The
tested encoder accepts target CBR in this mode but disables TPL and warns that
the configured maximum bitrate is not enforced as a strict peak bound. Report
measured bitrate rather than assuming identical rate-control behavior.

## Marker geometry boundary

Search for the first failing cell size while holding the 540p60 H.264 video
profile and all rendering parameters except `marker.cell` fixed:

```bash
make benchmark-geometry-exploratory
```

This short, single-repetition matrix is only a boundary finder. Use its
first passing and failing sizes to declare a smaller ten-second, five-repetition
formal matrix; do not present exploratory percentages as a reliability claim.

The committed formal follow-up tests the discovered boundary at cells 3 and 4,
plus cells 6 and 12 as references:

```bash
PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
  --matrix benchmarks/matrices/geometry-cell-formal.json \
  --output benchmark-results/geometry-cell-formal \
  --overwrite
```

## Resolution with fixed marker pixels

After establishing cell 6 as a margin-bearing geometry, vary only video
resolution while keeping the marker at the same pixel size:

```bash
make benchmark-resolution-exploratory
```

This distinguishes resolution/compression effects from marker scaling. A later
resolution-normalized experiment will scale marker position, cell, and padding
together and must be reported separately.

Run that paired resolution-normalized exploration with:

```bash
make benchmark-resolution-normalized-exploratory
```

It anchors at 540p/cell 6 and scales geometry proportionally to cell 4 at 360p,
cell 8 at 720p, and cell 12 at 1080p.

The formal paired follow-up is:

```bash
PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
  --matrix benchmarks/matrices/resolution-normalized-formal.json \
  --output benchmark-results/resolution-normalized-formal \
  --overwrite
```

The formal fixed-pixel follow-up uses ten seconds and five repetitions for all
four resolutions:

```bash
PYTHONPATH=src/python python3 tools/run_offline_matrix.py \
  --matrix benchmarks/matrices/resolution-fixed-cell6-formal.json \
  --output benchmark-results/resolution-fixed-cell6-formal \
  --overwrite
```

Resolution is intentionally excluded from the first formal matrix. The current
408-pixel outer marker cannot fit in a 360p frame; changing both resolution and
marker geometry in one factor would confound image-resolution effects with
marker-scale effects. Resolution and marker geometry require a separately
declared experiment.

Run the reference suite:

```bash
make benchmark-smoke
```

Or choose an output directory:

```bash
PYTHONPATH=src/python python3 tools/run_offline_benchmark.py \
  --scenario benchmarks/scenarios/h264-540p60-2500k.json \
  --output benchmark-results/h264-baseline \
  --overwrite
```

Keep encoded H.264 artifacts when visual inspection is needed:

```bash
PYTHONPATH=src/python python3 tools/run_offline_benchmark.py \
  --scenario benchmarks/scenarios/h264-540p60-2500k.json \
  --output benchmark-results/h264-baseline \
  --overwrite \
  --keep-bitstreams
```

Each run produces:

- `samples.jsonl`: one record for every decoded frame;
- `summary.json`: scenario, toolchain, encoded size/bitrate, decode success and
  latency-independent quality statistics;
- `ffmpeg-*.log`: encoder and decoder diagnostics;
- optional `*.h264` elementary streams.

The per-frame schema is documented in
`benchmarks/schema/offline-sample.schema.json`. Result directories are ignored
by Git. Commit only intentionally curated result sets.

`bitrate_kbps` configures the encoder rate-control target. Simple content can
produce a much lower elementary-stream bitrate, while short, complex clips can
temporarily exceed the target because of the VBV window. Always report the
measured `actual_bitrate_kbps` from `summary.json`.

## Controlled live-network impairment

The network matrix runner applies validated `tc netem` conditions to the
publisher container egress and samples the existing tunnel monitor API from its
container. Validate the randomized plan and exact commands without touching the
network:

```bash
make benchmark-network-dry-run
```

Run the short adapter smoke after opening the Direct Viewer on `fish_front`:

```bash
python3 tools/run_network_matrix.py \
  --matrix benchmarks/network/tunnel-direct-single-factor-smoke.json \
  --output benchmark-results/network-single-factor-smoke \
  --overwrite
```

The smoke permits up to 30 ms clock uncertainty so it can validate this
deployment's current clock-sync path. The formal matrix remains stricter at
20 ms; smoke latency distributions are diagnostic and are not formal accuracy
evidence.

The runner always clears the publisher qdisc between conditions and on exit.
It records raw monitor snapshots, normalized samples, applied commands,
readiness probes, per-run summaries, randomized execution order, and aggregate
counter deltas. Stall diagnostics include cumulative freeze/pause counts,
per-stats-interval freeze/pause durations, receive-minus-decode frame backlog,
decoded FPS, and
`requestVideoFrameCallback` gap. The same-origin clock endpoint runs outside
the impaired publisher container, keeping clock estimation on an out-of-band
management path for this adapter.
Each run also stores end-of-condition `tc -s qdisc` output so reports can prove
that media packets actually traversed the intended impairment point.

Before starting, clear any profile managed by the tunnel netem guard:

```bash
cd /path/to/tunnel
scripts/netem-fish-front.sh clear
```

The runner refuses to start while the guard PID file exists because the guard
would otherwise restore its own qdisc during a measured condition. Every run
must independently meet the matrix's minimum ready-sample and clock-valid
sample fractions. Clock-sensitive ORTM/upstream distributions exclude samples
whose clock uncertainty exceeds the declared limit.

The formal matrix is `benchmarks/network/tunnel-direct-single-factor-formal.json`.
It uses five randomized 60-second repetitions for delay, jitter, loss, and
bandwidth conditions. Do not start it until the smoke completes with active,
clock-valid Viewer samples.
