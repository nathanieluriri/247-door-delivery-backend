# Analysis for core/tasks.py

## Summary
- Registry for async task dispatch by name.

## Potential issues / gaps
- Duplicate task keys can cause confusion and hidden overrides.
- No versioning or namespacing for task keys.

## Notes
- Used by Celery task dispatcher.
