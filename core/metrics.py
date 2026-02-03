from prometheus_client import Counter, Histogram

match_time_seconds = Histogram(
    "ride_match_time_seconds",
    "Time from ride request to driver assignment",
    buckets=(1, 2, 5, 10, 20, 40, 80),
)

driver_acceptance_rate = Counter(
    "ride_driver_accepts_total",
    "Count of driver acceptances",
)

driver_rejects = Counter(
    "ride_driver_rejects_total",
    "Count of driver rejects/timeouts",
)

payment_failures = Counter(
    "ride_payment_failures_total",
    "Count of payment failures",
)

sse_backlog = Histogram(
    "ride_sse_pending_events",
    "Pending SSE events length sampled",
    buckets=(0, 1, 5, 10, 20, 50, 100, 200),
)

av_scan_failures = Counter(
    "storage_av_scan_failures_total",
    "Count of AV scan failures",
)

integrity_failures = Counter(
    "storage_integrity_failures_total",
    "Count of integrity verification failures",
)
