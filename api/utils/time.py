from datetime import UTC, datetime, timedelta


def now() -> datetime:
    return datetime.now(UTC)


def time_diff(dt: timedelta) -> int:
    return max(0, int(round(dt.days * 86400 + dt.seconds)))
