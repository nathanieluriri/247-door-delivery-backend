# Production Dependencies

- Python 3.11 runtime
- Redis cluster or highly available instance for rate limiting, presence, SSE, DLQ queues
- MongoDB replica set for app data and APScheduler job store
- Stripe credentials: `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_TAX_RATE_ID`
- S3-compatible object storage (`STORAGE_BACKEND=s3`) with `STORAGE_S3_BUCKET`, `STORAGE_S3_REGION`, optional `STORAGE_S3_ENDPOINT` for presigned URLs
- Queue/Worker: Celery broker on Redis, workers deployed with same codebase; Flower optional for monitoring
- Observability: metrics endpoint `/metrics` scraped by Prometheus; configure logging aggregation to consume JSON logs
- Secrets management: supply environment variables via vault/secret manager (tokens, DB URIs, SMS provider keys when added)
- Networking: expose FastAPI app behind reverse proxy (e.g., nginx) with HTTPS; ensure webhook ingress for Stripe
