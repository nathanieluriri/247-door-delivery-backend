# Local Dependencies

- Python 3.11+
- Redis (for rate limiting, presence, SSE queues) running on localhost:6379 (DB 0 by default)
- MongoDB (for primary data) reachable via `MONGO_URL`
- Optional: Local file storage for documents (`STORAGE_BACKEND=local`, default path `uploads/documents`)
- Poetry/pip: install `requirements.txt`
- Environment: copy `.env.example` (if present) and set `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET` for payment flows; set `STORAGE_BACKEND=local` for uploads.
- For tests: no external services required; uses pure unit tests. Run `pytest`.
