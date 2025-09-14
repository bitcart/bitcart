from typing import cast


class InvoiceStatus:
    PENDING = "pending"
    PAID = "paid"
    UNCONFIRMED = "unconfirmed"  # equals to paid, electrum status
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    INVALID = "invalid"
    COMPLETE = "complete"
    REFUNDED = "refunded"


class InvoiceExceptionStatus:
    NONE = "none"
    PAID_PARTIAL = "paid_partial"
    PAID_OVER = "paid_over"
    FAILED_CONFIRM = "failed_confirm"


DEFAULT_PENDING_STATUSES = [InvoiceStatus.PENDING, InvoiceStatus.PAID]
PAID_STATUSES = [InvoiceStatus.PAID, InvoiceStatus.CONFIRMED, InvoiceStatus.COMPLETE]
FAILED_STATUSES = [InvoiceStatus.EXPIRED, InvoiceStatus.INVALID]


# TODO: move it to daemon somehow
STATUS_MAPPING = {
    # electrum integer statuses
    0: InvoiceStatus.PENDING,
    1: InvoiceStatus.EXPIRED,
    2: InvoiceStatus.INVALID,
    3: InvoiceStatus.COMPLETE,
    4: "In progress",
    5: "Failed",
    6: "routing",
    7: InvoiceStatus.UNCONFIRMED,
    # for pending checks on reboot we also maintain string versions of those statuses
    "Pending": InvoiceStatus.PENDING,  # electrum < 4.1, electron-cash
    "Unpaid": InvoiceStatus.PENDING,  # electrum 4.1
    "Paid": InvoiceStatus.COMPLETE,
    "Unknown": InvoiceStatus.INVALID,
    "Expired": InvoiceStatus.EXPIRED,
    "Unconfirmed": InvoiceStatus.UNCONFIRMED,
}


def convert_status(status: int | str) -> str:
    if status in STATUS_MAPPING and (isinstance(status, int | str)):
        status = STATUS_MAPPING[status]
    if not status:
        status = InvoiceStatus.EXPIRED
    return cast(str, status)
