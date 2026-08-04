# finder-layout-formal Results

## Scope

This offline experiment measures ORTM v0 survivability and ORTM decoder cost
after a real FFmpeg encode/decode cycle. It does not use a network,
a WebRTC receiver, or a display, so these results are not G2G latency
measurements.

## Method

- Seed: `20260804`
- Measured repetitions per variant: 5
- Warm-up runs per variant: 1
- Completed measured runs: 10
- Decoded frames: 18000 / 18000 (100.00%)
- Raw artifact directory: `benchmark-results/finder-layout-formal`

Condition order was deterministically randomized. Aggregates combine all
frame-level samples from separate execution repetitions. Source frames are
deterministic, so repeated failures at the same frame are reproducible
content-dependent events, not independent random samples.

## Results

| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| four-finder | moving-checker | 100.00% | 2423.40 kbps | 1.968 ms | 2.136 ms | 178.14 |
| four-finder | snow | 100.00% | 2601.10 kbps | 1.967 ms | 7.431 ms | 170.17 |
| four-finder | stripes | 100.00% | 252.83 kbps | 1.964 ms | 4.067 ms | 189.00 |
| three-finder | moving-checker | 100.00% | 2405.37 kbps | 1.971 ms | 2.216 ms | 178.39 |
| three-finder | snow | 100.00% | 2603.61 kbps | 1.963 ms | 2.258 ms | 168.39 |
| three-finder | stripes | 100.00% | 251.38 kbps | 1.967 ms | 4.223 ms | 209.33 |

## Interpretation

- Every declared condition decoded successfully; no finder, timing,
  CRC, or frame-identity failures were observed in measured frames.
- ORTM decode p95 ranged from 1.963 ms to
  1.971 ms across aggregate conditions.
- Actual bitrate depends strongly on source content. Target bitrate must not
  be reported as measured encoded bitrate.
- Omitting the bottom-right finder reduced encoded cells from 195 to
  179 (8.2%) without an observed recovery failure in this matrix.
- Decode p95 and actual bitrate remained effectively unchanged; the
  expected benefit is lower visual salience, not throughput or latency.
- The three-finder image requires an explicitly layout-aware decoder and
  must not be presented as backward-compatible ORTM v0 imagery.

## Declared Variants

- `four-finder`: Standard ORTM v0 four-corner finder layout.
- `three-finder`: Experimental layout omitting the bottom-right finder while retaining its reserved cells.

## Limitations And Next Experiments

- This run does not validate clock synchronization or optical accuracy.
- It uses fixed 720p geometry and a fixed-ROI decoder; it does not measure
  full-image detection, false positives, rotation, scale, or perspective.
- It does not cover camera content, packet loss, jitter, WebRTC buffering,
  browser presentation, or TURN relay behavior.
- The next step is a live camera/WebRTC comparison, followed by controlled
  translation, scale, rotation, and perspective stress tests.
