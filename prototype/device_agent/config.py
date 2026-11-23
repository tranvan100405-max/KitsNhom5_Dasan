import os

DB_PATH = os.environ.get("DASAN_DB_PATH", "dasan_proto.db")

TIME_SCALE = float(os.environ.get("DASAN_TIME_SCALE", "1"))


def _scaled(seconds: float) -> float:
    return seconds / TIME_SCALE


CHECKIN_INTERVAL_SECONDS = _scaled(300)
CHECKIN_JITTER_SECONDS = _scaled(30)
OFFLINE_AFTER_MISSED_CHECKINS = 3

STATE_TIMEOUT_SECONDS = {
    "DOWNLOADING": _scaled(15 * 60),
    "INSTALLING": _scaled(10 * 60),
    "VERIFYING": _scaled(5 * 60),
}

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = [_scaled(1 * 60), _scaled(5 * 60), _scaled(15 * 60)]

DEFAULT_WAVE_DEADLINE_SECONDS = _scaled(24 * 3600)

HMAC_MAX_CLOCK_SKEW_SECONDS = 300
NONCE_TTL_SECONDS = HMAC_MAX_CLOCK_SKEW_SECONDS * 2

PRESIGNED_URL_TTL_SECONDS = STATE_TIMEOUT_SECONDS["DOWNLOADING"]
FIRMWARE_CDN_BASE_URL = "https://cdn.example.local/firmware"
