import hashlib
import hmac
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request

from . import config, timeutil
from .db import get_db
from .errors import ApiError


@dataclass(frozen=True)
class DeviceIdentity:
    id: str
    serialNo: str
    model: str


def canonical_string(serial: str, timestamp: str, nonce: str, method: str, path: str,
                     body: bytes) -> str:
    return "\n".join([serial, timestamp, nonce, method.upper(), path,
                      hashlib.sha256(body).hexdigest()])


def sign(secret: str, serial: str, timestamp: str, nonce: str, method: str, path: str,
         body: bytes) -> str:
    msg = canonical_string(serial, timestamp, nonce, method, path, body).encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def signed_headers(serial: str, secret: str, method: str, path: str, body: bytes,
                   timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    ts = str(timestamp if timestamp is not None else int(timeutil.now().timestamp()))
    nonce = nonce or uuid.uuid4().hex
    return {
        "X-Device-Serial": serial,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": sign(secret, serial, ts, nonce, method, path, body),
        "Content-Type": "application/json",
    }


class NonceCache:
    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def use(self, serial: str, nonce: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._seen) > 100_000:
                self._seen = {k: exp for k, exp in self._seen.items() if exp > now}
            key = (serial, nonce)
            exp = self._seen.get(key)
            if exp is not None and exp > now:
                return False
            self._seen[key] = now + self._ttl
            return True


nonce_cache = NonceCache(config.NONCE_TTL_SECONDS)

_UNAUTHORIZED = "Xác thực thiết bị thất bại"


async def verify_device(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> DeviceIdentity:
    serial = request.headers.get("X-Device-Serial")
    ts = request.headers.get("X-Timestamp")
    nonce = request.headers.get("X-Nonce")
    signature = request.headers.get("X-Signature")
    if not serial or not ts or not nonce or not signature:
        raise ApiError(401, _UNAUTHORIZED, {"reason": "MISSING_AUTH_HEADERS"})
    if not 8 <= len(nonce) <= 64:
        raise ApiError(401, _UNAUTHORIZED, {"reason": "INVALID_NONCE"})

    try:
        ts_int = int(ts)
    except ValueError:
        raise ApiError(401, _UNAUTHORIZED, {"reason": "INVALID_TIMESTAMP"})
    if abs(timeutil.now().timestamp() - ts_int) > config.HMAC_MAX_CLOCK_SKEW_SECONDS:
        raise ApiError(401, _UNAUTHORIZED, {"reason": "TIMESTAMP_OUT_OF_WINDOW"})

    row = conn.execute(
        """SELECT d.id, d.serialNo, d.model, c.secret
             FROM devices d JOIN device_credentials c ON c.deviceId = d.id
            WHERE d.serialNo = ?""",
        (serial,),
    ).fetchone()
    body = await request.body()
    expected = sign(row["secret"] if row else "unknown-device", serial, ts, nonce,
                    request.method, request.url.path, body)
    if row is None or not hmac.compare_digest(expected, signature):
        raise ApiError(401, _UNAUTHORIZED, {"reason": "INVALID_SIGNATURE"})

    if not nonce_cache.use(serial, nonce):
        raise ApiError(401, _UNAUTHORIZED, {"reason": "NONCE_REUSED"})

    return DeviceIdentity(id=row["id"], serialNo=row["serialNo"], model=row["model"])
