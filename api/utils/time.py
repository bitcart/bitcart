from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc)


def time_diff(dt):
    return max(0, int(round(dt.days * 86400 + dt.seconds)))
