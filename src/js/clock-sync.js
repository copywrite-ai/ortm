const DEFAULT_SAMPLE_COUNT = 12;
const DEFAULT_SAMPLE_GAP_MS = 25;
const DEFAULT_TIMEOUT_MS = 2000;

export const CLOCK_SYNC_PROTOCOL = 'ortm-clock-sync/1';

function finiteNumber(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`${name} must be finite`);
  return number;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function calculateClockSample({
  clientSendUnixMs,
  clientReceiveUnixMs,
  clientElapsedMs,
  serverReceiveUnixMs,
  serverSendUnixMs,
  clockId,
}) {
  const t1 = finiteNumber(clientSendUnixMs, 'clientSendUnixMs');
  const t2 = finiteNumber(serverReceiveUnixMs, 'serverReceiveUnixMs');
  const t3 = finiteNumber(serverSendUnixMs, 'serverSendUnixMs');
  const t4 = finiteNumber(clientReceiveUnixMs, 'clientReceiveUnixMs');
  const serverProcessingMs = Math.max(0, t3 - t2);
  const wallElapsedMs = Math.max(0, t4 - t1);
  const measuredElapsedMs = Number.isFinite(Number(clientElapsedMs))
    ? Math.max(0, Number(clientElapsedMs))
    : wallElapsedMs;

  return {
    clockId: String(clockId || ''),
    offsetMs: ((t2 - t1) + (t3 - t4)) / 2,
    rttMs: Math.max(0, measuredElapsedMs - serverProcessingMs),
    serverProcessingMs,
    clientSendUnixMs: t1,
    clientReceiveUnixMs: t4,
    serverReceiveUnixMs: t2,
    serverSendUnixMs: t3,
  };
}

export function selectClockEstimate(samples, nowUnixMs = Date.now()) {
  const valid = (samples || [])
    .filter(
      (sample) =>
        Number.isFinite(sample?.offsetMs) &&
        Number.isFinite(sample?.rttMs) &&
        typeof sample?.clockId === 'string' &&
        sample.clockId.length > 0,
    )
    .sort((left, right) => left.rttMs - right.rttMs);
  if (!valid.length) throw new Error('no valid clock samples');

  const clockIds = new Set(valid.map((sample) => sample.clockId));
  if (clockIds.size !== 1) throw new Error('clock samples came from multiple clock IDs');

  const best = valid[0];
  const lowDelay = valid.slice(0, Math.min(5, valid.length));
  const lowOffsets = lowDelay.map((sample) => sample.offsetMs);
  const offsetSpreadMs = (Math.max(...lowOffsets) - Math.min(...lowOffsets)) / 2;
  return {
    ok: true,
    protocol: CLOCK_SYNC_PROTOCOL,
    clockId: best.clockId,
    offsetMs: best.offsetMs,
    rttMs: best.rttMs,
    uncertaintyMs: best.rttMs / 2 + offsetSpreadMs,
    offsetSpreadMs,
    sampleCount: valid.length,
    selectedSample: best,
    measuredAtUnixMs: finiteNumber(nowUnixMs, 'nowUnixMs'),
  };
}

export class ClockSynchronizer {
  constructor(endpoint, options = {}) {
    if (!endpoint) throw new TypeError('endpoint is required');
    this.endpoint = endpoint;
    this.expectedClockId = options.expectedClockId || null;
    this.sampleCount = options.sampleCount ?? DEFAULT_SAMPLE_COUNT;
    this.sampleGapMs = options.sampleGapMs ?? DEFAULT_SAMPLE_GAP_MS;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch?.bind(globalThis);
    this.payloadAdapter = options.payloadAdapter ?? ((payload) => payload);
    this.estimate = null;
    if (!this.fetchImpl) throw new Error('fetch is unavailable');
    if (typeof this.payloadAdapter !== 'function') {
      throw new TypeError('payloadAdapter must be a function');
    }
  }

  async sample(index = 0) {
    const url = new URL(this.endpoint, globalThis.location?.href || 'http://localhost/');
    const requestId = `${Date.now()}-${index}-${Math.random().toString(16).slice(2)}`;
    url.searchParams.set('requestId', requestId);
    url.searchParams.set('_', String(Date.now()));

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    const clientSendUnixMs = Date.now();
    const clientSendPerfMs = performance.now();
    try {
      const response = await this.fetchImpl(url, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'omit',
        signal: controller.signal,
      });
      const rawPayload = await response.json();
      const payload = await this.payloadAdapter(rawPayload, {
        endpoint: url.toString(),
        requestId,
        response,
      });
      const clientReceivePerfMs = performance.now();
      const clientReceiveUnixMs = Date.now();

      if (!response.ok || payload?.ok !== true) {
        throw new Error(`clock endpoint returned ${response.status}`);
      }
      if (payload.protocol !== CLOCK_SYNC_PROTOCOL) {
        throw new Error(`unsupported clock protocol: ${payload.protocol || 'missing'}`);
      }
      if (!payload.clockId) throw new Error('clock endpoint omitted clockId');
      if (payload.requestId !== requestId) throw new Error('clock endpoint requestId mismatch');
      if (this.expectedClockId && payload.clockId !== this.expectedClockId) {
        throw new Error(
          `clockId mismatch: expected ${this.expectedClockId}, received ${payload.clockId}`,
        );
      }

      return calculateClockSample({
        clientSendUnixMs,
        clientReceiveUnixMs,
        clientElapsedMs: clientReceivePerfMs - clientSendPerfMs,
        serverReceiveUnixMs: payload.serverReceiveUnixMs,
        serverSendUnixMs: payload.serverSendUnixMs,
        clockId: payload.clockId,
      });
    } finally {
      clearTimeout(timeout);
    }
  }

  async synchronize() {
    const samples = [];
    const errors = [];
    for (let index = 0; index < this.sampleCount; index += 1) {
      try {
        samples.push(await this.sample(index));
      } catch (error) {
        errors.push(error);
      }
      if (index + 1 < this.sampleCount && this.sampleGapMs > 0) {
        await sleep(this.sampleGapMs);
      }
    }
    if (!samples.length) {
      throw errors.at(-1) || new Error('clock synchronization failed');
    }
    this.estimate = selectClockEstimate(samples);
    return this.estimate;
  }

  correctedUnixMs(clientUnixMs = Date.now()) {
    if (!this.estimate?.ok) throw new Error('clock has not been synchronized');
    return finiteNumber(clientUnixMs, 'clientUnixMs') + this.estimate.offsetMs;
  }
}
