from datetime import UTC, datetime


def now():
    return datetime.now(UTC)


def time_diff(dt):
    return max(0, int(round(dt.days * 86400 + dt.seconds)))
