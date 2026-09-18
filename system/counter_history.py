"""Bounded, anonymous hourly counter activity (all timestamps are UTC)."""

from datetime import datetime, timedelta, timezone

HISTORY_HOURS = 30 * 24


def history_enabled(value):
    return value is True or (isinstance(value, str) and value.lower() in {'true', 'on', '1'})


def hour_start(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(
        minute=0, second=0, microsecond=0)


def hour_key(hour):
    return hour.strftime('%Y-%m-%dT%H:00:00Z')


def record_hour(history, amount, now=None):
    hour = hour_start(now)
    cutoff = hour_key(hour - timedelta(hours=HISTORY_HOURS - 1))
    key = hour_key(hour)
    retained = {k: v for k, v in (history or {}).items() if cutoff <= k <= key}
    previous = retained.get(key, {})
    retained[key] = {
        'uses': previous.get('uses', 0) + 1,
        'amount': previous.get('amount', 0) + amount,
    }
    return retained


def usage_series(history, hours, now=None):
    end = hour_start(now)
    start = end - timedelta(hours=hours - 1)
    series = []
    for i in range(hours):
        key = hour_key(start + timedelta(hours=i))
        bucket = (history or {}).get(key, {})
        series.append({'hour': key, 'uses': bucket.get('uses', 0),
                       'amount': bucket.get('amount', 0)})
    return series
