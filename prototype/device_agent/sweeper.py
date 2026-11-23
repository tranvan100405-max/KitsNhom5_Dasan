import sqlite3
from datetime import datetime

from . import config, timeutil
from .db import transaction
from .errors import ApiError
from .service import _fail_or_retry, _load_task
from .state_machine import TaskStatus as S


def sweep_timeouts(conn: sqlite3.Connection, now: datetime) -> dict:
    timed_out = retried = 0
    now_iso = timeutil.to_iso(now)
    with transaction(conn):
        rows = conn.execute(
            "SELECT id, status, lastHeartbeatAt FROM device_tasks"
            " WHERE status IN ('DOWNLOADING','INSTALLING','VERIFYING')"
        ).fetchall()
        for row in rows:
            deadline = timeutil.plus_seconds(
                timeutil.from_iso(row["lastHeartbeatAt"]),
                config.STATE_TIMEOUT_SECONDS[row["status"]],
            )
            if deadline > now:
                continue
            task = _load_task(conn, row["id"])
            try:
                outcome = _fail_or_retry(
                    conn, task, S.TIMEOUT, now, f"STATE_TIMEOUT_{row['status']}",
                    f"Không nhận được heartbeat sau khi ở trạng thái {row['status']} quá hạn",
                )
            except ApiError:
                continue
            if outcome["status"] == S.PENDING.value:
                retried += 1
            else:
                timed_out += 1

        wave_expired = conn.execute(
            "UPDATE device_tasks SET status = 'TIMEOUT', errorCode = 'WAVE_DEADLINE_EXCEEDED',"
            " errorMessage = 'Wave đã quá hạn chót deadlineAt khi task chưa bắt đầu',"
            " finishedAt = ?, lastHeartbeatAt = ?"
            " WHERE status = 'PENDING' AND waveId IN"
            " (SELECT id FROM campaign_waves WHERE deadlineAt IS NOT NULL AND deadlineAt < ?)",
            (now_iso, now_iso, now_iso),
        ).rowcount

        offline_before = timeutil.to_iso(timeutil.plus_seconds(
            now, -config.CHECKIN_INTERVAL_SECONDS * config.OFFLINE_AFTER_MISSED_CHECKINS))
        offline = conn.execute(
            "UPDATE devices SET connectivity = 'OFFLINE'"
            " WHERE connectivity = 'ONLINE' AND lastCheckInAt < ?",
            (offline_before,),
        ).rowcount
    return {"retried": retried, "timedOut": timed_out, "waveDeadlineExpired": wave_expired,
            "markedOffline": offline}
