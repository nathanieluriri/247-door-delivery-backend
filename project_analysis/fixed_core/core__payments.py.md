# Analysis for core/payments.py

## Summary
- Stripe payment provider and webhook handler for ride payments.

## Potential issues / gaps
- Stripe amount calculation uses `price / 10` instead of smallest currency unit (usually /100).
- Hard-coded currency and tax behavior reduce multi-region support.
- No idempotency keys on Stripe calls (risk of duplicate charges).
- Webhook updates rides without validating amounts or payment_intent ownership.

## Notes
- Emits websocket updates on payment confirmation.
