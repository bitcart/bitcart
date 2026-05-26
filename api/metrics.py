from prometheus_client import Counter, Gauge, Histogram, Summary

NAMESPACE = "bitcart"

pending_creation_payment_methods_count = Gauge(
    "pending_creation_payment_methods_count",
    "Number of payment methods pending creation",
    labelnames=["currency", "contract", "store", "lightning"],
    namespace=NAMESPACE,
    multiprocess_mode="livesum",
)

_HIGHR_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    1.5,
    2.0,
    2.5,
    3.0,
    3.5,
    4.0,
    4.5,
    5.0,
    7.5,
    10.0,
    30.0,
    60.0,
    float("inf"),
)
_LOWR_BUCKETS = (0.1, 0.5, 1.0, float("inf"))

http_requests_total = Counter(
    "http_requests_total",
    "Total number of requests by method, status and handler.",
    labelnames=("method", "status", "handler"),
    namespace=NAMESPACE,
)
http_request_size_bytes = Summary(
    "http_request_size_bytes",
    "Content length of incoming requests by handler.",
    labelnames=("handler",),
    namespace=NAMESPACE,
)
http_response_size_bytes = Summary(
    "http_response_size_bytes",
    "Content length of outgoing responses by handler.",
    labelnames=("handler",),
    namespace=NAMESPACE,
)
http_request_duration_highr_seconds = Histogram(
    "http_request_duration_highr_seconds",
    "Latency with many buckets but no API specific labels.",
    buckets=_HIGHR_BUCKETS,
    namespace=NAMESPACE,
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Latency with only few buckets by handler.",
    labelnames=("method", "handler"),
    buckets=_LOWR_BUCKETS,
    namespace=NAMESPACE,
)
http_requests_inprogress = Gauge(
    "http_requests_inprogress",
    "Number of HTTP requests in progress.",
    labelnames=("method", "handler"),
    namespace=NAMESPACE,
    multiprocess_mode="livesum",
)
