# Frontend Implementation Delta

What changed since your current integration:

1) **Compliance/Docs & Integrity**
   - New: `POST /api/v1/drivers/documents/upload` now rejects infected files; includes hash metadata and returns `signedUrl` when using R2. No payload change, but handle 400 with detail "Infected file detected".
   - New: `GET /api/v1/drivers/documents/{docId}/verify` to let drivers check integrity; surface pass/fail message.
   - New: Quarantine list for admins `GET /api/v1/quarantine/` (view-only) for flagged uploads.

2) **Background Checks**
   - New admin endpoint: `POST /api/v1/admins/driver/{driverId}/background/provider` to ingest provider results.
   - Admin list: `GET /api/v1/admins/background-checks` (existing drivers and status history).
   - Auto-link: approving required docs can auto-pass background; drivers may see status flip to `PASSED` without admin manual change.

3) **Observability/Health (read-only for dashboards)**
   - Metrics at `/metrics` (Prometheus) include match time, driver accepts, payment failures, SSE backlog, AV/integrity failures.
   - Alert/dashboard assets added (no frontend change, but if you host dashboards, import `dashboards/observability.json`).

4) **Notifications**
   - Push now uses OneSignal; email fallback added. Frontend should still rely on SSE for realtime; no payload change. If you show device opt-in, ensure OneSignal player IDs are available to backend via your existing flow (if any).

5) **New docs**
   - Reference: `frontend_instructions/endpoints.md` (complete endpoint list), `docs/alert_rules.md`, `docs/background_checks.md`.

Actions for frontend to implement/update:
- Add UI hook for drivers to run integrity check (call `/documents/{docId}/verify` and display result).
- Admin console: add background checks list + provider update form; add quarantine events view.
- If you collect OneSignal player IDs, send them with user session so backend can push (optional; SSE still primary).
- Update error handling for document upload to show AV rejection message.
