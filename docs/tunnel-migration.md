# Migrating the tunnel lab to ORTM packages

The tunnel lab currently contains independent copies of the ORTM encoder and
fixed-ROI browser decoder. Do not replace them with a sibling-directory import;
that would work on one workstation but fail in Docker and CI.

## Prerequisites

1. Commit and publish this repository at a stable Git URL.
2. Tag the first compatible release, initially `v0.1.0`.
3. Keep `vectors/ortm-v0.json` unchanged for all v0-compatible releases.

## Publisher migration

The current publisher owns copies of grid constants, finder layout, CRC, and
payload encoding. Replace those definitions with imports from `ortm.codec` and
replace the local Cairo renderer with `integrations/gstreamer/ortm_overlay.py`.

The publisher may retain application-specific behavior such as:

- PTS-to-frame metric correlation;
- `overlay_to_send_ms` collection;
- timestamp text displayed beside the marker;
- WHIP endpoint and request-pad handling;
- environment-variable parsing.

Pin the Python dependency to a release tag or immutable commit in the publisher
image. Do not install from an unpinned default branch.

## Browser migration

Replace the inline implementations of CRC, logical-grid decoding, candidate
construction, luma sampling, and fixed-ROI decoding with imports from:

```js
import { decodeGrid } from './vendor/ortm/ortm.js';
import { buildReadRoi, decodeRgbaImage } from './vendor/ortm/raster.js';
```

The viewer should retain application-specific behavior such as WHEP signaling,
`requestVideoFrameCallback`, charting, logging, Prometheus export, and freeze
policy. Copy or bundle tagged ORTM modules during the build; do not reference a
developer workstation path from browser code.

## Compatibility gate

Before removing the old implementations:

1. run both encoders against every committed golden vector;
2. decode old publisher frames with the new browser module;
3. decode new publisher frames with the old decoder;
4. run a `fish_front` direct canary and compare decode success, ORTM latency,
   frame sequence, and freeze events;
5. remove duplicate code only after the canary passes.

TURN relay behavior is outside the codec migration and should be tested only
after direct playback remains stable.
