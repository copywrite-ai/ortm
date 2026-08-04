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
- Completed measured runs: 15
- Decoded frames: 27000 / 27000 (100.00%)
- Raw artifact directory: `benchmark-results/finder-layout-formal`

Condition order was deterministically randomized. Aggregates combine all
frame-level samples from separate execution repetitions. Source frames are
deterministic, so repeated failures at the same frame are reproducible
content-dependent events, not independent random samples.

## Results

| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| four-finder | moving-checker | 100.00% | 2421.62 kbps | 1.978 ms | 2.127 ms | 178.11 |
| four-finder | snow | 100.00% | 2604.03 kbps | 1.972 ms | 2.172 ms | 170.17 |
| four-finder | stripes | 100.00% | 252.83 kbps | 1.969 ms | 4.364 ms | 189.00 |
| three-finder | moving-checker | 100.00% | 2405.73 kbps | 1.969 ms | 2.093 ms | 178.39 |
| three-finder | snow | 100.00% | 2603.67 kbps | 1.964 ms | 2.257 ms | 168.39 |
| three-finder | stripes | 100.00% | 251.38 kbps | 1.967 ms | 4.047 ms | 209.33 |
| two-top-finder | moving-checker | 100.00% | 2375.04 kbps | 1.967 ms | 2.199 ms | 178.17 |
| two-top-finder | snow | 100.00% | 2595.92 kbps | 1.965 ms | 5.553 ms | 168.50 |
| two-top-finder | stripes | 100.00% | 250.65 kbps | 1.959 ms | 4.165 ms | 189.00 |

## Interpretation

- Every declared condition decoded successfully; no finder, timing,
  CRC, or frame-identity failures were observed in measured frames.
- ORTM decode p95 ranged from 1.959 ms to
  1.978 ms across aggregate conditions.
- Actual bitrate depends strongly on source content. Target bitrate must not
  be reported as measured encoded bitrate.
- Omitting the bottom-right finder reduced encoded cells from 195 to
  179 (8.2%); retaining only the two top finders reduced them to 163
  (16.4%). No recovery failure was observed in this matrix.
- Decode p95 and actual bitrate remained effectively unchanged; the
  expected benefit is lower visual salience, not throughput or latency.
- The sparse finder images require an explicitly layout-aware decoder and
  must not be presented as backward-compatible ORTM v0 imagery.
- The two-top finders are collinear. This layout is intended only for fixed
  ROI use and sacrifices geometric evidence needed for robust rotation,
  perspective, and full-image detection.

## Declared Variants

- `four-finder`: Standard ORTM v0 four-corner finder layout.
- `three-finder`: Experimental layout omitting the bottom-right finder while retaining its reserved cells.
- `two-top-finder`: Experimental layout retaining only the two top finders while all four corner areas remain reserved.

## Limitations And Next Experiments

- This run does not validate clock synchronization or optical accuracy.
- It uses fixed 720p geometry and a fixed-ROI decoder; it does not measure
  full-image detection, false positives, rotation, scale, or perspective.
- It does not cover camera content, packet loss, jitter, WebRTC buffering,
  browser presentation, or TURN relay behavior.
- The next step is a live camera/WebRTC comparison, followed by controlled
  translation, scale, rotation, and perspective stress tests.
