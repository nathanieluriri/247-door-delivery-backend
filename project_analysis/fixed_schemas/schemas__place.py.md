# Analysis for schemas/place.py

## Summary
- Pydantic models for place details and fare calculation inputs.

## Potential issues / gaps
- `PlaceBase` defines `address` twice; redundant field.
- No validation for latitude/longitude ranges.
- Fare response uses raw `Vehicle` values without currency or units.

## Notes
- Includes lightweight `Location` model for geo points.
