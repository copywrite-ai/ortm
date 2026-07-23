# codec-core-formal Results

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
- Raw artifact directory: `benchmark-results/codec-core-formal`

Condition order was deterministically randomized. Aggregates combine all
frame-level samples from separate execution repetitions. Source frames are
deterministic, so repeated failures at the same frame are reproducible
content-dependent events, not independent random samples.

## Results

| Variant | Background | Success | Actual bitrate median | ORTM decode p95 | ORTM decode max | Contrast median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| av1 | flat | 100.00% | 2498.66 kbps | 5.734 ms | 25.051 ms | 166.00 |
| av1 | moving-checker | 100.00% | 2558.54 kbps | 2.207 ms | 13.657 ms | 165.17 |
| av1 | stripes | 100.00% | 2503.34 kbps | 5.769 ms | 14.547 ms | 166.06 |
| h264 | flat | 100.00% | 207.52 kbps | 2.216 ms | 20.242 ms | 166.00 |
| h264 | moving-checker | 100.00% | 2640.76 kbps | 5.862 ms | 33.998 ms | 165.33 |
| h264 | stripes | 100.00% | 437.24 kbps | 2.225 ms | 3.002 ms | 166.00 |
| vp8 | flat | 100.00% | 299.75 kbps | 2.203 ms | 3.715 ms | 166.00 |
| vp8 | moving-checker | 100.00% | 3560.70 kbps | 2.201 ms | 2.719 ms | 165.22 |
| vp8 | stripes | 100.00% | 485.94 kbps | 2.217 ms | 2.364 ms | 166.00 |
| vp9 | flat | 100.00% | 169.47 kbps | 3.175 ms | 10.878 ms | 166.00 |
| vp9 | moving-checker | 100.00% | 1909.52 kbps | 2.206 ms | 8.268 ms | 167.17 |
| vp9 | stripes | 100.00% | 235.43 kbps | 5.763 ms | 17.415 ms | 166.00 |

## Interpretation

- Every declared condition decoded successfully; no finder, timing,
  CRC, or frame-identity failures were observed in measured frames.
- ORTM decode p95 ranged from 2.201 ms to
  5.862 ms across aggregate conditions.
- Actual bitrate depends strongly on source content. Target bitrate must not
  be reported as measured encoded bitrate.
- Codec profiles produced different actual rate-control behavior while
  preserving ORTM in this matrix. This is a survivability result, not a
  claim of equivalent visual quality or encoder efficiency.

## Declared Variants

- `h264`: libx264 ultrafast zerolatency.
- `vp8`: libvpx realtime with lookahead and alternate references disabled.
- `vp9`: libvpx-vp9 realtime with lookahead and alternate references disabled.
- `av1`: SVT-AV1 preset 11 with low-delay prediction structure and target CBR.

## Limitations And Next Experiments

- This run does not validate clock synchronization or optical accuracy.
- It does not cover packet loss, jitter, bandwidth transitions, WebRTC
  buffering, browser presentation, or TURN relay behavior.
- Resolution requires a separate declared matrix because the current
  408-pixel outer marker cannot fit in a 360p frame; changing resolution
  and marker geometry together would confound the two effects.
- The next rigorous stages are geometry/resolution tests, controlled network
  impairment, and comparison with an optical reference.
