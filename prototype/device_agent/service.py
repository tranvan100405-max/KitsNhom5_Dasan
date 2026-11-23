import hashlib
import sqlite3
import uuid
from datetime import datetime

from . import config, timeutil
from .auth import DeviceIdentity
from .db import transaction
from .errors import ApiError
from .schemas import CheckInRequest, TaskResultRequest
from .state_machine import (
    DOWNLOAD_SLOT_STATUSES,
    IN_PROGRESS_STATUSES,
    RECONCILE_SUCCESS_FROM,
    STAGE_TO_STATUS,
    InvalidTransition,
    Stage,
    TaskStatus as S,
    validate_transition,
)

_TASK_SELECT = """
SELECT t.*,
       tf.versionNo              AS toVersion,
       tf.checksum               AS toChecksum,
       tf.model                  AS toModel,
       tf.status                 AS toFirmwareStatus,
       tf.minRequiredVersionCode AS minRequiredVersionCode,
       ff.versionNo              AS fromVersion,
       c.status                  AS campaignStatus,
       c.maxConcurrentDevices    AS maxConcurrentDevices,
       w.status                  AS waveStatus,
       w.deadlineAt              AS waveDeadlineAt
  FROM device_tasks t
  JOIN firmware_versions tf ON tf.id = t.toFirmwareId
  LEFT JOIN firmware_versions ff ON ff.id = t.fromFirmwareId
  JOIN campaigns c ON c.id = t.campaignId
  JOIN campaign_waves w ON w.id = t.waveId
"""

_SLOT_SQL = ",".join(f"'{s.value}'" for s in DOWNLOAD_SLOT_STATUSES)


def _resolve_firmware(conn: sqlite3.Connection, model: str, version: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, versionCode FROM firmware_versions WHERE model = ? AND versionNo = ?",
        (model, version),
    ).fetchone()


def _load_task(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row | None:
    return conn.execute(_TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()


def _load_active_task(conn: sqlite3.Connection, device_id: str) -> sqlite3.Row | None:
    return conn.execute(
        _TASK_SELECT + " WHERE t.deviceId = ? AND t.status IN "
        "('PENDING','DOWNLOADING','INSTALLING','VERIFYING')",
        (device_id,),
    ).fetchone()


def _update_task(conn: sqlite3.Connection, task: sqlite3.Row, now: datetime, **fields) -> None:
    fields.setdefault("lastHeartbeatAt", timeutil.to_iso(now))
    cols = ", ".join(f"{k} = ?" for k in fields)
    cur = conn.execute(
        f"UPDATE device_tasks SET {cols} WHERE id = ? AND status = ? AND attemptCount = ?",
        (*fields.values(), task["id"], task["status"], task["attemptCount"]),
    )
    if cur.rowcount != 1:
        raise ApiError(409, "Task vừa bị thay đổi bởi tiến trình khác, hãy thử lại",
                       {"reason": "CONCURRENT_MODIFICATION", "taskId": task["id"]})


def retry_eligible_at(task: sqlite3.Row) -> str | None:
    attempt = task["attemptCount"]
    if attempt <= 1 or not task["lastHeartbeatAt"]:
        return None
    return timeutil.to_iso(timeutil.plus_seconds(
        timeutil.from_iso(task["lastHeartbeatAt"]), config.RETRY_BACKOFF_SECONDS[attempt - 2]))


def _fail_or_retry(conn: sqlite3.Connection, task: sqlite3.Row, failure: S, now: datetime,
                   error_code: str | None, error_message: str | None) -> dict:
    validate_transition(S(task["status"]), failure)
    attempt = task["attemptCount"]
    if attempt < config.MAX_ATTEMPTS:
        validate_transition(failure, S.PENDING)
        _update_task(conn, task, now, status=S.PENDING.value, attemptCount=attempt + 1,
                     errorCode=error_code, errorMessage=error_message)
        next_at = timeutil.to_iso(
            timeutil.plus_seconds(now, config.RETRY_BACKOFF_SECONDS[attempt - 1]))
        return {"status": S.PENDING.value, "attempt": attempt + 1, "nextEligibleAt": next_at}

    _update_task(conn, task, now, status=failure.value, errorCode=error_code,
                 errorMessage=error_message, finishedAt=timeutil.to_iso(now))
    return {"status": failure.value, "attempt": attempt, "nextEligibleAt": None}


def _finish_success(conn: sqlite3.Connection, task: sqlite3.Row, now: datetime,
                    partition: str) -> dict:
    now_iso = timeutil.to_iso(now)
    _update_task(conn, task, now, status=S.SUCCESS.value, finishedAt=now_iso,
                 errorCode=None, errorMessage=None)
    conn.execute(
        "UPDATE devices SET currentFirmwareId = ?, activePartition = ? WHERE id = ?",
        (task["toFirmwareId"], partition, task["deviceId"]),
    )
    conn.execute(
        "INSERT OR IGNORE INTO device_firmware_histories (id, deviceId, firmwareId, taskId, installedAt)"
        " VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), task["deviceId"], task["toFirmwareId"], task["id"], now_iso),
    )
    return {"status": S.SUCCESS.value, "attempt": task["attemptCount"], "nextEligibleAt": None}


def _finish_rollback(conn: sqlite3.Connection, task: sqlite3.Row, now: datetime, model: str,
                     reported_version: str, partition: str,
                     error_code: str | None, error_message: str | None) -> dict:
    validate_transition(S(task["status"]), S.ROLLED_BACK)
    _update_task(conn, task, now, status=S.ROLLED_BACK.value, finishedAt=timeutil.to_iso(now),
                 errorCode=error_code or "ROLLED_BACK", errorMessage=error_message)
    fw = _resolve_firmware(conn, model, reported_version)
    conn.execute(
        "UPDATE devices SET currentFirmwareId = ?, activePartition = ? WHERE id = ?",
        (fw["id"] if fw else task["fromFirmwareId"], partition, task["deviceId"]),
    )
    return {"status": S.ROLLED_BACK.value, "attempt": task["attemptCount"], "nextEligibleAt": None}


def _expire_by_wave_deadline(conn: sqlite3.Connection, task: sqlite3.Row, now: datetime) -> None:
    validate_transition(S(task["status"]), S.TIMEOUT)
    _update_task(conn, task, now, status=S.TIMEOUT.value, errorCode="WAVE_DEADLINE_EXCEEDED",
                 errorMessage="Wave đã quá hạn chót deadlineAt khi task chưa bắt đầu",
                 finishedAt=timeutil.to_iso(now))


def _presigned_url(task: sqlite3.Row, now: datetime) -> tuple[str, str]:
    expires = timeutil.plus_seconds(now, config.PRESIGNED_URL_TTL_SECONDS)
    exp_unix = int(expires.timestamp())
    sig = hashlib.sha256(f"{task['id']}:{task['attemptCount']}:{exp_unix}".encode()).hexdigest()[:16]
    url = (f"{config.FIRMWARE_CDN_BASE_URL}/{task['toModel']}/{task['toVersion']}.bin"
           f"?task={task['id']}&attempt={task['attemptCount']}&expires={exp_unix}&sig={sig}")
    return url, timeutil.to_iso(expires)


def _task_info(task: sqlite3.Row, now: datetime) -> dict:
    url, url_exp = _presigned_url(task, now)
    timeout = config.STATE_TIMEOUT_SECONDS.get(task["status"])
    deadline = None
    if timeout and task["lastHeartbeatAt"]:
        deadline = timeutil.to_iso(
            timeutil.plus_seconds(timeutil.from_iso(task["lastHeartbeatAt"]), timeout))
    return {
        "taskId": task["id"],
        "attempt": task["attemptCount"],
        "taskStatus": task["status"],
        "toVersion": task["toVersion"],
        "downloadUrl": url,
        "urlExpiresAt": url_exp,
        "checksum": task["toChecksum"],
        "stateDeadlineAt": deadline,
    }


def _no_task(now: datetime) -> dict:
    return {"action": "NO_TASK", "task": None,
            "nextCheckInSeconds": config.CHECKIN_INTERVAL_SECONDS,
            "serverTime": timeutil.to_iso(now)}


def check_in(conn: sqlite3.Connection, device: DeviceIdentity, req: CheckInRequest,
             now: datetime) -> dict:
    if req.serialNo != device.serialNo:
        raise ApiError(403, "serialNo trong body không khớp với thiết bị đã ký request")
    if req.model != device.model:
        raise ApiError(400, "model không khớp với dữ liệu đăng ký của thiết bị")

    with transaction(conn):
        now_iso = timeutil.to_iso(now)
        reported_fw = _resolve_firmware(conn, device.model, req.currentVersion)
        conn.execute(
            "UPDATE devices SET lastCheckInAt = ?, connectivity = 'ONLINE', activePartition = ?,"
            " currentFirmwareId = COALESCE(?, currentFirmwareId) WHERE id = ?",
            (now_iso, req.activePartition, reported_fw["id"] if reported_fw else None, device.id),
        )

        task = _load_active_task(conn, device.id)

        if task is None:
            late = conn.execute(
                _TASK_SELECT + " WHERE t.deviceId = ? AND t.status = 'TIMEOUT'"
                " ORDER BY t.finishedAt DESC LIMIT 1",
                (device.id,),
            ).fetchone()
            if late is not None and late["toVersion"] == req.currentVersion:
                _finish_success(conn, late, now, req.activePartition)
            return _no_task(now)

        status = S(task["status"])
        if req.currentVersion == task["toVersion"] and status in RECONCILE_SUCCESS_FROM:
            _finish_success(conn, task, now, req.activePartition)
            return _no_task(now)
        if status == S.VERIFYING and req.currentVersion == task["fromVersion"]:
            _finish_rollback(conn, task, now, device.model, req.currentVersion,
                             req.activePartition, "ROLLBACK_DETECTED_ON_CHECKIN",
                             "Thiết bị check-in với firmware cũ khi task đang VERIFYING")
            return _no_task(now)

        if status in IN_PROGRESS_STATUSES:
            return {"action": "UPDATE", "task": _task_info(task, now),
                    "nextCheckInSeconds": config.CHECKIN_INTERVAL_SECONDS,
                    "serverTime": now_iso}

        if task["waveDeadlineAt"] and task["waveDeadlineAt"] < now_iso:
            _expire_by_wave_deadline(conn, task, now)
            return _no_task(now)
        if task["campaignStatus"] != "RUNNING" or task["waveStatus"] != "RUNNING":
            return _no_task(now)
        eligible_at = retry_eligible_at(task)
        if eligible_at and eligible_at > now_iso:
            return _no_task(now)
        if task["toFirmwareStatus"] != "APPROVED":
            return _no_task(now)

        min_code = task["minRequiredVersionCode"]
        if task["toModel"] != device.model or (min_code is not None and (
                reported_fw is None or reported_fw["versionCode"] < min_code)):
            validate_transition(status, S.FAILED)
            _update_task(conn, task, now, status=S.FAILED.value, errorCode="INCOMPATIBLE",
                         errorMessage=f"Thiết bị {device.model} v{req.currentVersion} không đủ điều kiện"
                                      f" lên v{task['toVersion']} (yêu cầu versionCode >= {min_code})",
                         finishedAt=now_iso)
            return _no_task(now)

        downloading = conn.execute(
            f"SELECT COUNT(*) FROM device_tasks WHERE campaignId = ? AND status IN ({_SLOT_SQL})",
            (task["campaignId"],),
        ).fetchone()[0]
        if downloading >= task["maxConcurrentDevices"]:
            return _no_task(now)

        validate_transition(status, S.DOWNLOADING)
        _update_task(conn, task, now, status=S.DOWNLOADING.value,
                     startedAt=task["startedAt"] or now_iso)
        claimed = _load_task(conn, task["id"])
        return {"action": "UPDATE", "task": _task_info(claimed, now),
                "nextCheckInSeconds": config.CHECKIN_INTERVAL_SECONDS,
                "serverTime": now_iso}


def _result(task_id: str, outcome: dict, duplicate: bool) -> dict:
    return {"taskId": task_id, "status": outcome["status"], "attempt": outcome["attempt"],
            "duplicate": duplicate, "nextEligibleAt": outcome.get("nextEligibleAt")}


def report_result(conn: sqlite3.Connection, device: DeviceIdentity, task_id: str,
                  req: TaskResultRequest, now: datetime) -> dict:
    with transaction(conn):
        task = _load_task(conn, task_id)
        if task is None:
            raise ApiError(404, "Không tìm thấy task", {"taskId": task_id})
        if task["deviceId"] != device.id:
            raise ApiError(403, "Task không thuộc về thiết bị này", {"taskId": task_id})

        current = S(task["status"])
        stage = Stage(req.stage)
        new = STAGE_TO_STATUS[stage]
        current_outcome = {"status": current.value, "attempt": task["attemptCount"],
                           "nextEligibleAt": retry_eligible_at(task) if current == S.PENDING else None}

        if new == S.SUCCESS:
            if req.reportedVersion != task["toVersion"]:
                raise ApiError(409, "Báo SUCCESS nhưng phiên bản đang chạy không khớp firmware đích",
                               {"reason": "VERSION_MISMATCH", "expected": task["toVersion"],
                                "reported": req.reportedVersion})
            if current == S.SUCCESS:
                return _result(task_id, current_outcome, duplicate=True)
            if current not in RECONCILE_SUCCESS_FROM:
                raise ApiError(409, f"Không thể chuyển trạng thái {current.value} -> SUCCESS",
                               {"reason": "INVALID_TRANSITION", "currentStatus": current.value})
            return _result(task_id, _finish_success(conn, task, now, req.activePartition), False)

        if req.attempt != task["attemptCount"]:
            if req.attempt < task["attemptCount"] and new == S.FAILED:
                return _result(task_id, current_outcome, duplicate=True)
            raise ApiError(409, "Báo cáo thuộc lượt thử đã cũ",
                           {"reason": "STALE_ATTEMPT", "currentAttempt": task["attemptCount"],
                            "reportedAttempt": req.attempt})

        if current == new:
            if current in IN_PROGRESS_STATUSES:
                _update_task(conn, task, now)
            return _result(task_id, current_outcome, duplicate=True)

        try:
            if new == S.FAILED:
                outcome = _fail_or_retry(conn, task, S.FAILED, now, req.errorCode or "UNKNOWN",
                                         req.errorMessage)
            elif new == S.ROLLED_BACK:
                outcome = _finish_rollback(conn, task, now, device.model, req.reportedVersion,
                                           req.activePartition, req.errorCode, req.errorMessage)
            else:
                validate_transition(current, new)
                _update_task(conn, task, now, status=new.value)
                outcome = {"status": new.value, "attempt": task["attemptCount"],
                           "nextEligibleAt": None}
        except InvalidTransition as exc:
            raise ApiError(409, str(exc), {"reason": "INVALID_TRANSITION",
                                           "currentStatus": current.value})
        return _result(task_id, outcome, duplicate=False)
