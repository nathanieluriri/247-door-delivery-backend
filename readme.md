# Door Delivery Backend API

Backend service for a rider/driver/admin delivery platform built with FastAPI, MongoDB, Redis, Celery, and SSE.

## What This Service Does
- Rider, driver, and admin authentication flows (including Google OAuth for rider/driver)
- Ride lifecycle management and dispatch
- Driver onboarding/profile/document handling
- Payment integration and webhook processing
- Chat and Server-Sent Events (SSE) updates
- Push notification token registration and notification delivery pipeline
- Health checks, structured logging, rate limiting, and metrics

## Tech Stack
- Python 3.11
- FastAPI
- MongoDB (`motor`, `pymongo`)
- Redis (`redis`, `redis_om`)
- Celery + Flower
- Stripe
- Authlib (Google OAuth)
- APScheduler
- Prometheus FastAPI Instrumentator

## Project Structure
```text
api/v1/                 Versioned API routes (admins, drivers, riders, payments, sse, chats)
core/                   Shared infra/config (db, scheduler, storage, routing, payments)
services/               Business logic services
repositories/           Data access layer
schemas/                Pydantic request/response models
security/               Auth, JWT, permissions, session/oauth helpers
middlewares/            Request timing, structured logs, rate limits, admin path normalization
tests/                  Unit and integration-style tests
main.py                 App entrypoint and router mounting
celery_worker.py        Celery worker entrypoint
docker-compose.yml      Multi-service local stack
Dockerfile              Container build
```

## API Base and Docs
- Base API prefix: `/api/v1`
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Prometheus metrics: `/metrics`
- Health:
  - `/health`
  - `/health-detailed`

## Core Route Groups
- `/api/v1/admins`
- `/api/v1/drivers`
- `/api/v1/riders`
- `/api/v1/payments`
- `/api/v1/sse`
- `/api/v1/chats`

## API Contracts
- Driver headshot upload + admin approval flow:
  - [docs/driver_headshot_upload_and_approval.md](docs/driver_headshot_upload_and_approval.md)
- Reverse geocoding + ride calculation frontend flow:
  - [docs/reverse_geocoding_ride_calculation_flow.md](docs/reverse_geocoding_ride_calculation_flow.md)

## Prerequisites
- Python 3.11+
- MongoDB
- Redis
- (Optional) Docker + Docker Compose

## Quick Start (Docker)
1. Create/update `.env` with required values.
2. Start stack:
```bash
docker compose up --build
```
3. API available at `http://localhost:7860`.
4. Flower available at `http://localhost:5555`.

## Quick Start (Local)
1. Create virtual env and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

2. Ensure MongoDB and Redis are running.

3. Run API:
```bash
fastapi run main.py --host 0.0.0.0 --port 7860
```

4. Run worker (separate shell):
```bash
celery -A celery_worker worker -l info --pool=custom --concurrency=5
```

5. Optional Flower:
```bash
celery -A celery_worker.celery_app flower --port=5555
```

## Configuration
The service reads configuration from environment variables. Keep secrets out of source control.

### Minimum required for local development
- `DB_TYPE` (`mongodb` or `sqlite`)
- `DB_NAME` (for MongoDB mode)
- `MONGO_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `SECRET_KEY`

### Commonly used variables
- Auth/session:
  - `SECRETID`
  - `SESSION_SECRET_KEY`
  - `SESSION_MAX_AGE_SECONDS`
  - `SESSION_SAME_SITE`
  - `SESSION_HTTPS_ONLY`
  - `ACCESS_TOKEN_EXPIRE_MINUTES`
  - `REFRESH_TOKEN_EXPIRE_DAYS`
  - `OAUTH_STATE_SECRET`
  - `OAUTH_STATE_TTL_SECONDS`
  - `RETURN_URL_ALLOWLIST`
  - `RIDER_FRONTEND_URL_LOCAL`
  - `DRIVER_FRONTEND_URL_LOCAL`
  - `RIDER_ERROR_PAGE_URL`
  - `DRIVER_ERROR_PAGE_URL`
- Google OAuth / Maps:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_CLIENT_ID_FOR_DRIVER_ROLE`
  - `GOOGLE_CLIENT_SECRET_FOR_DRIVER_ROLE`
  - `GOOGLE_MAPS_API_KEY`
- Payments:
  - `PAYMENT_DEFAULT_PROVIDER`
  - `STRIPE_API_KEY`
  - `STRIPE_WEBHOOK_SECRET`
  - `STRIPE_CONNECT_RETURN_URL`
  - `STRIPE_CONNECT_REFRESH_URL`
  - `STRIPE_TAX_RATE_ID`
- Notifications:
  - `ONESIGNAL_APP_ID`
  - `ONESIGNAL_API_KEY`
  - `PUSH_TOKEN_TTL_SECONDS`
- Email:
  - `EMAIL_HOST`
  - `EMAIL_PORT`
  - `EMAIL_USERNAME`
  - `EMAIL_PASSWORD`
  - `EMAIL_USE_TLS`
- Storage:
  - `STORAGE_BACKEND`
  - `STORAGE_LOCAL_ROOT`
  - `STORAGE_S3_ENDPOINT`
  - `STORAGE_S3_REGION`
  - `STORAGE_S3_BUCKET`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`

## Notifications
Driver/rider notification plumbing already exists:
- Push token registration endpoints:
  - `POST /api/v1/drivers/push/register`
  - `GET /api/v1/drivers/push/status`
  - `POST /api/v1/riders/push/register`
  - `GET /api/v1/riders/push/status`
- Tokens are stored in Redis sets with TTL.
- Notification service attempts push first, then fallback channels (email/SMS behavior depends on provider wiring), with retry and DLQ queues in Redis.

## Tests
Run:
```bash
pytest -q
```

Useful targeted runs:
```bash
pytest -q tests/test_oauth_return.py
pytest -q tests/test_driver_oauth_callback.py
pytest -q tests/test_place_service.py
```

## Operational Notes
- Rate limits are Redis-backed fixed windows:
  - Anonymous: `120/min`
  - Member: `160/min`
  - Admin: `240/min`
- Startup creates key Mongo indexes (including refresh token TTL index).
- APScheduler heartbeat and stale driver presence cleanup run automatically.
- Admin path normalization middleware avoids slash-based redirects for `/api/v1/admins/...` routes.

## Troubleshooting
- `307` redirect from `https` to `http` on admin endpoints:
  - Use latest code with admin path normalization middleware.
  - Ensure reverse proxy sets forwarded headers correctly (`X-Forwarded-Proto`, `Host`).
- Push notifications not delivered:
  - Confirm `ONESIGNAL_APP_ID` and `ONESIGNAL_API_KEY`.
  - Confirm device token is registered via `/push/register`.
  - Check Redis connectivity and notification retry/DLQ keys.
- OAuth callback issues:
  - Verify Google OAuth client IDs/secrets and callback URLs.
  - Verify `SESSION_SECRET_KEY`, return URL allowlist/base URL settings.

## Security
- Do not commit real secrets in `.env`.
- Rotate exposed keys immediately if leaked.
- Use HTTPS in production and set secure session settings:
  - `SESSION_HTTPS_ONLY=true`
  - strict allowlists for return URLs

