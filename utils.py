import time
from datetime import datetime
from config import LOG_FILE


def iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def log_event(message):
    line = f"{iso_now()} | {message}"
    print(line, flush=True)

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(line + "\n")
    except Exception:
        pass


def to_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def to_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def parse_iso(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def seconds_old(timestamp):
    parsed = parse_iso(timestamp)

    if parsed is None:
        return None

    return (datetime.now() - parsed).total_seconds()


def is_stale(timestamp, max_age_seconds):
    age = seconds_old(timestamp)

    if age is None:
        return True

    return age > max_age_seconds
