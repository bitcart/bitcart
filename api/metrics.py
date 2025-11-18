from prometheus_client import Gauge

pending_creation_payment_methods_count = Gauge(
    "bitcart_pending_creation_payment_methods_count",
    "Number of payment methods pending creation",
    labelnames=["currency", "contract", "store", "lightning"],
    multiprocess_mode="livesum",
)
