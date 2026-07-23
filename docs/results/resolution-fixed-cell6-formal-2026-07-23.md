# resolution-fixed-cell6-formal Results

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
- Decoded frames: 35959 / 36000 (99.89%)
- Raw artifact directory: `benchmark-results/resolution-fixed-cell6-formal`

Condition order was deterministically randomized. Aggregates combine all
frame-level samples from separate execution repetitions. Source frames are
deterministic, so repeated failures at the same frame are reproducible
content-dependent events, not independent random samples.

## Results

| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1080p | flat | 100.00% | 382.04 kbps | 2.214 ms | 3.738 ms | 166.00 |
| 1080p | moving-checker | 99.00% | 2445.19 kbps | 2.221 ms | 440.902 ms | 165.00 |
| 1080p | stripes | 100.00% | 473.55 kbps | 2.225 ms | 2.429 ms | 166.00 |
| 360p | flat | 100.00% | 309.53 kbps | 2.138 ms | 3.746 ms | 166.00 |
| 360p | moving-checker | 100.00% | 2542.22 kbps | 2.144 ms | 2.288 ms | 165.44 |
| 360p | stripes | 100.00% | 341.74 kbps | 2.147 ms | 2.372 ms | 166.00 |
| 540p | flat | 100.00% | 330.69 kbps | 2.176 ms | 3.691 ms | 166.00 |
| 540p | moving-checker | 100.00% | 2457.98 kbps | 2.175 ms | 2.649 ms | 165.28 |
| 540p | stripes | 100.00% | 379.20 kbps | 2.186 ms | 3.125 ms | 166.00 |
| 720p | flat | 100.00% | 354.76 kbps | 2.181 ms | 3.714 ms | 166.00 |
| 720p | moving-checker | 99.63% | 2440.03 kbps | 2.180 ms | 440.714 ms | 165.06 |
| 720p | stripes | 100.00% | 422.32 kbps | 2.187 ms | 2.392 ms | 166.00 |

## Interpretation

- Overall frame recovery was 99.89%;
  failures are part of the measured robustness boundary.
- ORTM decode p95 ranged from 2.138 ms to
  2.225 ms across aggregate conditions.
- Actual bitrate depends strongly on source content. Target bitrate must not
  be reported as measured encoded bitrate.

## Boundary Findings

- 360p and 540p recovered 9,000 / 9,000 frames each across all backgrounds.
- At 720p, only moving-checker failed: 2,989 / 3,000 frames recovered
  (99.633%). Failures were concentrated in the first two frames, with one
  repetition also failing frame 2.
- At 1080p, moving-checker recovered 2,970 / 3,000 frames (99.0%). Every
  repetition failed frames 0 through 4 and frame 123; frame 123 was a
  structure mismatch near the key-int=120 boundary.
- Failed frames required exhaustive candidate search and raised ORTM decode
  time to about 441 ms, while successful conditions remained near 2.1-2.2 ms.
- This is an interaction between fixed marker pixels, complex moving content,
  resolution, and the fixed 2.5 Mbps total bitrate. It must not be summarized
  as "high resolution breaks ORTM" in isolation.
- For a fixed cell 6 marker at 2.5 Mbps, 540p is the highest fully recovering
  resolution in this declared matrix. Higher resolutions need a larger marker,
  more bitrate, or both.

## Declared Variants

- `360p`: 640x360 with fixed cell 6 marker.
- `540p`: 960x540 with fixed cell 6 marker.
- `720p`: 1280x720 with fixed cell 6 marker.
- `1080p`: 1920x1080 with fixed cell 6 marker.

## Limitations And Next Experiments

- This run does not validate clock synchronization or optical accuracy.
- It does not cover packet loss, jitter, bandwidth transitions, WebRTC
  buffering, browser presentation, or TURN relay behavior.
- This matrix keeps marker pixels fixed across resolutions. It does not
  test a resolution-normalized marker whose position, cell, and padding
  scale with the video dimensions.
- The next rigorous stages are resolution-normalized geometry, controlled
  network impairment, and comparison with an optical reference.
