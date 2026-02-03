# IAM & Key Rotation (Cloudflare R2 via S3 API)

1) Rotate keys
   - Create new access key in R2 dashboard.
   - Update `.env` with new `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`; deploy.
   - After rollout, delete old key in R2.

2) Least privilege
   - Restrict key to the specific bucket used (`STORAGE_S3_BUCKET`), read/write only.
   - Deny `DeleteObject` if not required; deny `ListAllMyBuckets`.
   - Require TLS; block public bucket ACLs and enforce private bucket policy.

3) Quarantine policy
   - Optional separate prefix `quarantine/`; allow write/read to that prefix for admins only.

4) Logging & auditing
   - Enable access logs on R2 bucket if available; store to separate log bucket.

5) Secrets handling
   - Keep keys in secret manager/CI secrets; avoid commits.
   - Set short rotation cadence (e.g., 90 days) and document each rotation date.
