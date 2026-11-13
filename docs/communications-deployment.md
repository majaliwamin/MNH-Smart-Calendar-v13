# Communications Centre — Deployment Guide

WhatsApp Click-to-Chat + AI drafting + Asterisk ARI voice calls.

Channels are independent: a failure in one never disables the others.
Nothing sends a WhatsApp message or places a call automatically. All
communications require a signed-in editor and pass server-side safeguards
(consent → do-not-contact → calling hours → emergency stop).

---

## 1. Environment variables

See `.env.example` for the full list with placeholders. Summary:

| Variable | Purpose | Required for |
| --- | --- | --- |
| `MNH_WA_BRIDGE_URL` | WhatsApp bridge base URL on the Asterisk server (e.g. `http://127.0.0.1:3000`) | all WhatsApp sending |
| `MNH_WA_BRIDGE_TOKEN` | Bearer token for the bridge, if it has auth | bridge auth |
| `MNH_WA_BRIDGE_STYLE` | `waha` (default) or `generic` payload shape | bridge compatibility |
| `MNH_WA_BRIDGE_SESSION` | WAHA session name (default `default`) | WAHA bridges |
| `MNH_AI_API_KEY` | AI drafting (OpenAI-compatible) | AI draft button |
| `MNH_AI_BASE_URL` | Provider base URL (default `https://api.openai.com/v1`) | alternative providers |
| `MNH_AI_MODEL` | Model name (default `gpt-4o-mini`) | alternative models |
| `MNH_AI_TRIGGER_ENABLED` | `1` = AI detects timetable changes and sends automatically (default off) | auto-trigger |
| `MNH_ARI_BASE_URL` | Asterisk ARI root, e.g. `http://10.0.0.5:8088/ari` | voice calls |
| `MNH_ARI_USER` / `MNH_ARI_PASSWORD` | ARI credentials from `ari.conf` | voice calls |
| `MNH_ARI_APP` | Stasis app name (default `mnh-calendar`) | voice calls |
| `MNH_ARI_ENDPOINT` | Dial pattern, default `Local/{number}@mnh-outbound` | voice calls |
| `MNH_CALL_WINDOW_START/END` | Allowed calling hours, Africa/Blantyre | voice calls |
| `MNH_WHATSAPP_TOKEN` / `MNH_WHATSAPP_PHONE_ID` | ~~Retired~~ — Meta Cloud API removed; see bridge variables above | — |

All `MNH_ARI_*` and `MNH_AI_*` values stay server-side. They are never sent to
the browser; the UI only receives booleans and missing-variable names.

---

## 2. Architecture

```
Browser / Flutter ── HTTPS ──> FastAPI (Render) ── SQLite
                                  │
                                  ├─ WhatsApp bridge (HTTP) → WAHA/gateway on the Asterisk VPS → WhatsApp
                                  ├─ AI drafts/triggers → OpenAI-compatible API (outbound HTTPS)
                                  └─ ARI (HTTP + poll) → Cloudflare Tunnel → Asterisk core
```

- **Render** hosts the app exactly as today (see `render.yaml`; new variables
  added with `sync: false` so they are set in the dashboard, never committed).
- **Asterisk + the WhatsApp bridge run on a separate VPS.** Render cannot host
  Asterisk: no SIP/RTP ingress, no UDP, no root. Do not try.
- **Meta's WhatsApp Cloud API is retired** from this app: every automatic send
  (AI triggers, reminders, tests) goes through the bridge on the VPS.
- **Cloudflare Tunnel** (`cloudflared`) connects Render → Asterisk without
  exposing ARI to the public internet. ARI speaks HTTP, which the Tunnel
  proxies fine; the SIP/RTP media itself never touches the Tunnel — it flows
  directly between the Asterisk VPS and the SIP trunk/carrier.

---

## 3. Asterisk server setup (VPS)

### 3.1 ari.conf

```ini
[general]
enabled = yes
pretty = yes
allowed_origins = ""

[mnh-calendar]
type = user
password = <strong-random-password>
```

### 3.2 http.conf

```ini
[general]
enabled = yes
bindaddr = 127.0.0.1     ; ARI listens ONLY on localhost; cloudflared connects locally
bindport = 8088
```

### 3.3 dialplan (extensions.conf) — outbound context

```ini
[mnh-outbound]
exten => _X!,1,NoOp(MNH calendar call to ${EXTEN})
 same => n,Dial(PJSIP/${EXTEN}@<your-trunk-name>,30)
 same => n,Hangup()
```

`MNH_ARI_ENDPOINT` (default `Local/{number}@mnh-outbound`) originates into
this context; the trunk carries the call to the PSTN. Replace
`<your-trunk-name>` with your SIP trunk's endpoint name and confirm outbound
calling permission with your carrier.

### 3.4 Verify before connecting the app

```bash
asterisk -rx "ari show apps"       # ARI enabled
asterisk -rx "ari show users"      # mnh-calendar user exists
# from the app host, through the tunnel (step 4):
curl -u mnh-calendar:<password> https://ari.your-domain.example/asterisk/info
```

Set `MNH_ARI_ENDPOINT` per your dialplan. Test with a phone number you own
before anything else. Recording is disabled in the app by default and needs
separate approval + consent before it is turned on.

---

## 4. Cloudflare Tunnel (Asterisk host)

1. Point a Cloudflare zone at your infrastructure (the domain's DNS on Cloudflare).
2. On the Asterisk VPS install cloudflared and create the tunnel:

```bash
cloudflared tunnel create mnh-ari
cloudflared tunnel route dns mnh-ari ari.your-domain.example
```

3. `~/.cloudflared/config.yml`:

```yaml
tunnel: mnh-ari
credentials-file: /etc/cloudflared/<tunnel-id>.json
ingress:
  - hostname: ari.your-domain.example
    service: http://localhost:8088
  - service: http_status:404
```

4. Run `cloudflared tunnel run mnh-ari` (or install as a service) and set on
   Render: `MNH_ARI_BASE_URL=https://ari.your-domain.example/ari`.

ARI credentials additionally travel inside the tunnel; the hostname resolves
only through Cloudflare, and the ARI port itself is bound to localhost —
nothing on the VPS exposes 8088 publicly.

Note: Cloudflare Tunnel proxies HTTP(S) well, but it is not involved in the
telephony media path (SIP/RTP between the VPS and the trunk). If the AI voice
pipeline is added later (ExternalMedia), its media transport must be validated
directly against Asterisk — do not assume the Tunnel carries RTP.

---

## 5. AI provider

Any OpenAI-compatible chat-completions endpoint works:

- OpenAI: `MNH_AI_BASE_URL=https://api.openai.com/v1`, e.g. `MNH_AI_MODEL=gpt-4o-mini`
- Self-hosted (e.g. an internal LLM gateway): point `MNH_AI_BASE_URL` at it.

The assistant drafts only. It cannot send WhatsApp messages, place calls, or
override consent — the code has no path for that.

---

## 6. Status checklist after deployment

1. `GET /api/comm/status` (signed in): WhatsApp, AI and Asterisk each report
   `configured: true` and no `missing` variables.
2. Add one test contact with consent, prepare a draft, open its wa.me link on
   a phone you own, send manually, mark it sent.
3. Schedule a job 2 minutes ahead; confirm it turns into a **draft** (not a
   sent message) and the responsible user is flagged to review.
4. Place one test voice call to a number you own during calling hours;
   confirm state transitions to answered/ended in the Voice calls card.
5. Turn the emergency stop on and confirm drafting, scheduling and calling all
   refuse; turn it off afterwards.

---

## 7. Security notes

- ARI is reachable only through the Cloudflare Tunnel from localhost — never
  expose port 8088 or Asterisk's AMI publicly.
- Secrets live in environment variables (Render dashboard / server env), never
  in git, the browser, or the Flutter app.
- Communications endpoints all require an authorised editing session; the
  audit table (`comm_audit`) records every action with the acting role.
- Contacts and call metadata stay in the same SQLite database and backups as
  the rest of the app; the do-not-contact list is checked on every send and
  every call regardless of consent flags.
