import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import test from 'node:test';

import {
  CLOCK_SYNC_PROTOCOL,
  ClockSynchronizer,
  calculateClockSample,
  selectClockEstimate,
} from '../src/js/clock-sync.js';
import { createClockSyncHandler } from '../src/node/clock-sync.js';

test('calculates NTP offset and network RTT', () => {
  const sample = calculateClockSample({
    clientSendUnixMs: 1000,
    serverReceiveUnixMs: 1055,
    serverSendUnixMs: 1057,
    clientReceiveUnixMs: 1022,
    clientElapsedMs: 22,
    clockId: 'publisher-a',
  });
  assert.equal(sample.offsetMs, 45);
  assert.equal(sample.rttMs, 20);
  assert.equal(sample.serverProcessingMs, 2);
});

test('selects the minimum RTT sample from one clock', () => {
  const estimate = selectClockEstimate([
    { clockId: 'publisher-a', offsetMs: -191, rttMs: 12 },
    { clockId: 'publisher-a', offsetMs: -200, rttMs: 3 },
    { clockId: 'publisher-a', offsetMs: -198, rttMs: 5 },
  ], 1234);
  assert.equal(estimate.clockId, 'publisher-a');
  assert.equal(estimate.offsetMs, -200);
  assert.equal(estimate.rttMs, 3);
  assert.equal(estimate.sampleCount, 3);
  assert.equal(estimate.measuredAtUnixMs, 1234);
  assert.ok(estimate.uncertaintyMs >= 1.5);
});

test('rejects samples mixed across publisher clocks', () => {
  assert.throws(
    () =>
      selectClockEstimate([
        { clockId: 'publisher-a', offsetMs: 1, rttMs: 2 },
        { clockId: 'publisher-b', offsetMs: 1, rttMs: 3 },
      ]),
    /multiple clock IDs/,
  );
});

test('reference HTTP server and browser client interoperate', async (context) => {
  const handler = createClockSyncHandler({ clockId: 'publisher-a' });
  const server = createServer((request, response) => handler(request, response));
  server.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  context.after(() => new Promise((resolve) => server.close(resolve)));

  const address = server.address();
  const endpoint = `http://127.0.0.1:${address.port}/api/clock-sync`;
  const synchronizer = new ClockSynchronizer(endpoint, {
    expectedClockId: 'publisher-a',
    sampleCount: 3,
    sampleGapMs: 0,
  });
  const estimate = await synchronizer.synchronize();

  assert.equal(estimate.protocol, CLOCK_SYNC_PROTOCOL);
  assert.equal(estimate.clockId, 'publisher-a');
  assert.equal(estimate.sampleCount, 3);
  assert.ok(estimate.rttMs >= 0);
  assert.ok(Number.isFinite(synchronizer.correctedUnixMs()));
});

test('client rejects a valid endpoint belonging to another publisher', async (context) => {
  const handler = createClockSyncHandler({ clockId: 'publisher-b' });
  const server = createServer((request, response) => handler(request, response));
  server.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  context.after(() => new Promise((resolve) => server.close(resolve)));

  const address = server.address();
  const synchronizer = new ClockSynchronizer(
    `http://127.0.0.1:${address.port}/api/clock-sync`,
    {
      expectedClockId: 'publisher-a',
      sampleCount: 1,
      sampleGapMs: 0,
    },
  );
  await assert.rejects(() => synchronizer.synchronize(), /clockId mismatch/);
});

test('payload adapter can map a custom clock service to the canonical protocol', async () => {
  const synchronizer = new ClockSynchronizer('https://publisher.example/api/clock-sync', {
    expectedClockId: 'publisher-a',
    sampleCount: 1,
    sampleGapMs: 0,
    fetchImpl: async (url) => {
      const requestId = new URL(url).searchParams.get('requestId');
      return {
        ok: true,
        status: 200,
        json: async () => ({
          ok: true,
          request_id: requestId,
          server_receive_ms: Date.now(),
          server_transmit_ms: Date.now(),
        }),
      };
    },
    payloadAdapter: (payload) => ({
      ok: payload.ok,
      protocol: CLOCK_SYNC_PROTOCOL,
      clockId: 'publisher-a',
      requestId: payload.request_id,
      serverReceiveUnixMs: payload.server_receive_ms,
      serverSendUnixMs: payload.server_transmit_ms,
    }),
  });

  const estimate = await synchronizer.synchronize();
  assert.equal(estimate.clockId, 'publisher-a');
  assert.equal(estimate.sampleCount, 1);
});
