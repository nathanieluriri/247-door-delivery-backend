# Analysis for core/staff_payment.py

## Summary
- Stripe Connect integration for driver onboarding and payouts.

## Potential issues / gaps
- `pay_driver` passes `description` and `metadata` to `create_payout` but method signature doesn’t accept them.
- Hard-coded country/currency limits multi-region support.
- No idempotency keys or balance checks before transfers/payouts.

## Notes
- Webhook handler updates driver payout eligibility.
