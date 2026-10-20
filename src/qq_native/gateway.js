'use strict';
const http = require('node:http');

// Deliberately no arbitrary native-method proxy, profile reader, or plugin endpoint.
function gateway(driver, config) {
  const clients = new Set();
  let heartbeat;
  const server = http.createServer(async (req, res) => {
    const allowedHost = `127.0.0.1:${server.address().port}`;
    if (req.headers.host !== allowedHost || req.headers.origin || req.headers['x-qq-chatbot'] !== '1') {
      res.writeHead(403); res.end(); return;
    }
    res.setHeader('Cache-Control', 'no-store');
    if (req.method === 'GET' && req.url === '/events') {
      if (clients.size >= 2) {res.writeHead(429); res.end(); return;}
      res.writeHead(200, {'Content-Type': 'application/x-ndjson'});
      clients.add(res);
      res.write(JSON.stringify({post_type: 'meta_event', meta_event_type: 'heartbeat', status: {online: driver.online && !!driver.service}}) + '\n');
      res.on('close', () => clients.delete(res)); return;
    }
    const actions = new Set(['get_status', 'get_login_info', 'send_private_msg']);
    const action = req.url?.slice(1);
    if (req.method !== 'POST' || !actions.has(action)) {res.writeHead(404); res.end(); return;}
    if (req.headers['content-type']?.split(';')[0] !== 'application/json') {res.writeHead(415); res.end(); return;}
    const chunks = []; let size = 0;
    try {
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 65536) {res.writeHead(413); res.end(); return;}
        chunks.push(chunk);
      }
      const params = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if (!params || typeof params !== 'object' || Array.isArray(params)) throw new Error('invalid_request');
      const result = await Promise.race([driver.action(action, params), new Promise((_, reject) => { const timer = setTimeout(() => reject(new Error('native_timeout_do_not_retry')), 8000); timer.unref(); })]);
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({status: 'ok', retcode: 0, data: result}));
    } catch (err) {
      // Native errors can contain opaque account data. Return only our fixed codes.
      const code = /^(not_logged_in|not_ready|recipient_not_allowed|text_only|invalid_text|owner_must_message_first|rate_limited|native_send_failed|native_timeout_do_not_retry|unsupported_action|invalid_request)$/.test(err?.message) ? err.message : 'native_error';
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({status: 'failed', retcode: 1, message: code}));
    }
  });
  server.requestTimeout = 10000;
  server.headersTimeout = 5000;
  server.maxConnections = 8;
  server.on('close', () => clearInterval(heartbeat));
  function emit(event) {
    const line = JSON.stringify(event) + '\n';
    if (Buffer.byteLength(line) > 262144) return;
    for (const client of clients) {
      if (client.writableLength > 1048576) {client.destroy(); clients.delete(client); continue;}
      client.write(line);
    }
  }
  function listen() {
    return new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(config.port, '127.0.0.1', () => {
        heartbeat = setInterval(() => emit({post_type: 'meta_event', meta_event_type: 'heartbeat', status: {online: driver.online && !!driver.service}}), 15000);
        heartbeat.unref(); resolve(server.address());
      });
    });
  }
  return {server, listen, emit, close: () => {for (const client of clients) client.destroy(); return new Promise(resolve => server.close(resolve));}};
}
module.exports = {gateway};
