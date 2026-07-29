# Open Raster Timing Marker (ORTM)

ORTM (Open Raster Timing Marker) is a small, codec-resistant in-frame marker for
continuous video latency observation. A publisher burns a sequence number and a
wall-clock timestamp into each video frame. A receiver recovers the marker from
decoded pixels and can estimate frame age, detect frozen frames, and correlate
measurements with transport metrics.

ORTM v0 is intentionally narrow:

- fixed 32 x 32 logical grid;
- four 4 x 4 finder patterns;
- one timing row and one timing column;
- 68 payload bits protected by CRC-16/CCITT-FALSE;
- fixed-ROI decoding with small scale and translation candidates.

The GStreamer adapter and browser demo default to the validated low-impact
rendering profile: `background alpha=0.15`, `cell alpha=0.65`, with only
protocol-bearing cells drawn and an opaque border retained for localization.

It is not a QR-code replacement and it does not perform full-image detection,
rotation recovery, or perspective correction.

## Measurement boundary

An ORTM timestamp is written immediately before video encoding. Decoding ORTM
from a received video frame measures approximately:

```text
pre-encode overlay -> encode -> transport -> decode -> frame available to observer
```

It does not, by itself, measure camera exposure before the overlay or the final
display scan-out after the frame becomes available. Strict glass-to-glass claims
must be calibrated against an external optical reference.

## Clock synchronization

ORTM carries a wall-clock timestamp but does not synchronize clocks inside the
video marker. This repository includes an optional four-timestamp HTTP reference
implementation for clock-corrected approximate G2G measurements:

- `src/js/clock-sync.js`: browser/JavaScript client;
- `src/node/clock-sync.js`: embeddable Node.js request handler;
- `examples/clock-sync-server.mjs`: standalone reference server;
- `docs/clock-sync.md`: protocol, deployment, and source-binding rules.

The clock endpoint MUST represent the same Publisher clock that writes the ORTM
timestamp. Each deployment assigns that clock a stable `clockId`; a Viewer
SHOULD validate the expected `clockId` before accepting a correction.

## Repository layout

- `spec/ORTM-v0.md`: normative wire and raster specification.
- `src/python/ortm`: Python reference codec and fixed-ROI raster decoder.
- `src/js/ortm.js`: JavaScript reference logical codec.
- `src/js/raster.js`: reusable browser fixed-ROI pixel decoder.
- `src/js/clock-sync.js`: four-timestamp clock estimator.
- `src/node/clock-sync.js`: embeddable clock-sync HTTP handler.
- `integrations/clock-sync`: standalone clock-sync container.
- `integrations/gstreamer`: reusable `cairooverlay` adapter.
- `profiles/ortm-v0-fixed-720p.json`: machine-readable sender compatibility profile.
- `tools/validate_frame.py`: strict final-frame sender conformance check.
- `web/index.html`: zero-backend browser encode/decode demo.
- `vectors/ortm-v0.json`: language-neutral golden vectors.
- `tests`: conformance, corruption, rollover, scale, and translation tests.
- `docs/benchmark-plan.md`: validation plan for an academic evaluation.
- `docs/tunnel-migration.md`: safe migration path for the original WebRTC lab.
- `examples/gstreamer_testsrc.py`: real GStreamer smoke-test pipeline.

## Integration guides

- [中文：GStreamer 发送端、Web 前端与 BFF 接入指南](docs/frontend-backend-integration.zh-CN.md)
- [中文：ORTM v0 GStreamer 发送端兼容指南](docs/sender-integration.zh-CN.md)
- [Clock synchronization reference](docs/clock-sync.md)
- [GStreamer integration](integrations/gstreamer/README.md)
- [Benchmark plan](docs/benchmark-plan.md)

## Run the conformance suite

Requirements: Python 3.10+ and Node.js 20+.

```bash
make test
```

Regenerate vectors after an intentional specification change:

```bash
make vectors
```

Run the browser demo from the repository root:

```bash
python3 -m http.server 8080
```

Then open `http://127.0.0.1:8080/web/`.

Run the offline FFmpeg/libx264 codec benchmark (no network required):

```bash
make benchmark-smoke
```

Run the repeated, randomized H.264 matrix smoke suite:

```bash
make benchmark-matrix-smoke
```

See `benchmarks/README.md` for the output schema and artifact options.

Generated vectors are committed. A normal implementation change must not alter
them.

## Status

ORTM v0 is an experimental specification. The bit layout is frozen for
interoperability, while decoder heuristics and rendering profiles may evolve.

## License

MIT
