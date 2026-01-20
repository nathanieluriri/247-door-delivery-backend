# Analysis for core/scheduler.py

## Summary
- APScheduler configuration using MongoDB job store.

## Potential issues / gaps
- No timezone configuration; scheduled jobs may drift.
- No error handling for job store connection failures.

## Notes
- Scheduler is started in `main.py` lifespan.
