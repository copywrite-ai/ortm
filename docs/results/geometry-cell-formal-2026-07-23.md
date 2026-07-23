# geometry-cell-formal Results

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
- Decoded frames: 35990 / 36000 (99.97%)
- Raw artifact directory: `benchmark-results/geometry-cell-formal`

Condition order was deterministically randomized. Aggregates combine all
frame-level samples from separate execution repetitions. Source frames are
deterministic, so repeated failures at the same frame are reproducible
content-dependent events, not independent random samples.

## Results

| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| cell12 | flat | 100.00% | 207.47 kbps | 2.182 ms | 3.738 ms | 166.00 |
| cell12 | moving-checker | 100.00% | 2640.76 kbps | 2.183 ms | 2.283 ms | 165.39 |
| cell12 | stripes | 100.00% | 437.29 kbps | 2.184 ms | 2.352 ms | 166.00 |
| cell3 | flat | 100.00% | 361.51 kbps | 2.226 ms | 3.830 ms | 166.00 |
| cell3 | moving-checker | 99.67% | 2180.26 kbps | 2.236 ms | 449.423 ms | 163.61 |
| cell3 | stripes | 100.00% | 392.54 kbps | 2.237 ms | 2.794 ms | 165.78 |
| cell4 | flat | 100.00% | 91.92 kbps | 2.160 ms | 3.826 ms | 166.00 |
| cell4 | moving-checker | 100.00% | 2265.69 kbps | 2.167 ms | 2.815 ms | 165.22 |
| cell4 | stripes | 100.00% | 126.63 kbps | 2.166 ms | 2.300 ms | 166.00 |
| cell6 | flat | 100.00% | 330.69 kbps | 2.233 ms | 3.761 ms | 166.00 |
| cell6 | moving-checker | 100.00% | 2457.98 kbps | 2.236 ms | 2.387 ms | 165.19 |
| cell6 | stripes | 100.00% | 379.20 kbps | 2.246 ms | 2.440 ms | 166.00 |

## Interpretation

- Overall frame recovery was 99.97%;
  failures are part of the measured robustness boundary.
- ORTM decode p95 ranged from 2.160 ms to
  2.246 ms across aggregate conditions.
- Actual bitrate depends strongly on source content. Target bitrate must not
  be reported as measured encoded bitrate.

## Boundary Findings

- `cell=4` is the smallest fully recovering size in this declared matrix:
  9,000 / 9,000 frames passed across flat, stripes, and moving-checker.
- `cell=3` failed exactly the first two moving-checker frames in every
  repetition. The 10 failures were all `low-contrast`, showing a deterministic
  stream-start/content interaction rather than random loss.
- A failed `cell=3` frame required exhaustive candidate search and raised ORTM
  decode time to 449.423 ms, although successful-frame behavior stayed near
  the normal 2.2 ms range.
- The exploratory matrix produced 0% recovery for cells 1 and 2. The tested
  geometry boundary is therefore between cells 3 and 4.
- `cell=4` is a laboratory minimum, not yet a production recommendation.
  Scaling, packet loss, transcoding, and natural camera content remain untested;
  use cell 6 or larger when margin matters, while cell 12 remains the validated
  live reference.

## Declared Variants

- `cell3`: First partially failing size in the exploratory matrix.
- `cell4`: Smallest size with complete exploratory recovery.
- `cell6`: Intermediate geometry reference.
- `cell12`: Current validated geometry reference.

## Limitations And Next Experiments

- This run does not validate clock synchronization or optical accuracy.
- It does not cover packet loss, jitter, bandwidth transitions, WebRTC
  buffering, browser presentation, or TURN relay behavior.
- Resolution requires a separate declared matrix because the current
  408-pixel outer marker cannot fit in a 360p frame; changing resolution
  and marker geometry together would confound the two effects.
- The next rigorous stages are geometry/resolution tests, controlled network
  impairment, and comparison with an optical reference.
