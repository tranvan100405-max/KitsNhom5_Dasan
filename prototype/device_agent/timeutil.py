from datetime import datetime, timedelta, timezone

_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_FMT)


def from_iso(value: str) -> datetime:
    return datetime.strptime(value, _FMT).replace(tzinfo=timezone.utc)


def plus_seconds(dt: datetime, seconds: float) -> datetime:
    return dt + timedelta(seconds=seconds)
