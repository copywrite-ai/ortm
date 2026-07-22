# Offline codec benchmark

The offline benchmark renders deterministic ORTM frames, sends them through a
real FFmpeg/libx264 encode/decode cycle, and decodes ORTM from the resulting
pixels. It does not open a network connection and does not measure G2G latency.

The committed baseline is a two-second smoke suite per background. It verifies
the harness and catches gross regressions; it is not long enough for a
publication-quality statistical claim. Formal runs must use the repetition and
observation policy in `docs/benchmark-plan.md`.

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
