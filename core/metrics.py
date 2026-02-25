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

sse_events_published_total = Counter(
    "sse_events_published_total",
    "Total SSE events published",
    ["event_type", "user_type"],
)

sse_events_delivered_total = Counter(
    "sse_events_delivered_total",
    "Total SSE events delivered to streams",
    ["event_type", "user_type"],
)

sse_events_acked_total = Counter(
    "sse_events_acked_total",
    "Total SSE events acknowledged by clients",
    ["event_type", "user_type"],
)

sse_ack_latency_seconds = Histogram(
    "sse_ack_latency_seconds",
    "Latency from SSE event creation to acknowledgement",
    ["event_type", "user_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

sse_dead_lettered_total = Counter(
    "sse_dead_lettered_total",
    "Total SSE events moved to dead-letter queue",
    ["reason", "user_type"],
)

sse_queue_overflow_drops_total = Counter(
    "sse_queue_overflow_drops_total",
    "Total SSE events dropped because pending queue exceeded cap",
    ["user_type"],
)

av_scan_failures = Counter(
    "storage_av_scan_failures_total",
    "Count of AV scan failures",
)

integrity_failures = Counter(
    "storage_integrity_failures_total",
    "Count of integrity verification failures",
)
