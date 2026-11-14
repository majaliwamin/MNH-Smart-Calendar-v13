# MNH Baileys WhatsApp bridge (VPS)

This is a small, separately hosted Node.js transport service. The existing FastAPI app calls it using the existing generic bridge contract:

- `POST /send` with `{"phone":"265...","message":"..."}`
- `Authorization: Bearer <MNH_WA_BRIDGE_TOKEN>`

It does not expose QR codes or pairing controls over HTTP. Pairing QR codes are printed only to the VPS service log. Authentication files are stored outside the repository in a persistent directory.

## Important

Baileys is an unofficial WhatsApp Web protocol client, not a WhatsApp-approved API. WhatsApp can change the protocol or restrict the linked account. The Baileys maintainers discourage bulk and automated messaging. Use a dedicated number, message only people who have explicitly agreed to receive academic notifications, respect opt-outs, and keep volumes low. This bridge does not make automated messaging officially authorised.

## Requirements

- Linux VPS with systemd
- Node.js 20.10+ (use Node 22 LTS)
- Outbound internet access over HTTPS/WebSocket
- Persistent disk for `BAILEYS_AUTH_DIR`
- A domain/reverse proxy is not required if FastAPI can reach this service over a private network or VPN

## Install

From the repository root:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
# Install Node.js 22 LTS using your preferred trusted NodeSource/Node.js repository.
node --version
npm --version

sudo useradd --system --home /opt/mnh-baileys --shell /usr/sbin/nologin mnhwa || true
sudo mkdir -p /opt/mnh-baileys /var/lib/mnh-bailey s/auth
sudo chown -R mnhwa:mnhwa /opt/mnh-baileys /var/lib/mnh-baileys
```

Copy this directory to `/opt/mnh-baileys`, then:

```bash
cd /opt/mnh-baileys
npm ci --omit=dev
sudo install -d -o mnhwa -g mnhwa -m 0700 /var/lib/mnh-baileys/auth
sudo install -o root -g mnhwa -m 0640 .env.example /etc/mnh-baileys.env
sudo nano /etc/mnh-baileys.env
```

Set `MNH_WA_BRIDGE_TOKEN` to a unique random secret. Keep `HOST=127.0.0.1` unless a private network interface is explicitly required. Do not expose port 3000 directly to the public internet.

## systemd

Create `/etc/systemd/system/mnh-baileys.service`:

```ini
[Unit]
Description=MNH Baileys WhatsApp bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mnhwa
Group=mnhwa
WorkingDirectory=/opt/mnh-baileys
EnvironmentFile=/etc/mnh-baileys.env
ExecStart=/usr/bin/node /opt/mnh-baileys/src/index.js
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/mnh-baileys

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mnh-baileys
sudo journalctl -u mnh-baileys -f
```

The first start prints a QR code in the journal. On the dedicated WhatsApp phone, open **WhatsApp → Linked devices → Link a device**, then scan the QR code shown in the VPS logs. Do not share the QR code or auth directory. Once paired, the session is persisted and reconnects after restart.

## FastAPI configuration

Set these on the FastAPI host (Render environment variables), not in Git:

```env
MNH_WA_BRIDGE_URL=http://<private-vps-address>:3000
MNH_WA_BRIDGE_STYLE=generic
MNH_WA_BRIDGE_TOKEN=<same-random-secret>
```

The FastAPI host must have a private route/VPN to the VPS. If it cannot, put an authenticated HTTPS reverse proxy in front of the bridge; never expose the unauthenticated send endpoint to the public internet. Keep the bridge port bound to localhost when using a local reverse proxy.

## Verify

```bash
curl http://127.0.0.1:3000/health
curl -H "Authorization: Bearer $MNH_WA_BRIDGE_TOKEN" http://127.0.0.1:3000/status
```

The status endpoint should report `connected: true`. Test sending only to the dedicated account owner's own number first.

## Operations

- Check logs: `sudo journalctl -u mnh-baileys -n 100 --no-pager`
- Restart: `sudo systemctl restart mnh-baileys`
- Stop: `sudo systemctl stop mnh-baileys`
- Back up `/var/lib/mnh-baileys/auth` securely; it grants access to the linked WhatsApp session.
- To pair a different number, stop the service, back up then remove the auth directory, and start again.
- Do not commit `.env`, auth files, QR codes, or logs containing private identifiers.

The service serializes sends and enforces a small inter-message delay. It does not guarantee delivery/read receipts; HTTP success means Baileys accepted the send request, not that the recipient read it.
