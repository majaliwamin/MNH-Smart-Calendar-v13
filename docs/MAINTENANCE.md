# Maintenance notes

- Keep HTTP endpoints in `backend/app/api/routes.py`; application assembly and middleware belong in `backend/app/main.py`.
- Keep SQLite schema/transactions in `backend/app/database/connection.py` and business operations in `backend/app/services/`.
- Keep UI styles in `frontend/css/app.css`; do not add large inline style blocks to `index.html`.
- Keep browser logic in `frontend/js/app.js`; shared API calls belong in `frontend/js/api-client.js`.
- Keep Flutter screens and widgets under `mobile/lib/`; all data access must go through `mobile/lib/services/api_service.dart` and the same backend API.
- Do not edit or delete the SQLite database while the server is running. Stop the local server before manual database replacement.
- Automatic backups are produced while the service is running. Verify a real `.sqlite3` snapshot and the `/api/health` backup fields.
- For Render, keep the persistent disk mounted at `/var/data`; do not deploy multiple independent service instances that write to the same SQLite database.
- Keep EXAMS server rules in `backend/app/exams/routes.py`, transactional storage in `backend/app/exams/store.py`, validation in `schemas.py`, permissions in `permissions.py`, and the hash-chained ledger in `audit.py`. Keep the EXAMS browser client in `frontend/js/exams.js` and styles in `frontend/css/exams.css`.
- Do not add `exams_*` collections to generic `/api/export` or `/api/restore`. Use `GET /api/exams/backup` and `POST /api/exams/restore`, which verify a SHA-256 checksum and block overwrites unless an EXAMS administrator explicitly allows them.
- Treat `exams_audit_ledger` as append-only. SQLite triggers block UPDATE/DELETE; never edit the ledger manually to "fix" data. Use `GET /api/exams/audit/verify` to check the hash chain.
- When any EXAMS frontend file changes, bump the shared build id in `backend/app/config.py`, `frontend/index.html`, `frontend/service-worker.js`, `scripts/build_statistical_glossary.py`, hard-coded test assertions, and regenerate the glossary plus local-knowledge JSON. See `docs/EXAMS.md`.
