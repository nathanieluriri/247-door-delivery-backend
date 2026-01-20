# Analysis for schemas

## Summary
- Pydantic models for request/response and stored data.

## Potential issues / gaps
- Many models lack field constraints and domain validation.
- Money and time are often floats/ints without explicit units.
- Inconsistent naming and optionality can lead to invalid state.

## Notes
- Several schemas use alias conversion for Mongo `_id` fields.
