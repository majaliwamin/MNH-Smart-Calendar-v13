# WhatsApp bridge (WAHA) — setup runbook

This stands up WAHA on your always-on server and connects it to the MNH app.
Do this on the **VPS/Asterisk host**, not on a laptop.

Total time: ~15 minutes. You need:

- SSH access to the VPS (root or sudo).
- The phone with the sender SIM: **+26599130362**.
- A Cloudflare account with a domain (for the HTTPS tunnel), or another way to
  give the bridge an HTTPS URL that Render can reach.
- Access to the Render dashboard for the `mnh-calendar` service.

---

## 1. Install Docker (VPS, once)

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
docker --version
```

## 2. Copy this folder to the VPS and start WAHA

From your computer (adjust user@host):

```bash
scp -r deploy/waha user@your-vps:/opt/mnh-waha
```

On the VPS:

```bash
cd /opt/mnh-waha
cp .env.example .env
nano .env                 # set WAHA_API_KEY and WAHA_DASHBOARD_PASSWORD
docker compose up -d
docker compose logs -f waha
```

If you left `WAHA_API_KEY` blank, WAHA generates one on startup and prints it in
the logs — read it there and use it as `MNH_WA_BRIDGE_TOKEN` later.

Sanity check (should return `[]`, not 401):

```bash
curl -H "X-Api-Key: $WAHA_API_KEY" http://127.0.0.1:3000/api/sessions
```

## 3. Link the sender phone (physical step)

1. Open the dashboard in a browser through an SSH tunnel:
   ```bash
   ssh -L 3000:127.0.0.1:3000 user@your-vps
   ```
   then open <http://localhost:3000/dashboard> and log in with the dashboard
   username/password from `.env`.
2. Start (or create) the session named **`default`**.
3. Scan the QR code with WhatsApp on **+26599130362**:
   *WhatsApp → Settings → Linked devices → Link a device*.
4. Wait for the session to show **WORKING**.

> The account must be a **member** of any group you want to message.

## 4. Expose it to Render over HTTPS (Cloudflare Tunnel)

On the VPS:

```bash
# install cloudflared (Debian/Ubuntu)
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install -y cloudflared

cloudflared tunnel login
cloudflared tunnel create mnh-wa
cloudflared tunnel route dns mnh-wa wa.your-domain.example
```

`~/.cloudflared/config.yml`:

```yaml
tunnel: mnh-wa
credentials-file: /root/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: wa.your-domain.example
    service: http://localhost:3000
  - service: http_status:404
```

```bash
sudo cloudflared service install     # or: cloudflared tunnel run mnh-wa
```

The API key still protects the endpoint, so a public hostname is safe.

## 5. Set the environment variables in Render

Render dashboard → **mnh-calendar** → *Environment* → add:

| Variable | Value |
| --- | --- |
| `MNH_WA_BRIDGE_URL` | `https://wa.your-domain.example` |
| `MNH_WA_BRIDGE_TOKEN` | the `WAHA_API_KEY` value |
| `MNH_WA_BRIDGE_STYLE` | `waha` |
| `MNH_WA_BRIDGE_SESSION` | `default` |
| `MNH_WA_SENDER_NUMBER` | `26599130362` |
| `MNH_WA_PROFILE_NAME` | `Maternal & Neonatal Health Smart Time Table` |
| `MNH_AI_API_KEY` | your OpenAI-compatible key (for AI drafting) |
| `MNH_AI_TRIGGER_ENABLED` | `0` for now |

Save and wait for the service to restart.

## 6. Verify

```bash
curl -s https://mnh-smart-calendar-v13.onrender.com/api/comm/status
```

`aiTrigger.bridge.configured` must be `true` with an empty `missing` list.
Then in the app: **Communications → System status → Set WhatsApp display name
to the app name**, then **Send sample reminder** to `+265881988156`.

## 7. Groups

- Add a contact with **type = WhatsApp group** and paste the group id
  (`1203630…@g.us`) — find it with
  `curl -H "X-Api-Key: $WAHA_API_KEY" http://127.0.0.1:3000/api/default/groups`.
- Or paste the group id into the reminder recipients list.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `missing: ["MNH_WA_BRIDGE_URL"]` | Render env var not set / service not restarted |
| HTTP 401 from the bridge | `MNH_WA_BRIDGE_TOKEN` ≠ `WAHA_API_KEY` |
| Connection refused / timeout | Tunnel down, or `MNH_WA_BRIDGE_URL` wrong |
| Session `FAILED` / logged out | Re-scan the QR with +26599130362 |
| Message not delivered | Sender account not a member of the group |
