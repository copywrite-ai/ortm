# resolution-normalized-formal Results

## Scope

This offline experiment measures ORTM v0 survivability and ORTM decoder cost
after a real FFmpeg encode/decode cycle. It does not use a network,
a WebRTC receiver, or a display, so these results are not G2G latency
measurements.

## Method

- Seed: `20260723`
- Measured repetitions per variant: 5
- Warm-up runs per variant: 1
- Completed measured runs: 20
- Decoded frames: 36000 / 36000 (100.00%)
- Raw artifact directory: `benchmark-results/resolution-normalized-formal`

Condition order was deterministically randomized. Aggregates combine all
frame-level samples from separate execution repetitions. Source frames are
deterministic, so repeated failures at the same frame are reproducible
content-dependent events, not independent random samples.

## Results

| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1080p-cell12 | flat | 100.00% | 205.18 kbps | 2.259 ms | 5.329 ms | 166.00 |
| 1080p-cell12 | moving-checker | 100.00% | 2635.83 kbps | 2.258 ms | 2.955 ms | 163.72 |
| 1080p-cell12 | stripes | 100.00% | 500.71 kbps | 2.258 ms | 2.452 ms | 166.00 |
| 360p-cell4 | flat | 100.00% | 70.72 kbps | 2.150 ms | 3.757 ms | 166.00 |
| 360p-cell4 | moving-checker | 100.00% | 2377.39 kbps | 2.149 ms | 2.256 ms | 165.22 |
| 360p-cell4 | stripes | 100.00% | 88.88 kbps | 2.155 ms | 2.822 ms | 166.00 |
| 540p-cell6 | flat | 100.00% | 330.69 kbps | 2.159 ms | 3.771 ms | 166.00 |
| 540p-cell6 | moving-checker | 100.00% | 2457.98 kbps | 2.160 ms | 2.273 ms | 165.22 |
| 540p-cell6 | stripes | 100.00% | 379.16 kbps | 2.157 ms | 2.302 ms | 166.00 |
| 720p-cell8 | flat | 100.00% | 138.67 kbps | 2.188 ms | 3.682 ms | 166.00 |
| 720p-cell8 | moving-checker | 100.00% | 2580.08 kbps | 2.190 ms | 2.398 ms | 165.67 |
| 720p-cell8 | stripes | 100.00% | 268.28 kbps | 2.193 ms | 2.376 ms | 176.17 |

## Interpretation

- Every declared condition decoded successfully; no finder, timing,
  CRC, or frame-identity failures were observed in measured frames.
- ORTM decode p95 ranged from 2.149 ms to
  2.259 ms across aggregate conditions.
- Actual bitrate depends strongly on source content. Target bitrate must not
  be reported as measured encoded bitrate.

## Paired Findings

- The normalized profiles recovered 36,000 / 36,000 frames across all four
  resolutions and three backgrounds.
- The paired fixed-cell matrix failed moving-checker at 720p (99.633%) and
  1080p (99.0%). Scaling cell 6 to cell 8 and cell 12 respectively removed
  every observed failure under the same 60 fps and 2.5 Mbps target.
- Successful ORTM decode p95 remained between 2.149 ms and 2.259 ms; increasing
  marker pixels did not create a material decoder-cost increase in this test.
- The result supports a relative-size policy: preserve approximately the same
  marker-to-frame ratio instead of using one fixed cell size at every
  resolution.
- This is a combined geometry mitigation. Because x, y, cell, and padding all
  changed together, the experiment does not assign the recovery to one field.

## Declared Variants

- `360p-cell4`: 640x360 with proportional x16/y16/cell4/padding8 geometry.
- `540p-cell6`: 960x540 anchor with x24/y24/cell6/padding12 geometry.
- `720p-cell8`: 1280x720 with proportional x32/y32/cell8/padding16 geometry.
- `1080p-cell12`: 1920x1080 with proportional x48/y48/cell12/padding24 geometry.

## Limitations And Next Experiments

- This run does not validate clock synchronization or optical accuracy.
- It does not cover packet loss, jitter, bandwidth transitions, WebRTC
  buffering, browser presentation, or TURN relay behavior.
- This matrix scales marker position, cell, and padding together. It
  validates the combined resolution-normalized profile but does not
  isolate the contribution of each geometry parameter.
- The next rigorous stages are controlled network impairment and
  comparison with an optical reference.
