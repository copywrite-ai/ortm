# ORTM v0 Specification

Status: Experimental, bit layout frozen

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT,
RECOMMENDED, MAY, and OPTIONAL are to be interpreted as described in RFC 2119.

## 1. Scope

ORTM v0 carries a frame sequence number and a wall-clock timestamp in visible
video pixels. It is designed for a known region of interest and small geometric
variation. Full-image location, rotation, and perspective recovery are outside
the v0 scope.

## 2. Coordinate system and logical grid

The marker is a 32 x 32 grid. Rows increase downwards and columns increase to
the right. Cell `(0, 0)` is the top-left cell.

The default raster profile is:

| Parameter | Value |
| --- | ---: |
| outer box x | 24 pixels |
| outer box y | 24 pixels |
| cell size | 12 pixels |
| padding | 12 pixels |
| grid size | 32 cells |
| marker content size | 384 pixels |
| outer box size | 408 pixels |

The logical format is independent of these raster dimensions.

## 3. Reserved cells

Four 4 x 4 finder patterns occupy these inclusive row/column ranges:

- top-left: rows 0..3, columns 0..3;
- top-right: rows 0..3, columns 28..31;
- bottom-left: rows 28..31, columns 0..3;
- bottom-right: rows 28..31, columns 28..31.

A finder cell is black (`1`) on its outer ring and white (`0`) in its 2 x 2
interior.

Row 4 is the timing row. Outside finder cells, its logical bit is `column mod 2`.
Column 4 is the timing column. Outside finder cells, its logical bit is
`row mod 2`.

Finder cells take precedence over timing cells. Timing cells take precedence
over payload cells.

## 4. Payload

The payload is 68 bits. Fields are appended most-significant bit first:

| Field | Width | v0 meaning |
| --- | ---: | --- |
| version | 4 bits | MUST be zero |
| frame_seq | 16 bits | unsigned frame sequence modulo 65536 |
| timestamp_ms | 32 bits | Unix wall-clock milliseconds modulo 2^32 |
| crc16 | 16 bits | CRC-16/CCITT-FALSE |

Payload bits are written row-major into non-reserved cells, starting at the
first available cell. Only the first 68 non-reserved cells are encoded cells.
Remaining non-reserved cells are unused and MUST be ignored by decoders.

## 5. CRC byte representation

CRC-16/CCITT-FALSE parameters are:

```text
width   = 16
poly    = 0x1021
init    = 0xffff
refin   = false
refout  = false
xorout  = 0x0000
check("123456789") = 0x29b1
```

The CRC input is exactly seven bytes:

```text
byte 0: 0000vvvv, where vvvv is the 4-bit version
byte 1: frame_seq bits 15..8
byte 2: frame_seq bits 7..0
byte 3: timestamp_ms bits 31..24
byte 4: timestamp_ms bits 23..16
byte 5: timestamp_ms bits 15..8
byte 6: timestamp_ms bits 7..0
```

This one-byte representation of the 4-bit version is normative.

## 6. Raster rendering

Logical `1` is black and logical `0` is white. A lossless conformance renderer
MUST draw encoded cells without antialiasing. An implementation MAY use alpha
blending for production video, but the composited result must preserve enough
finder contrast for decoding.

The recommended opaque profile draws:

1. a white outer box;
2. a black border around the outer box;
3. every encoded cell as a complete black or white rectangle.

The recommended transparent profile draws:

1. a white outer box with configurable background alpha;
2. encoded black and white cells with configurable cell alpha;
3. an opaque black border.

The currently validated low-impact profile uses outer-box alpha `0.15`, encoded
cell alpha `0.65`, and an opaque 2-pixel border. These are rendering defaults,
not part of the v0 logical format; applications SHOULD validate them against
their own codecs, bitrates, resolutions, and scene content.

Unused cells MAY remain transparent. Their pixels have no logical value.

## 7. Fixed-ROI decoding

A v0 fixed-ROI decoder SHOULD test the nominal raster profile and a bounded set
of scale and translation candidates. For each candidate it SHOULD:

1. sample multiple interior points per encoded cell;
2. derive black and white levels from expected finder cells;
3. threshold cells using the midpoint of those levels;
4. reject insufficient contrast or excessive finder/timing errors;
5. read the first 68 payload cells in row-major order;
6. reject unsupported versions and CRC mismatch.

Reference candidate values are:

```text
scale:  1.00, 0.95, 1.05, 0.90, 1.10
dx/dy:  0, -4, 4, -8, 8, -12, 12 pixels
```

Candidate ordering is an implementation detail. CRC success is authoritative.

## 8. Time arithmetic

For a synchronized receiver wall clock `now_ms`, frame age is:

```text
age_ms = (uint32(now_ms) - timestamp_ms) modulo 2^32
```

An application MUST apply a plausible upper bound before accepting the result.
The reference profile accepts `0 <= age_ms < 5000`.

ORTM does not synchronize clocks. The measured value contains sender/receiver
clock offset and clock error. Experiments MUST record their synchronization
method and measured uncertainty.

## 9. Sequence semantics

`frame_seq` increments once for every frame on which the marker is rendered and
wraps modulo 65536. Repeated sequence values can indicate a displayed-frame
freeze. A sequence discontinuity can indicate dropped, skipped, or unobserved
frames; ORTM alone cannot distinguish those causes.

## 10. Measurement semantics

The timestamp SHOULD be sampled as close as possible to the completion of source
frame acquisition and MUST be sampled before encoding. A receiver timestamp is
taken when the decoded frame is observed by the decoder.

This interval is an in-frame, pre-encode-to-observer latency. It is only strict
glass-to-glass latency after calibration against camera exposure and physical
display scan-out.
