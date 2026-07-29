import { createServer } from 'node:http';

import { createClockSyncHandler } from '../src/node/clock-sync.js';

const host = process.env.HOST || '0.0.0.0';
const port = Number(process.env.PORT || 9011);
const clockId = process.env.CLOCK_ID;

if (!clockId) {
  console.error('CLOCK_ID is required, for example CLOCK_ID=camera-01');
  process.exit(1);
}

const handleClockSync = createClockSyncHandler({ clockId });
const server = createServer((request, response) => {
  const requestUrl = new URL(request.url || '/', 'http://localhost');
  if (requestUrl.pathname !== '/api/clock-sync') {
    response.writeHead(404, { 'Content-Type': 'application/json; charset=utf-8' });
    response.end(JSON.stringify({ ok: false, error: 'not-found' }));
    return;
  }
  handleClockSync(request, response);
});

server.listen(port, host, () => {
  console.log(`ORTM clock sync listening on http://${host}:${port}/api/clock-sync clockId=${clockId}`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
