import assert from 'node:assert/strict';
import test from 'node:test';

import {
  FINDER_LAYOUT_THREE,
  FINDER_LAYOUT_TWO_TOP,
  PAYLOAD_CELLS,
  encodeGrid,
  encodedCells,
} from '../src/js/ortm.js';
import { DEFAULT_RASTER_PROFILE, buildReadRoi, decodeRgbaImage } from '../src/js/raster.js';

function renderRgba(
  frameSeq,
  timestampMs,
  actual = DEFAULT_RASTER_PROFILE,
  {
    backgroundAlpha = 1,
    cellAlpha = 1,
    striped = false,
    finderLayout = 'four',
  } = {},
) {
  const width = 640;
  const height = 480;
  const data = new Uint8ClampedArray(width * height * 4);
  for (let offset = 0; offset < data.length; offset += 4) {
    const pixel = offset / 4;
    const x = pixel % width;
    const value = striped ? (Math.floor(x / 12) % 2 ? 230 : 25) : 127;
    data[offset] = value;
    data[offset + 1] = value;
    data[offset + 2] = value;
    data[offset + 3] = 255;
  }
  const grid = encodeGrid(frameSeq, timestampMs, 0, finderLayout);
  const originX = actual.x + actual.padding;
  const originY = actual.y + actual.padding;
  const blendRect = (x0, y0, x1, y1, value, alpha) => {
    for (let y = Math.round(y0); y < Math.round(y1); y += 1) {
      for (let x = Math.round(x0); x < Math.round(x1); x += 1) {
        const offset = (y * width + x) * 4;
        for (let channel = 0; channel < 3; channel += 1) {
          data[offset + channel] = Math.round(value * alpha + data[offset + channel] * (1 - alpha));
        }
      }
    }
  };
  const boxSize = 32 * actual.cell + actual.padding * 2;
  blendRect(actual.x, actual.y, actual.x + boxSize, actual.y + boxSize, 255, backgroundAlpha);
  for (const [row, col] of encodedCells(finderLayout)) {
    const value = grid[row][col] ? 0 : 255;
    blendRect(
      originX + col * actual.cell,
      originY + row * actual.cell,
      originX + (col + 1) * actual.cell,
      originY + (row + 1) * actual.cell,
      value,
      cellAlpha,
    );
  }
  return { imageData: { data, width, height }, width, height };
}

test('fixed-ROI RGBA decoder reads a nominal marker', () => {
  const timestampMs = 0x12345678;
  const frame = renderRgba(321, timestampMs);
  const result = decodeRgbaImage(frame.imageData, frame.width, frame.height, timestampMs + 37);
  assert.equal(result.ok, true);
  assert.equal(result.frame_seq, 321);
  assert.equal(result.timestamp_ms, timestampMs);
  assert.equal(result.latency_ms, 37);
  assert.equal(result.raw_age_ms, 37);
  assert.equal(result.finder_errors, 0);
  assert.equal(result.timing_errors, 0);
});

test('latency range failure preserves the CRC-validated marker and signed clock delta', () => {
  const timestampMs = 10_000;
  const frame = renderRgba(42, timestampMs);
  const result = decodeRgbaImage(frame.imageData, frame.width, frame.height, timestampMs - 2_000);
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'latency-out-of-range');
  assert.equal(result.frame_seq, 42);
  assert.equal(result.timestamp_ms, timestampMs);
  assert.equal(result.raw_age_ms, -2_000);
});

test('fixed-ROI RGBA decoder tolerates supported scale and translation', () => {
  const actual = { ...DEFAULT_RASTER_PROFILE, x: 28, y: 16, cell: 11.4, padding: 11.4 };
  const timestampMs = 0x89abcdef;
  const frame = renderRgba(777, timestampMs, actual);
  const result = decodeRgbaImage(frame.imageData, frame.width, frame.height, timestampMs + 50);
  assert.equal(result.ok, true);
  assert.equal(result.frame_seq, 777);
  assert.equal(result.latency_ms, 50);
});

test('validated low-impact profile decodes over black and white stripes', () => {
  const timestampMs = 0x2468ace0;
  const frame = renderRgba(909, timestampMs, DEFAULT_RASTER_PROFILE, {
    backgroundAlpha: 0.15,
    cellAlpha: 0.65,
    striped: true,
  });
  const result = decodeRgbaImage(frame.imageData, frame.width, frame.height, timestampMs + 44);
  assert.equal(result.ok, true);
  assert.equal(result.frame_seq, 909);
  assert.equal(result.timestamp_ms, timestampMs);
  assert.equal(result.latency_ms, 44);
  assert.ok(result.contrast >= 32);
});

test('fixed-ROI RGBA decoder reports CRC damage', () => {
  const timestampMs = 1000;
  const frame = renderRgba(5, timestampMs);
  const [row, col] = PAYLOAD_CELLS[30];
  const profile = { ...DEFAULT_RASTER_PROFILE, scales: [1], offsets: [0] };
  const x0 = profile.x + profile.padding + col * profile.cell;
  const y0 = profile.y + profile.padding + row * profile.cell;
  const current = frame.imageData.data[(Math.round(y0 + 1) * frame.width + Math.round(x0 + 1)) * 4];
  const replacement = current < 128 ? 230 : 20;
  for (let y = y0; y < y0 + profile.cell; y += 1) {
    for (let x = x0; x < x0 + profile.cell; x += 1) {
      const offset = (Math.round(y) * frame.width + Math.round(x)) * 4;
      frame.imageData.data[offset] = replacement;
      frame.imageData.data[offset + 1] = replacement;
      frame.imageData.data[offset + 2] = replacement;
    }
  }
  const result = decodeRgbaImage(frame.imageData, frame.width, frame.height, timestampMs + 10, { profile });
  assert.equal(result.ok, false);
  assert.equal(result.reason, 'crc-mismatch');
});

test('read ROI contains all configured candidates', () => {
  const roi = buildReadRoi();
  assert.deepEqual(roi, { x: 12, y: 12, width: 473, height: 473 });
});

test('fixed-ROI decoder reads a three-finder marker when configured', () => {
  const timestampMs = 0x13572468;
  const profile = {
    ...DEFAULT_RASTER_PROFILE,
    finderLayout: FINDER_LAYOUT_THREE,
  };
  const frame = renderRgba(654, timestampMs, profile, {
    finderLayout: FINDER_LAYOUT_THREE,
  });
  const result = decodeRgbaImage(
    frame.imageData,
    frame.width,
    frame.height,
    timestampMs + 25,
    { profile },
  );
  assert.equal(result.ok, true);
  assert.equal(result.frame_seq, 654);
  assert.equal(result.latency_ms, 25);
});

test('fixed-ROI decoder reads a two-top marker when configured', () => {
  const timestampMs = 0x24681357;
  const profile = {
    ...DEFAULT_RASTER_PROFILE,
    finderLayout: FINDER_LAYOUT_TWO_TOP,
  };
  const frame = renderRgba(987, timestampMs, profile, {
    finderLayout: FINDER_LAYOUT_TWO_TOP,
  });
  const result = decodeRgbaImage(
    frame.imageData,
    frame.width,
    frame.height,
    timestampMs + 19,
    { profile },
  );
  assert.equal(result.ok, true);
  assert.equal(result.frame_seq, 987);
  assert.equal(result.latency_ms, 19);
});
