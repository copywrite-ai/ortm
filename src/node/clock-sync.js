import { CLOCK_SYNC_PROTOCOL } from '../js/clock-sync.js';

function setResponseHeaders(response, allowOrigin) {
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
  response.setHeader('Pragma', 'no-cache');
  response.setHeader('Access-Control-Allow-Origin', allowOrigin);
  response.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Accept, Cache-Control');
  response.setHeader('Access-Control-Allow-Private-Network', 'true');
}

function sendJson(response, status, body) {
  response.writeHead(status);
  response.end(JSON.stringify(body));
}

export function createClockSyncHandler({
  clockId,
  allowOrigin = '*',
  now = Date.now,
  monotonicNow = () => process.hrtime.bigint(),
} = {}) {
  if (typeof clockId !== 'string' || !clockId.trim()) {
    throw new TypeError('clockId is required');
  }
  const normalizedClockId = clockId.trim();

  return function handleClockSync(request, response) {
    setResponseHeaders(response, allowOrigin);
    if (request.method === 'OPTIONS') {
      response.writeHead(204);
      response.end();
      return;
    }
    if (request.method !== 'GET') {
      response.setHeader('Allow', 'GET, OPTIONS');
      sendJson(response, 405, { ok: false, error: 'method-not-allowed' });
      return;
    }

    const receiveUnixMs = now();
    const receiveMonotonicNs = monotonicNow();
    const requestUrl = new URL(request.url || '/', 'http://localhost');
    const sendUnixMs = now();
    const sendMonotonicNs = monotonicNow();
    sendJson(response, 200, {
      ok: true,
      protocol: CLOCK_SYNC_PROTOCOL,
      clockId: normalizedClockId,
      requestId: requestUrl.searchParams.get('requestId'),
      serverReceiveUnixMs: receiveUnixMs,
      serverSendUnixMs: sendUnixMs,
      serverProcessingMs: Number(sendMonotonicNs - receiveMonotonicNs) / 1e6,
    });
  };
}
