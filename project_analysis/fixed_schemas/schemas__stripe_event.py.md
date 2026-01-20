# Analysis for schemas/stripe_event.py

## Summary
- Pydantic models for Stripe Event data.

## Potential issues / gaps
- Minimal field constraints (no ranges, regex, or length checks).
- Timestamps use epoch ints with no timezone validation.
- Optional fields may allow invalid state transitions.

## Notes
- Many schemas use aliasing for Mongo `_id` fields.
