# Maintenance notes

- Keep HTTP endpoints in `backend/app/api/routes.py`; application assembly and middleware belong in `backend/app/main.py`.
- Keep SQLite schema/transactions in `backend/app/database/connection.py` and business operations in `backend/app/services/`.
- Keep UI styles in `frontend/css/app.css`; do not add large inline style blocks to `index.html`.
- Keep browser logic in `frontend/js/app.js`; shared API calls belong in `frontend/js/api-client.js`.
- Keep Flutter screens and widgets under `mobile/lib/`; all data access must go through `mobile/lib/services/api_service.dart` and the same backend API.
- Do not edit or delete the SQLite database while the server is running. Stop the local server before manual database replacement.
- Automatic backups are produced while the service is running. Verify a real `.sqlite3` snapshot and the `/api/health` backup fields.
- For Render, keep the persistent disk mounted at `/var/data`; do not deploy multiple independent service instances that write to the same SQLite database.
