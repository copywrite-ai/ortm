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
