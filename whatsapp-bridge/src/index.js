import http from 'node:http';
import { timingSafeEqual } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import makeWASocket, {
  Browsers,
  DisconnectReason,
  useMultiFileAuthState,
} from '@whiskeysockets/baileys';
import pino from 'pino';
import qrcode from 'qrcode-terminal';

const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || '127.0.0.1';
const TOKEN = (process.env.MNH_WA_BRIDGE_TOKEN || '').trim();
const AUTH_DIR = path.resolve(process.env.BAILEYS_AUTH_DIR || './data/auth');
const MIN_SEND_INTERVAL_MS = Math.max(1000, Number(process.env.MIN_SEND_INTERVAL_MS || 2500));
const MAX_BODY_BYTES = 32 * 1024;
const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

if (!TOKEN || TOKEN.length < 32) {
  logger.fatal('MNH_WA_BRIDGE_TOKEN must be set to a random secret of at least 32 characters.');
  process.exit(1);
}

let socket;
let connected = false;
let reconnectTimer;
let reconnectDelay = 2000;
let sendChain = Promise.resolve();
let lastSendAt = 0;
let stopping = false;

function authorised(req) {
  const header = String(req.headers.authorization || '');
  const supplied = header.startsWith('Bearer ') ? header.slice(7) : '';
  const a = Buffer.from(supplied);
  const b = Buffer.from(TOKEN);
  return a.length === b.length && timingSafeEqual(a, b);
}

function json(res, status, body) {
  const data = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': data.length,
    'cache-control': 'no-store',
  });
  res.end(data);
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new Error('Request body too large.');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

async function connectWhatsApp() {
  if (stopping) return;
  await mkdir(AUTH_DIR, { recursive: true, mode: 0o700 });
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const sock = makeWASocket({
    auth: state,
    browser: Browsers.ubuntu('Chrome'),
    logger: logger.child({ component: 'baileys' }),
    markOnlineOnConnect: false,
    syncFullHistory: false,
    shouldSyncHistoryMessage: () => false,
  });
  socket = sock;

  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      logger.info('Scan this QR code with WhatsApp → Linked devices → Link a device:');
      qrcode.generate(qr, { small: true });
    }
    if (connection === 'open') {
      connected = true;
      reconnectDelay = 2000;
      logger.info('WhatsApp linked and connected.');
    } else if (connection === 'close') {
      connected = false;
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      if (statusCode === DisconnectReason.loggedOut) {
        logger.error('WhatsApp session logged out. Remove the auth directory only if you intend to pair again.');
        return;
      }
      if (!stopping && !reconnectTimer) {
        const wait = reconnectDelay;
        reconnectDelay = Math.min(reconnectDelay * 2, 60000);
        logger.warn({ statusCode, retryInMs: wait }, 'WhatsApp connection closed; reconnecting.');
        reconnectTimer = setTimeout(() => {
          reconnectTimer = undefined;
          connectWhatsApp().catch((error) => logger.error({ err: error }, 'Reconnect failed.'));
        }, wait);
      }
    }
  });
}

function enqueueSend(phone, message) {
  const task = sendChain.then(async () => {
    if (!connected || !socket) throw Object.assign(new Error('WhatsApp is not connected.'), { statusCode: 503 });
    const wait = Math.max(0, MIN_SEND_INTERVAL_MS - (Date.now() - lastSendAt));
    if (wait) await new Promise((resolve) => setTimeout(resolve, wait));
    if (!connected || !socket) throw Object.assign(new Error('WhatsApp disconnected before sending.'), { statusCode: 503 });
    const jid = `${phone}@s.whatsapp.net`;
    const result = await socket.sendMessage(jid, { text: message });
    lastSendAt = Date.now();
    return { ok: true, messageId: result?.key?.id || null, to: phone };
  });
  sendChain = task.catch(() => {});
  return task;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
  if (req.method === 'GET' && url.pathname === '/health') {
    return json(res, 200, { ok: true, service: 'mnh-baileys-bridge' });
  }
  if (!authorised(req)) return json(res, 401, { ok: false, error: 'Unauthorized.' });
  if (req.method === 'GET' && url.pathname === '/status') {
    return json(res, 200, { ok: true, connected, provider: 'Baileys' });
  }
  if (req.method === 'POST' && url.pathname === '/send') {
    if (!String(req.headers['content-type'] || '').includes('application/json')) {
      return json(res, 415, { ok: false, error: 'Content-Type must be application/json.' });
    }
    try {
      const body = await readJson(req);
      const phone = String(body.phone || '').replace(/^\+/, '');
      const message = String(body.message || '').trim();
      if (!/^\d{8,15}$/.test(phone)) return json(res, 400, { ok: false, error: 'phone must be an international number in digits.' });
      if (!message || message.length > 4096) return json(res, 400, { ok: false, error: 'message must contain 1–4096 characters.' });
      const result = await enqueueSend(phone, message);
      return json(res, 200, result);
    } catch (error) {
      const status = error.statusCode || (error instanceof SyntaxError ? 400 : 500);
      logger.error({ err: error }, 'Message send failed.');
      return json(res, status, { ok: false, error: status === 500 ? 'Message send failed.' : error.message });
    }
  }
  return json(res, 404, { ok: false, error: 'Not found.' });
});

async function shutdown(signal) {
  if (stopping) return;
  stopping = true;
  logger.info({ signal }, 'Shutting down.');
  clearTimeout(reconnectTimer);
  connected = false;
  try { socket?.end(undefined); } catch {}
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 10000).unref();
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

await connectWhatsApp();
server.listen(PORT, HOST, () => logger.info({ host: HOST, port: PORT }, 'Bridge HTTP server listening.'));
