# ORTM Validation and Benchmark Plan

## Claims to validate

1. Python and JavaScript implementations are bit-compatible.
2. The marker survives expected encoding, scaling, and background variation.
3. ORTM detects latency growth, frozen frames, and frame discontinuities.
4. ORTM estimates agree with an external optical reference within a measured
   error bound.
5. Render, decode, image-area, and bitrate overheads are small enough for
   continuous observation.

## Ground truth

Use an LED and photodiode/microcontroller setup, or a sufficiently high-frame-rate
camera that observes both the source event and receiver display. Run ORTM and
the optical method simultaneously.

Report at minimum:

- signed bias (`ORTM - optical`);
- mean absolute error;
- median, p95, and p99 absolute error;
- decode success rate with a confidence interval;
- false freeze and missed freeze rates;
- clock offset and uncertainty during every run.

## Baselines

- burned-in wall-clock text decoded with OCR;
- QR Code or Data Matrix carrying the same payload;
- WebRTC `getStats()` receiver metrics;
- external optical measurement.

## Experiment matrix

Vary one factor at a time around a declared reference configuration, then run a
smaller interaction matrix for known coupled factors such as FPS and bitrate.

| Factor | Levels |
| --- | --- |
| codec | H.264, VP8, VP9, AV1 |
| resolution | 640x360, 960x540, 1280x720, 1920x1080 |
| frame rate | 15, 30, 50, 60 fps |
| bitrate | under-provisioned, nominal, over-provisioned |
| key-frame interval | 1 s, 2 s, 4 s |
| path | loopback, direct network, TURN relay |
| impairment | delay, jitter, loss, bandwidth changes |
| background | flat, natural, high-frequency stripes, moving texture |
| geometry | nominal, scale candidates, translation candidates |
| rendering | opaque and declared alpha profiles |

Each condition should have a warm-up period, a fixed observation duration, at
least five independent repetitions, and raw per-frame data. Randomize condition
order where thermal state or network history could bias results.

## Avoided biases

- A 200 ms decoder interval samples frames rather than measuring every frame.
  Report this sampling policy and use per-frame decoding for accuracy studies.
- Do not treat repeated observations from one run as independent experiments.
- Do not discard CRC failures; failure rate is a primary result.
- Record actual encoded bitrate, received FPS, loss, jitter, and clock health.
- Separate transport latency from browser observation and display latency.

## Reproducibility artifacts

- container images or pinned dependency manifests;
- exact pipeline and encoder properties;
- network impairment configuration and random seed;
- raw measurements in a documented CSV or JSONL schema;
- analysis scripts that recreate every table and figure;
- a small redistributable set of encoded marker clips.

## Current executable matrices

`benchmarks/matrices/h264-core-formal.json` implements the first one-factor
formal matrix around the validated 540p60 H.264 profile. It fixes each measured
run to ten seconds, performs one warm-up run per variant, uses five independent
repetitions, and randomizes measured execution order with a committed seed.

The first matrix covers FPS, target bitrate, key-frame interval, and rendering
alpha. Resolution is deferred to a separate matrix because the default 408-pixel
outer marker does not fit at 360p. That experiment must explicitly distinguish
constant-pixel marker geometry from resolution-normalized marker geometry.

`benchmarks/matrices/codec-core-formal.json` holds all declared video and marker
factors constant while comparing fixed low-latency-oriented FFmpeg profiles for
H.264, VP8, VP9, and AV1. Codec results establish ORTM survivability under each
profile; they are not a codec quality or real-time CPU benchmark.

`benchmarks/matrices/geometry-cell-exploratory.json` searches cell sizes from
12 pixels down to 1 pixel at the fixed H.264 baseline. It is intentionally a
short boundary finder. A formal geometry matrix must be declared only after the
first passing/failing interval is known.

The exploratory run located that interval between cells 3 and 4. The formal
follow-up in `benchmarks/matrices/geometry-cell-formal.json` measures cells 3,
4, 6, and 12 for ten seconds with five independent repetitions.

`benchmarks/matrices/resolution-fixed-cell6-exploratory.json` then fixes marker
geometry at cell 6 while varying 360p, 540p, 720p, and 1080p. This isolates the
effect of video resolution at a common 60 fps and 2500 kbps target before any
resolution-normalized marker experiment is attempted.

The exploratory result found moving-texture failures at 720p and 1080p. The
formal follow-up in `benchmarks/matrices/resolution-fixed-cell6-formal.json`
keeps all four resolutions to measure both the passing controls and failing
boundary under the same randomized repetition policy.

`benchmarks/matrices/resolution-normalized-exploratory.json` is the paired
follow-up. It holds the marker at 40% of frame height by scaling x, y, cell, and
padding around the 540p/cell 6 reference.

The paired exploration recovered every frame. Its formal follow-up is declared
in `benchmarks/matrices/resolution-normalized-formal.json` with the same
ten-second, five-repetition policy as the fixed-pixel matrix.

## Controlled network impairment stage

`benchmarks/network/tunnel-direct-single-factor-smoke.json` validates the live
adapter with representative clear, delay, jitter, loss, and bandwidth
conditions. The formal matrix varies one factor at a time, uses five randomized
60-second repetitions, samples every two seconds, and preserves raw monitor
snapshots plus normalized ORTM/WebRTC/publisher metrics.

Netem is applied only to the publisher media container egress. The clock-sync
HTTP endpoint remains on an out-of-band management path, preventing the
controlled one-way media impairment from biasing the four-timestamp estimate.
Optical ground truth is explicitly deferred; live reports must continue to call
the result clock-corrected approximate G2G.
