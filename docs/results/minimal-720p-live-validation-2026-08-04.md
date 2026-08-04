# Minimal 720p ORTM Live Validation

## Scope

This engineering validation evaluates a low-obstruction ORTM v0 rendering
profile in a live GStreamer H.264 to WHIP to browser WHEP path. It validates
marker survivability under changing image content; it is not a controlled G2G
latency benchmark.

## Configuration

- Video: 1280x720, 60 fps, 2500 kbps target, H.264 ultrafast, key-int 120
- Marker: x=32, y=32, cell=8, padding=16
- Rendering: background alpha 0, cell alpha 0.70, border alpha 0
- Decoder: fixed ROI, nominal scale 1.0

## Observations

| Background | Decoded frames | Success | Structure failures | Contrast |
| --- | ---: | ---: | ---: | ---: |
| Moving checker, validation window A | 239 / 239 | 100% | 0 | about 183 |
| Moving checker, rebuilt default path | 504 / 504 | 100% | 0 | about 177 |
| Per-frame snow pressure test | 296 / 296 | 100% | 0 | about 163 |

The exact sparse profile decoded 1039 / 1039 observed frames. A nearby cell
alpha of 0.675 produced CRC failures in an earlier boundary run, so 0.70 is the
lowest validated value, not proof of a broad production margin.

## Reproducible Offline Check

The committed `h264-720p60-2500k-minimal.json` scenario was also run through an
FFmpeg/libx264 encode/decode cycle for 600 frames per background:

| Background | Decoded frames | Success | Actual bitrate | Decode p95 | Median contrast |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stripes | 600 / 600 | 100% | 252.8 kbps | 1.873 ms | 189.0 |
| Moving checker | 600 / 600 | 100% | 2423.2 kbps | 1.869 ms | 178.2 |
| Deterministic snow | 600 / 600 | 100% | 2602.5 kbps | 1.870 ms | 170.2 |

This local run used Python 3.14.6 and an FFmpeg 2026 development build. The
scenario is reproducible, but the table remains one run rather than a formal
multi-repetition matrix.

## Interpretation

- Removing both the translucent panel and border substantially reduces the
  occupied visual area without changing the ORTM v0 payload.
- Cell size 8 preserved the resolution-normalized geometry previously validated
  at 720p.
- Dynamic checker and snow content did not cause an observed failure at alpha
  0.70 in these windows.
- Snow reduced delivered viewer FPS in one live pressure run even though ORTM
  decoding remained successful. It should remain a stress case, not a normal
  source profile.

## Limitations

- These are finite live observation windows, not randomized formal repetitions.
- Raw live logs are not committed, so the live table is an engineering record;
  the offline scenario provides the reproducible portion of this validation.
- The test does not cover camera motion classes, codec implementations other
  than the tested H.264 path, packet loss, relay transport, or optical latency.
- Use the committed offline scenario for reproducible codec testing and run
  longer live trials before treating this profile as a production default.
