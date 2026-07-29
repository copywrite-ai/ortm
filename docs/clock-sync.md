# ORTM clock synchronization reference

## Scope

ORTM v0 stores the Publisher wall-clock timestamp in video pixels. Accurate
frame-age calculation requires the Viewer to know the difference between its
clock and the clock that generated that timestamp.

The clock-sync reference implementation uses the standard four timestamps:

```text
t1  Viewer sends request
t2  Publisher-side service receives request
t3  Publisher-side service sends response
t4  Viewer receives response

offset = ((t2 - t1) + (t3 - t4)) / 2
rtt    = (t4 - t1) - (t3 - t2)
```

`offset` is Publisher clock minus Viewer clock. A corrected Viewer timestamp is:

```text
corrected_now_ms = viewer_now_ms + offset
```

This is an application-level estimate. It does not change either operating
system clock.

## Source binding

The clock endpoint MUST use the same wall clock as the process or host that
writes `timestamp_ms` into the marker.

Do not infer the endpoint from the HTML page origin. The page can be hosted by a
different machine than the Publisher. Treat the media and clock configuration as
one source descriptor:

```js
const source = {
  whepUrl: 'https://publisher-a.example/fish_front/whep',
  clockSyncUrl: 'https://publisher-a.example/api/clock-sync',
  clockId: 'publisher-a',
};
```

For a multi-source Viewer, keep one clock estimate per source. Never share a
global estimate across Publishers.

`clockId` detects configuration mistakes; it does not prove that two services
share a physical clock. Deploy the clock endpoint on the Publisher host, or on a
host whose clock is independently synchronized with it, and record that method.

### Three-host deployments

The page host is not necessarily the Publisher or the Viewer:

```text
Publisher host  writes ORTM and serves media + clock-sync
Page host       serves HTML/JavaScript only
Viewer device   runs the browser and records t1/t4
```

Clock synchronization MUST run between the Viewer device and the Publisher
clock. The page host clock does not participate merely because it served the
HTML.

### Endpoint derivation

A Viewer MAY derive the default clock endpoint from the WHEP URL:

```js
const whep = new URL(source.whepUrl);
const clockSyncUrl = new URL('/api/clock-sync', whep.origin).toString();
```

This preserves the complete media origin, including an explicit port:

```text
https://publisher.example/fish/whep
-> https://publisher.example/api/clock-sync        (port 443)

https://publisher.example:8889/fish/whep
-> https://publisher.example:8889/api/clock-sync   (port 8889)
```

Automatic derivation is only a routing convention. It works when the public
origin routes both WHEP and `/api/clock-sync`. If the clock service uses another
origin or port, the source descriptor MUST provide an explicit `clockSyncUrl`.
Never derive from the page URL.

## HTTP protocol

Request:

```http
GET /api/clock-sync?requestId=viewer-generated-token
Cache-Control: no-store
```

Successful response:

```json
{
  "ok": true,
  "protocol": "ortm-clock-sync/1",
  "clockId": "publisher-a",
  "requestId": "viewer-generated-token",
  "serverReceiveUnixMs": 1785230000000,
  "serverSendUnixMs": 1785230000001,
  "serverProcessingMs": 0.12
}
```

Required behavior:

- accept `GET` and `OPTIONS`;
- return `Cache-Control: no-store`;
- echo `requestId`;
- expose CORS headers when the Viewer is on another origin;
- sample receive/send wall-clock timestamps as close to request handling and
  response transmission as practical.

The current protocol uses Unix milliseconds as JavaScript numbers. HTTPS is
recommended because an active intermediary could otherwise alter responses.

Field names and units are part of the protocol:

- `serverReceiveUnixMs` and `serverSendUnixMs` are finite JSON numbers;
- both values are Unix epoch milliseconds, not seconds, nanoseconds, ISO text,
  or monotonic process time;
- `requestId` uses the same spelling and value as the query parameter;
- `clockId` is stable for the Publisher clock domain.

Implementations SHOULD reject missing or non-finite timestamps. Silently
interpreting a differently named field as zero produces plausible-looking but
invalid G2G values.

### Adapting an existing clock service

Existing services may use names such as `server_receive_ms`,
`server_transmit_ms`, or `request_id`. Keep the ORTM protocol canonical and map
the external payload explicitly:

```js
import {
  CLOCK_SYNC_PROTOCOL,
  ClockSynchronizer,
} from 'open-raster-timing-marker/clock-sync';

const clock = new ClockSynchronizer(source.clockSyncUrl, {
  expectedClockId: source.clockId,
  payloadAdapter: (payload) => ({
    ok: payload.ok,
    protocol: CLOCK_SYNC_PROTOCOL,
    clockId: source.clockId,
    requestId: payload.requestId ?? payload.request_id,
    serverReceiveUnixMs:
      payload.serverReceiveUnixMs ?? payload.server_receive_ms,
    serverSendUnixMs:
      payload.serverSendUnixMs ?? payload.server_transmit_ms,
  }),
});
```

An adapter is a compatibility boundary, not proof of clock identity. The
configured `clockId` still has to describe the host clock that writes ORTM.

## Standalone server

Node.js 20 or newer:

```bash
CLOCK_ID=publisher-a HOST=0.0.0.0 PORT=9011 \
  node examples/clock-sync-server.mjs
```

Verify it:

```bash
curl 'http://127.0.0.1:9011/api/clock-sync?requestId=test'
```

Put the endpoint behind the same authenticated or private network boundary as
the media service. If WHEP occupies the public origin, route
`/api/clock-sync` to this server through the existing reverse proxy.

### Docker

Build from the repository root:

```bash
docker build -f integrations/clock-sync/Dockerfile -t ortm-clock-sync .
docker run --rm \
  -e CLOCK_ID=publisher-a \
  -p 9011:9011 \
  ortm-clock-sync
```

The container does not include or configure a reverse proxy. Route the public
`/api/clock-sync` path to port `9011`, while leaving the WHEP path routed to the
media server.

### HTTPS and reverse proxies

An HTTPS Viewer page cannot fetch a plain HTTP clock endpoint because browsers
block mixed content. A common deployment is:

```text
https://publisher.example:8889/fish_front/whep
    -> Media server

https://publisher.example:8889/api/clock-sync
    -> reverse proxy -> http://127.0.0.1:9011/api/clock-sync
```

The proxy SHOULD:

- preserve the query string and `requestId`;
- disable response caching and proxy buffering;
- avoid redirects, especially a `/api/clock-sync` to `/api/clock-sync/`
  redirect;
- expose the required CORS headers;
- route the path to the clock service, not to a media path handler.

Redirect and proxy time are included in t1-to-t4 RTT. The offset can remain
usable, but uncertainty increases and asymmetric routes can bias it.

## Embedding in an existing Node server

```js
import { createServer } from 'node:http';
import { createClockSyncHandler } from 'open-raster-timing-marker/clock-sync/server';

const clockSync = createClockSyncHandler({ clockId: 'publisher-a' });

createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/api/clock-sync') {
    clockSync(request, response);
    return;
  }
  response.writeHead(404).end();
}).listen(9011);
```

## Viewer integration

```js
import { ClockSynchronizer } from 'open-raster-timing-marker/clock-sync';

const clock = new ClockSynchronizer(source.clockSyncUrl, {
  expectedClockId: source.clockId,
  sampleCount: 12,
  sampleGapMs: 25,
});

const estimate = await clock.synchronize();
const correctedNowMs = clock.correctedUnixMs();
const decoded = decodeRaster(imageData, {
  nowMs: correctedNowMs,
});
```

Refresh the estimate periodically and after a network transition. Thirty
seconds is a reasonable starting interval for an interactive Viewer.

Record at least:

- `clockId`;
- offset;
- selected RTT;
- uncertainty;
- sample count;
- measurement time;
- synchronization failures.

Do not label a value simply as G2G when synchronization is unavailable or its
uncertainty exceeds the experiment's declared limit. Report it as uncorrected
frame age or suppress it.

## Validation checklist

Verify the public URL from the Viewer network, not only inside the Publisher:

```bash
curl -i \
  'https://publisher.example/api/clock-sync?requestId=clock-check'
```

Confirm:

1. HTTP status is `200`, with no redirect.
2. `requestId` is echoed as `clock-check`.
3. receive/send timestamps are finite Unix milliseconds near the current time.
4. `clockId` matches the configured Publisher.
5. repeated samples report plausible RTT and bounded uncertainty.
6. the Viewer refreshes synchronization after network changes and periodically
   during a long session.

Docker containers normally share the host wall clock. Still verify that the
marker writer and clock endpoint report the same time domain.

## Failure diagnosis

| Symptom | Likely cause |
| --- | --- |
| `serverReceiveUnixMs must be finite` | Missing field, custom field spelling, non-number value, or wrong endpoint |
| `unsupported clock protocol` | Endpoint is not ORTM clock-sync v1 or needs an explicit adapter |
| `clockId mismatch` | Media and clock endpoint belong to different Publishers |
| Browser mixed-content error | HTTPS page attempted to use an HTTP clock URL |
| CORS failure | Public clock endpoint omitted cross-origin headers |
| High RTT or uncertainty | Relay/proxy detour, redirect, congestion, or asymmetric path |
| `latency-out-of-range` after valid CRC | Wrong clock domain, stale frame, bad units, or excessive clock error |
| `structure-mismatch` before CRC | Marker geometry/ROI/rendering problem; clock-sync is not involved |

## Network experiments

Clock probes SHOULD use an out-of-band management path when evaluating
controlled one-way media delay, loss, jitter, or bandwidth. Applying the same
asymmetric impairment to the clock probes can bias the offset estimate.

Clock correction removes wall-clock offset. It does not remove network latency
from the measured video path and it does not produce optical glass-to-glass
ground truth.
