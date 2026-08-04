import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  PAYLOAD_CELLS,
  FINDER_LAYOUT_THREE,
  FINDER_LAYOUT_TWO_TOP,
  OrtmDecodeError,
  crc16CcittFalse,
  decodeGrid,
  encodeGrid,
  encodedCells,
  frameAgeMs,
  gridRows,
  rowsToGrid,
} from '../src/js/ortm.js';

const vectors = JSON.parse(
  await readFile(new URL('../vectors/ortm-v0.json', import.meta.url), 'ascii'),
).vectors;

test('CRC-16/CCITT-FALSE standard check value', () => {
  assert.equal(crc16CcittFalse(new TextEncoder().encode('123456789')), 0x29b1);
});

test('JavaScript matches committed Python golden vectors', () => {
  for (const vector of vectors) {
    const grid = encodeGrid(vector.frame_seq, vector.timestamp_ms);
    assert.deepEqual(gridRows(grid), vector.grid, vector.name);
    const decoded = decodeGrid(rowsToGrid(vector.grid));
    assert.equal(decoded.version, vector.version);
    assert.equal(decoded.frameSeq, vector.frame_seq);
    assert.equal(decoded.timestampMs, vector.timestamp_ms);
    assert.equal(decoded.crc16.toString(16).padStart(4, '0'), vector.crc16_hex);
  }
});

test('payload corruption is rejected by CRC', () => {
  const grid = encodeGrid(123, 0x12345678);
  const [row, col] = PAYLOAD_CELLS[20];
  grid[row][col] ^= 1;
  assert.throws(() => decodeGrid(grid), (error) => error instanceof OrtmDecodeError && error.reason === 'crc-mismatch');
});

test('timestamp rollover uses unsigned modulo arithmetic', () => {
  assert.equal(frameAgeMs(3, 0xfffffffa), 9);
});

test('unsupported versions are rejected', () => {
  assert.throws(
    () => decodeGrid(encodeGrid(1, 2, 1)),
    (error) => error instanceof OrtmDecodeError && error.reason === 'unsupported-version',
  );
});

test('three-finder layout requires a layout-aware decoder', () => {
  const grid = encodeGrid(321, 0x12345678, 0, FINDER_LAYOUT_THREE);
  assert.throws(
    () => decodeGrid(grid),
    (error) => error instanceof OrtmDecodeError && error.reason === 'structure-mismatch',
  );
  const decoded = decodeGrid(grid, { finderLayout: FINDER_LAYOUT_THREE });
  assert.equal(decoded.frameSeq, 321);
  assert.equal(decoded.timestampMs, 0x12345678);
  assert.equal(encodedCells(FINDER_LAYOUT_THREE).length, encodedCells().length - 16);
});

test('two-top layout requires a layout-aware decoder', () => {
  const grid = encodeGrid(654, 0x89abcdef, 0, FINDER_LAYOUT_TWO_TOP);
  assert.throws(() => decodeGrid(grid), (error) => (
    error instanceof OrtmDecodeError && error.reason === 'structure-mismatch'
  ));
  const decoded = decodeGrid(grid, { finderLayout: FINDER_LAYOUT_TWO_TOP });
  assert.equal(decoded.frameSeq, 654);
  assert.equal(decoded.timestampMs, 0x89abcdef);
  assert.equal(encodedCells(FINDER_LAYOUT_TWO_TOP).length, encodedCells().length - 32);
});
