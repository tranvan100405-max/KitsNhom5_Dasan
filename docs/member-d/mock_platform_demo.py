#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mock_platform_demo.py — Mock API & Swagger UI Demo (Task 6 / Điểm cộng #15 — Thành viên D).

Bổ trợ cho `prototype/` (Device Agent FastAPI của Thành viên B) mà KHÔNG đụng chạm file của B
(không gây xung đột Git khi merge), chạy ngay bằng Python chuẩn (0 pip install):
  1. Xác thực Web bằng JWT HS256 thuần stdlib (`POST /api/auth/login`) & Ma trận RBAC 4 vai trò.
  2. Nguyên tắc 4-mắt (`PATCH /api/firmware/{id}/approve`) chặn tự duyệt -> 403 FOUR_EYES_VIOLATION
     ở cả tầng Service lẫn SQLite CHECK Constraint (`uploadedBy <> approvedBy`).
  3. Tạo/chạy Campaign & Emergency Rollback Campaign tra ngược `device_firmware_histories` (#13).
  4. Xác thực Thiết bị cạnh bằng HMAC-SHA256 6 thành phần (`serialNo + ts + nonce + METHOD + path + sha256(body)`)
     kèm Nonce chống Replay (`POST /api/device-agent/check-in` & `/result`).
  5. Nhật ký kiểm toán `audit_logs` bất biến (Trigger SQLite chặn tuyệt đối UPDATE/DELETE), ghi cả lỗi 401/403.
  6. Cổng kiểm định AI (`POST /api/ai/validate`) kết nối trực tiếp tới `validate_output.py`.

Cách chạy:
  python docs/member-d/mock_platform_demo.py --self-test   # Chạy 9 kịch bản kiểm thử tự động end-to-end
  python docs/member-d/mock_platform_demo.py --port 8080   # Mở Swagger UI tại http://localhost:8080/docs
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sqlite3
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Nhập trực tiếp bộ kiểm định AI của Task 3 cùng thư mục
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import validate_output  # noqa: E402

JWT_SECRET = b"dasan-ojt-demo-jwt-hs256-key-not-for-prod"
JWT_TTL_SECONDS = 900  # 15 phút
HMAC_WINDOW_SECONDS = 300


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def issue_jwt(member_id: str, role: str) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    iat = int(time.time())
    payload = _b64url_encode(json.dumps({
        "sub": member_id,
        "role": role,
        "jti": str(uuid.uuid4()),
        "iat": iat,
        "exp": iat + JWT_TTL_SECONDS,
        "iss": "dasan-firmware-demo",
    }).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = _b64url_encode(hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_jwt(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ApiHttpError(401, "Token sai định dạng", {"reason": "MALFORMED_TOKEN"})
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected_sig = _b64url_encode(hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest())
    if not hmac.compare_digest(expected_sig, parts[2]):
        raise ApiHttpError(401, "Chữ ký JWT không hợp lệ", {"reason": "INVALID_TOKEN_SIGNATURE"})
    claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    if claims.get("exp", 0) < int(time.time()):
        raise ApiHttpError(401, "Token đã hết hạn", {"reason": "TOKEN_EXPIRED"})
    return claims


def sign_device_hmac(secret: str, serial: str, ts: str, nonce: str, method: str, path: str, body: bytes) -> str:
    canonical = "\n".join([
        serial, ts, nonce, method.upper(), path, hashlib.sha256(body).hexdigest()
    ])
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 50_000).hex()


class ApiHttpError(Exception):
    def __init__(self, status: int, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.data = data or {}


class PlatformStore:
    """In-memory / SQLite store bám sát ERD chuẩn hóa và quy ước Q1–Q10."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.nonce_cache: dict[tuple[str, str], float] = {}
        self._init_schema()
        self._seed()

    def _init_schema(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            salt TEXT NOT NULL,
            passwordHash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('ADMIN','DEVELOPER','QA','OPERATOR')),
            createdAt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS device_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            customerName TEXT NOT NULL,
            region TEXT NOT NULL,
            timezone TEXT,
            maintenanceWindow TEXT
        );

        CREATE TABLE IF NOT EXISTS firmware_versions (
            id TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            versionNo TEXT NOT NULL,
            versionCode INTEGER NOT NULL,
            releaseNotes TEXT,
            checksum TEXT NOT NULL,
            fileUrl TEXT NOT NULL,
            minRequiredVersion TEXT NOT NULL,
            minRequiredVersionCode INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('UPLOADED','APPROVED','DEPRECATED')),
            uploadedBy TEXT NOT NULL REFERENCES members(id),
            approvedBy TEXT REFERENCES members(id),
            createdAt TEXT NOT NULL,
            UNIQUE (model, versionNo),
            CHECK (minRequiredVersionCode <= versionCode),
            CHECK (approvedBy IS NULL OR uploadedBy <> approvedBy)
        );

        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            serialNo TEXT UNIQUE NOT NULL,
            model TEXT NOT NULL,
            deviceType TEXT NOT NULL CHECK (deviceType IN ('SWITCH','ROUTER','ONT','ONU')),
            groupId TEXT NOT NULL REFERENCES device_groups(id),
            currentFirmwareId TEXT REFERENCES firmware_versions(id),
            connectivity TEXT NOT NULL CHECK (connectivity IN ('ONLINE','OFFLINE')),
            lastCheckInAt TEXT,
            activePartition TEXT CHECK (activePartition IN ('A','B'))
        );

        CREATE TABLE IF NOT EXISTS device_credentials (
            deviceId TEXT PRIMARY KEY REFERENCES devices(id),
            secret TEXT NOT NULL,
            createdAt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            firmwareId TEXT NOT NULL REFERENCES firmware_versions(id),
            targetGroupId TEXT NOT NULL REFERENCES device_groups(id),
            status TEXT NOT NULL CHECK (status IN ('DRAFT','SCHEDULED','RUNNING','PAUSED','COMPLETED','ABORTED')),
            failureThresholdPercent REAL NOT NULL,
            maxConcurrentDevices INTEGER NOT NULL,
            createdBy TEXT NOT NULL REFERENCES members(id),
            scheduledAt TEXT,
            startedAt TEXT,
            finishedAt TEXT
        );

        CREATE TABLE IF NOT EXISTS campaign_waves (
            id TEXT PRIMARY KEY,
            campaignId TEXT NOT NULL REFERENCES campaigns(id),
            waveOrder INTEGER NOT NULL,
            rolloutPercentage REAL NOT NULL,
            minSuccessRateToProceed REAL NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','PAUSED','COMPLETED')),
            deadlineAt TEXT,
            startedAt TEXT,
            finishedAt TEXT,
            UNIQUE (campaignId, waveOrder)
        );

        CREATE TABLE IF NOT EXISTS device_tasks (
            id TEXT PRIMARY KEY,
            campaignId TEXT NOT NULL REFERENCES campaigns(id),
            waveId TEXT NOT NULL REFERENCES campaign_waves(id),
            deviceId TEXT NOT NULL REFERENCES devices(id),
            fromFirmwareId TEXT NOT NULL REFERENCES firmware_versions(id),
            toFirmwareId TEXT NOT NULL REFERENCES firmware_versions(id),
            status TEXT NOT NULL CHECK (status IN ('PENDING','DOWNLOADING','INSTALLING','VERIFYING','SUCCESS','FAILED','TIMEOUT','ROLLED_BACK')),
            attemptCount INTEGER NOT NULL DEFAULT 0,
            errorCode TEXT,
            errorMessage TEXT,
            startedAt TEXT,
            finishedAt TEXT,
            lastHeartbeatAt TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_device_task
        ON device_tasks(deviceId)
        WHERE status IN ('PENDING','DOWNLOADING','INSTALLING','VERIFYING');

        CREATE TABLE IF NOT EXISTS device_firmware_histories (
            id TEXT PRIMARY KEY,
            deviceId TEXT NOT NULL REFERENCES devices(id),
            firmwareId TEXT NOT NULL REFERENCES firmware_versions(id),
            taskId TEXT NOT NULL UNIQUE REFERENCES device_tasks(id),
            installedAt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            actorId TEXT REFERENCES members(id),
            actorType TEXT NOT NULL CHECK (actorType IN ('MEMBER','SYSTEM','DEVICE')),
            action TEXT NOT NULL,
            targetType TEXT NOT NULL,
            targetId TEXT NOT NULL,
            detail TEXT,
            createdAt TEXT NOT NULL,
            CHECK ((actorType = 'MEMBER' AND actorId IS NOT NULL) OR (actorType IN ('SYSTEM','DEVICE') AND actorId IS NULL))
        );

        CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
        BEFORE UPDATE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit_logs is append-only: UPDATE forbidden');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
        BEFORE DELETE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'audit_logs is append-only: DELETE forbidden');
        END;
        """)
        self.conn.commit()

    def _seed(self) -> None:
        if self.conn.execute("SELECT COUNT(*) FROM members").fetchone()[0] > 0:
            return
        ts = now_iso()
        users = [
            ("mem-admin", "admin@dasan.local", "System Admin", "ADMIN", "Admin@123"),
            ("mem-dev", "dev@dasan.local", "Firmware Dev", "DEVELOPER", "Dev@123"),
            ("mem-qa1", "qa1@dasan.local", "QA Reviewer 1", "QA", "Qa1@123"),
            ("mem-op", "operator@dasan.local", "NOC Operator", "OPERATOR", "Op@123"),
        ]
        for uid, email, name, role, pw in users:
            salt = uid
            self.conn.execute(
                "INSERT INTO members VALUES (?,?,?,?,?,?,?)",
                (uid, email, name, salt, hash_pw(pw, salt), role, ts),
            )

        self.conn.execute(
            "INSERT INTO device_groups VALUES (?,?,?,?,?,?)",
            ("grp-hanoi", "ISP-A Hanoi Residential", "ISP-A", "Ha Noi", "Asia/Ho_Chi_Minh", None),
        )
        # Seed baseline firmware v2.3.0 (APPROVED) & v2.4.0 (APPROVED)
        self.conn.execute(
            "INSERT INTO firmware_versions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("fw-230", "DASAN-H660GM", "2.3.0", 20300, "Stable baseline", "sha256-v230-ok",
             "https://cdn.dasan.local/fw/h660gm-2.3.0.bin", "2.0.0", 20000, "APPROVED",
             "mem-dev", "mem-qa1", ts),
        )
        # Seed 2 ONT devices currently on v2.3.0 with prior history
        for idx, serial, secret in [
            (1, "DSN-H660-0001", "demo-secret-0001-not-real"),
            (2, "DSN-H660-0002", "demo-secret-0002-not-real"),
        ]:
            dev_id = f"dev-000{idx}"
            self.conn.execute(
                "INSERT INTO devices VALUES (?,?,?,?,?,?,?,?,?)",
                (dev_id, serial, "DASAN-H660GM", "ONT", "grp-hanoi", "fw-230", "ONLINE", ts, "A"),
            )
            self.conn.execute(
                "INSERT INTO device_credentials VALUES (?,?,?)",
                (dev_id, secret, ts),
            )
        self.conn.commit()

    def write_audit(self, actor_type: str, actor_id: str | None, action: str,
                    target_type: str, target_id: str, detail: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), actor_id if actor_type == "MEMBER" else None,
             actor_type, action, target_type, target_id,
             json.dumps(detail, ensure_ascii=False), now_iso()),
        )
        self.conn.commit()

    def login(self, email: str, password: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT * FROM members WHERE email = ?", (email,)).fetchone()
        if not row or not hmac.compare_digest(row["passwordHash"], hash_pw(password, row["salt"])):
            self.write_audit("SYSTEM", None, "MEMBER_LOGIN_FAILED", "ENDPOINT", "/api/auth/login",
                             {"emailMasked": email[:2] + "***", "reason": "INVALID_CREDENTIALS"})
            raise ApiHttpError(401, "Sai thông tin đăng nhập")
        token = issue_jwt(row["id"], row["role"])
        self.write_audit("MEMBER", row["id"], "MEMBER_LOGIN_SUCCEEDED", "MEMBER", row["id"],
                         {"role": row["role"]})
        return {"accessToken": token, "role": row["role"], "memberId": row["id"], "expiresIn": JWT_TTL_SECONDS}

    def require_role(self, claims: dict[str, Any], allowed: set[str], method: str, path: str) -> None:
        if claims.get("role") not in allowed:
            self.write_audit("MEMBER", claims["sub"], "ACCESS_DENIED", "ENDPOINT", path,
                             {"method": method, "actualRole": claims.get("role"),
                              "requiredRoles": sorted(allowed), "reason": "ROLE_NOT_ALLOWED"})
            raise ApiHttpError(403, "Không đủ quyền thực hiện thao tác này", {"code": "ROLE_NOT_ALLOWED"})

    def upload_firmware(self, claims: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        self.require_role(claims, {"DEVELOPER"}, "POST", "/api/firmware")
        fw_id = f"fw-{uuid.uuid4().hex[:8]}"
        v_no = body["versionNo"]
        parts = [int(p) for p in v_no.lstrip("v").split(".")]
        v_code = parts[0] * 10000 + parts[1] * 100 + parts[2]
        min_no = body.get("minRequiredVersion", "2.3.0")
        mp = [int(p) for p in min_no.lstrip("v").split(".")]
        min_code = mp[0] * 10000 + mp[1] * 100 + mp[2]
        try:
            self.conn.execute(
                "INSERT INTO firmware_versions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fw_id, body["model"], v_no, v_code, body.get("releaseNotes", ""),
                 body["checksum"], body["fileUrl"], min_no, min_code, "UPLOADED",
                 claims["sub"], None, now_iso()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ApiHttpError(409, f"Xung đột hoặc sai khoảng phiên bản: {exc}") from exc
        self.write_audit("MEMBER", claims["sub"], "FIRMWARE_UPLOADED", "FIRMWARE", fw_id,
                         {"model": body["model"], "versionNo": v_no, "checksum": body["checksum"]})
        return {"id": fw_id, "status": "UPLOADED", "versionCode": v_code}

    def approve_firmware(self, claims: dict[str, Any], fw_id: str) -> dict[str, Any]:
        self.require_role(claims, {"QA"}, "PATCH", f"/api/firmware/{fw_id}/approve")
        fw = self.conn.execute("SELECT * FROM firmware_versions WHERE id = ?", (fw_id,)).fetchone()
        if not fw:
            raise ApiHttpError(404, "Không tìm thấy firmware")
        if fw["uploadedBy"] == claims["sub"]:
            self.write_audit("MEMBER", claims["sub"], "FIRMWARE_APPROVAL_DENIED", "FIRMWARE", fw_id,
                             {"reason": "FOUR_EYES_VIOLATION", "uploadedBy": fw["uploadedBy"]})
            raise ApiHttpError(403, "Vi phạm nguyên tắc 4-mắt: không được tự duyệt firmware mình tải lên",
                               {"code": "FOUR_EYES_VIOLATION"})
        if fw["status"] != "UPLOADED":
            raise ApiHttpError(409, f"Trạng thái hiện tại {fw['status']} không thể duyệt", {"code": "INVALID_STATE"})
        self.conn.execute(
            "UPDATE firmware_versions SET status = 'APPROVED', approvedBy = ? WHERE id = ?",
            (claims["sub"], fw_id),
        )
        self.conn.commit()
        self.write_audit("MEMBER", claims["sub"], "FIRMWARE_APPROVED", "FIRMWARE", fw_id,
                         {"before": {"status": "UPLOADED"}, "after": {"status": "APPROVED"},
                          "uploadedBy": fw["uploadedBy"], "approvedBy": claims["sub"]})
        return {"id": fw_id, "status": "APPROVED", "approvedBy": claims["sub"]}

    def deprecate_firmware(self, claims: dict[str, Any], fw_id: str, reason: str) -> dict[str, Any]:
        self.require_role(claims, {"ADMIN"}, "PATCH", f"/api/firmware/{fw_id}/deprecate")
        fw = self.conn.execute("SELECT * FROM firmware_versions WHERE id = ?", (fw_id,)).fetchone()
        if not fw:
            raise ApiHttpError(404, "Không tìm thấy firmware")
        if fw["status"] == "DEPRECATED":
            raise ApiHttpError(409, "Firmware đã bị thu hồi trước đó")
        self.conn.execute("UPDATE firmware_versions SET status = 'DEPRECATED' WHERE id = ?", (fw_id,))
        self.conn.commit()
        self.write_audit("MEMBER", claims["sub"], "FIRMWARE_DEPRECATED", "FIRMWARE", fw_id,
                         {"before": {"status": fw["status"]}, "after": {"status": "DEPRECATED"}, "reason": reason})
        return {"id": fw_id, "status": "DEPRECATED"}

    def create_and_start_campaign(self, claims: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        self.require_role(claims, {"OPERATOR"}, "POST", "/api/campaigns")
        mode = body.get("mode", "UPGRADE")
        fw = self.conn.execute("SELECT * FROM firmware_versions WHERE id = ?", (body["firmwareId"],)).fetchone()
        if not fw or fw["status"] != "APPROVED":
            raise ApiHttpError(409, "Chỉ được chọn firmware ở trạng thái APPROVED", {"code": "FIRMWARE_NOT_APPROVED"})

        cmp_id = f"cmp-{uuid.uuid4().hex[:8]}"
        wave_id = f"wv-{uuid.uuid4().hex[:6]}"
        ts = now_iso()
        self.conn.execute(
            "INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (cmp_id, body["name"], fw["id"], body["targetGroupId"], "RUNNING",
             body.get("failureThresholdPercent", 5.0), body.get("maxConcurrentDevices", 500),
             claims["sub"], None, ts, None),
        )
        self.conn.execute(
            "INSERT INTO campaign_waves VALUES (?,?,?,?,?,?,?,?,?)",
            (wave_id, cmp_id, 1, 100.0, 95.0, "RUNNING", "2026-11-25T23:59:59Z", ts, None),
        )

        created_tasks = 0
        if mode == "ROLLBACK":
            bad_fw_id = body["badFirmwareId"]
            devices = self.conn.execute(
                """SELECT d.id, d.currentFirmwareId
                     FROM devices d
                    WHERE d.groupId = ? AND d.model = ? AND d.currentFirmwareId = ?""",
                (body["targetGroupId"], fw["model"], bad_fw_id),
            ).fetchall()
            for d in devices:
                hist = self.conn.execute(
                    """SELECT h.firmwareId FROM device_firmware_histories h
                         JOIN firmware_versions f ON f.id = h.firmwareId
                        WHERE h.deviceId = ? AND h.firmwareId <> ? AND f.status = 'APPROVED'
                        ORDER BY h.installedAt DESC LIMIT 1""",
                    (d["id"], bad_fw_id),
                ).fetchone()
                to_fw = hist["firmwareId"] if hist else fw["id"]
                self.conn.execute(
                    "INSERT INTO device_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"tsk-{uuid.uuid4().hex[:8]}", cmp_id, wave_id, d["id"],
                     d["currentFirmwareId"], to_fw, "PENDING", 0, None, None, None, None, None),
                )
                created_tasks += 1
            action_name = "ROLLBACK_CAMPAIGN_CREATED"
        else:
            devices = self.conn.execute(
                """SELECT d.id, d.currentFirmwareId, cf.versionCode AS curCode
                     FROM devices d JOIN firmware_versions cf ON cf.id = d.currentFirmwareId
                    WHERE d.groupId = ? AND d.model = ?
                      AND cf.versionCode >= ? AND cf.versionCode < ?""",
                (body["targetGroupId"], fw["model"], fw["minRequiredVersionCode"], fw["versionCode"]),
            ).fetchall()
            for d in devices:
                try:
                    self.conn.execute(
                        "INSERT INTO device_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (f"tsk-{uuid.uuid4().hex[:8]}", cmp_id, wave_id, d["id"],
                         d["currentFirmwareId"], fw["id"], "PENDING", 0, None, None, None, None, None),
                    )
                    created_tasks += 1
                except sqlite3.IntegrityError as exc:
                    raise ApiHttpError(409, "Thiết bị đang có tác vụ cập nhật khác hoạt động",
                                       {"code": "CONCURRENT_ACTIVE_TASK"}) from exc
            action_name = "CAMPAIGN_STARTED"

        self.conn.commit()
        self.write_audit("MEMBER", claims["sub"], action_name, "CAMPAIGN", cmp_id,
                         {"mode": mode, "firmwareId": fw["id"], "tasksCreated": created_tasks})
        return {"campaignId": cmp_id, "waveId": wave_id, "mode": mode, "tasksCreated": created_tasks}

    def verify_device_headers(self, headers: dict[str, str], method: str, path: str, raw_body: bytes) -> sqlite3.Row:
        serial = headers.get("x-device-serial")
        ts_str = headers.get("x-timestamp")
        nonce = headers.get("x-nonce")
        sig = headers.get("x-signature")
        if not serial or not ts_str or not nonce or not sig:
            self.write_audit("DEVICE", None, "DEVICE_AUTH_FAILED", "ENDPOINT", path,
                             {"reason": "MISSING_AUTH_HEADERS"})
            raise ApiHttpError(401, "Thiếu header xác thực HMAC thiết bị", {"reason": "MISSING_AUTH_HEADERS"})
        try:
            ts_int = int(ts_str)
        except ValueError as exc:
            raise ApiHttpError(401, "Timestamp không hợp lệ", {"reason": "INVALID_TIMESTAMP"}) from exc
        if abs(int(time.time()) - ts_int) > HMAC_WINDOW_SECONDS:
            self.write_audit("DEVICE", None, "DEVICE_AUTH_FAILED", "DEVICE", serial,
                             {"serialNoClaimed": serial, "reason": "TIMESTAMP_OUT_OF_WINDOW"})
            raise ApiHttpError(401, "Timestamp nằm ngoài cửa sổ ±300s", {"reason": "TIMESTAMP_OUT_OF_WINDOW"})

        row = self.conn.execute(
            """SELECT d.*, c.secret FROM devices d
                 JOIN device_credentials c ON c.deviceId = d.id
                WHERE d.serialNo = ?""",
            (serial,),
        ).fetchone()
        expected = sign_device_hmac(row["secret"] if row else "dummy-unknown-secret",
                                    serial, ts_str, nonce, method, path, raw_body)
        if row is None or not hmac.compare_digest(expected, sig):
            self.write_audit("DEVICE", None, "DEVICE_AUTH_FAILED", "DEVICE", serial,
                             {"serialNoClaimed": serial, "reason": "INVALID_SIGNATURE"})
            raise ApiHttpError(401, "Xác thực chữ ký HMAC thất bại", {"reason": "INVALID_SIGNATURE"})

        now_m = time.monotonic()
        key = (serial, nonce)
        if key in self.nonce_cache and self.nonce_cache[key] > now_m:
            self.write_audit("DEVICE", None, "DEVICE_AUTH_FAILED", "DEVICE", row["id"],
                             {"serialNo": serial, "reason": "NONCE_REUSED"})
            raise ApiHttpError(401, "Nonce đã được sử dụng (chặn Replay Attack)", {"reason": "NONCE_REUSED"})
        self.nonce_cache[key] = now_m + 600.0
        return row

    def device_checkin(self, dev: sqlite3.Row, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("serialNo") != dev["serialNo"]:
            raise ApiHttpError(403, "serialNo trong body không khớp chữ ký", {"code": "SERIAL_MISMATCH"})
        ts = now_iso()
        self.conn.execute("UPDATE devices SET lastCheckInAt = ?, connectivity = 'ONLINE' WHERE id = ?",
                          (ts, dev["id"]))
        task = self.conn.execute(
            """SELECT t.*, fw.versionNo AS targetVersion, fw.checksum, fw.fileUrl
                 FROM device_tasks t
                 JOIN campaigns c ON c.id = t.campaignId
                 JOIN firmware_versions fw ON fw.id = t.toFirmwareId
                WHERE t.deviceId = ? AND c.status = 'RUNNING'
                  AND t.status IN ('PENDING','DOWNLOADING','INSTALLING','VERIFYING')
                LIMIT 1""",
            (dev["id"],),
        ).fetchone()
        if not task:
            self.conn.commit()
            return {"action": "NO_TASK", "nextCheckInSeconds": 300, "serverTime": ts}

        attempt = task["attemptCount"]
        if task["status"] == "PENDING":
            attempt += 1
            self.conn.execute(
                """UPDATE device_tasks
                      SET status = 'DOWNLOADING', attemptCount = ?, startedAt = ?, lastHeartbeatAt = ?
                    WHERE id = ?""",
                (attempt, ts, ts, task["id"]),
            )
            self.conn.commit()
            self.write_audit("SYSTEM", None, "DEVICE_TASK_STATE_CHANGED", "DEVICE_TASK", task["id"],
                             {"before": "PENDING", "after": "DOWNLOADING", "attempt": attempt})
        else:
            self.conn.commit()

        return {
            "action": "UPDATE",
            "taskId": task["id"],
            "attempt": attempt,
            "targetVersion": task["targetVersion"],
            "checksum": task["checksum"],
            "downloadUrl": f"{task['fileUrl']}?X-Expires=900&sig=presigned-demo",
            "nextCheckInSeconds": 300,
        }

    def device_report(self, dev: sqlite3.Row, task_id: str, body: dict[str, Any]) -> dict[str, Any]:
        task = self.conn.execute("SELECT * FROM device_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise ApiHttpError(404, "Không tìm thấy task")
        if task["deviceId"] != dev["id"]:
            raise ApiHttpError(403, "Task không thuộc thiết bị này", {"code": "TASK_NOT_OWNED"})

        stage = body.get("stage")
        ts = now_iso()
        cur = task["status"]
        transitions = {
            ("DOWNLOADING", "DOWNLOADED"): "INSTALLING",
            ("DOWNLOADING", "INSTALLING"): "INSTALLING",
            ("INSTALLING", "VERIFYING"): "VERIFYING",
            ("VERIFYING", "SUCCESS"): "SUCCESS",
        }
        # Idempotent duplicate
        if (stage in ("DOWNLOADED", "INSTALLING") and cur == "INSTALLING") or (stage == cur):
            return {"taskId": task_id, "status": cur, "idempotentDuplicate": True}

        nxt = transitions.get((cur, stage))
        if not nxt:
            raise ApiHttpError(409, f"Chuyển trạng thái không hợp lệ: {cur} -> {stage}",
                               {"code": "INVALID_TRANSITION"})

        if nxt == "SUCCESS":
            new_bank = "B" if dev["activePartition"] == "A" else "A"
            self.conn.execute(
                "UPDATE device_tasks SET status = 'SUCCESS', finishedAt = ?, lastHeartbeatAt = ? WHERE id = ?",
                (ts, ts, task_id),
            )
            self.conn.execute(
                "UPDATE devices SET currentFirmwareId = ?, activePartition = ? WHERE id = ?",
                (task["toFirmwareId"], new_bank, dev["id"]),
            )
            self.conn.execute(
                "INSERT INTO device_firmware_histories VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), dev["id"], task["toFirmwareId"], task_id, ts),
            )
        else:
            self.conn.execute(
                "UPDATE device_tasks SET status = ?, lastHeartbeatAt = ? WHERE id = ?",
                (nxt, ts, task_id),
            )
        self.conn.commit()
        self.write_audit("DEVICE", None, "DEVICE_TASK_STAGE_REPORTED", "DEVICE_TASK", task_id,
                         {"serialNo": dev["serialNo"], "before": cur, "after": nxt, "stage": stage})
        return {"taskId": task_id, "status": nxt, "idempotentDuplicate": False}

    def list_audits(self, claims: dict[str, Any]) -> list[dict[str, Any]]:
        self.require_role(claims, {"ADMIN"}, "GET", "/api/audit-logs")
        rows = self.conn.execute("SELECT * FROM audit_logs ORDER BY createdAt DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]


OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "DASAN Firmware Rollout Platform — Security, Rollback & AI Validator Demo",
        "version": "1.0.0",
        "description": "Demo tương tác phần Thành viên D (JWT + RBAC 4 vai trò, Four-Eyes 403, Emergency Rollback, HMAC 6 thành phần chống Replay, Audit Append-only & AI Validator).",
    },
    "components": {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    },
    "paths": {
        "/api/auth/login": {
            "post": {
                "summary": "Đăng nhập nhận JWT (admin/dev/qa1/operator@dasan.local)",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"example": {"email": "qa1@dasan.local", "password": "Qa1@123"}}},
                },
                "responses": {"200": {"description": "Cấp JWT thành công"}, "401": {"description": "Sai thông tin"}},
            }
        },
        "/api/firmware": {
            "post": {
                "summary": "Upload metadata firmware (chỉ DEVELOPER)",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"example": {
                        "model": "DASAN-H660GM", "versionNo": "2.4.1",
                        "checksum": "sha256-v241-demo", "fileUrl": "https://cdn.dasan.local/fw/h660gm-2.4.1.bin",
                        "minRequiredVersion": "2.3.0", "releaseNotes": "Fix PON stability"
                    }}},
                },
                "responses": {"201": {"description": "UPLOADED"}, "403": {"description": "ROLE_NOT_ALLOWED"}},
            }
        },
        "/api/firmware/{id}/approve": {
            "patch": {
                "summary": "Phê duyệt 4-mắt (chỉ QA, uploadedBy != approvedBy)",
                "security": [{"BearerAuth": []}],
                "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "APPROVED"}, "403": {"description": "FOUR_EYES_VIOLATION"}},
            }
        },
        "/api/campaigns": {
            "post": {
                "summary": "Tạo & chạy Campaign nâng cấp hoặc ROLLBACK (chỉ OPERATOR)",
                "security": [{"BearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"example": {
                        "name": "Rollout H660GM 2.4.1", "firmwareId": "fw-...",
                        "targetGroupId": "grp-hanoi", "mode": "UPGRADE"
                    }}},
                },
                "responses": {"201": {"description": "RUNNING"}},
            }
        },
        "/api/audit-logs": {
            "get": {
                "summary": "Tra cứu nhật ký kiểm toán bất biến (chỉ ADMIN)",
                "security": [{"BearerAuth": []}],
                "responses": {"200": {"description": "Danh sách audit_logs"}},
            }
        },
        "/api/ai/validate": {
            "post": {
                "summary": "Kiểm định JSON đầu ra của AI bằng validate_output.py (2 tầng)",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"example": {
                        "output": validate_output._fixture_valid_output(),
                        "input": validate_output._fixture_input(),
                    }}},
                },
                "responses": {"200": {"description": "HỢP LỆ"}, "422": {"description": "Bị Validator bác bỏ"}},
            }
        },
    },
}

SWAGGER_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>DASAN Firmware Rollout — Swagger UI Demo</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger-ui' });
    };
  </script>
</body>
</html>
"""


def make_handler(store: PlatformStore):
    class DemoHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send_json(self, code: int, message: str, data: Any) -> None:
            payload = json.dumps({"status": code, "message": message, "data": data}, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _jwt_claims(self) -> dict[str, Any]:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise ApiHttpError(401, "Thiếu Bearer JWT token", {"reason": "MISSING_TOKEN"})
            return verify_jwt(auth[7:].strip())

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path in ("/", "/docs"):
                    raw = SWAGGER_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if parsed.path == "/openapi.json":
                    raw = json.dumps(OPENAPI_SPEC, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if parsed.path == "/api/audit-logs":
                    claims = self._jwt_claims()
                    self._send_json(200, "success", {"items": store.list_audits(claims)})
                    return
                raise ApiHttpError(404, "Endpoint không tồn tại")
            except ApiHttpError as exc:
                self._send_json(exc.status, exc.message, exc.data)

        def do_POST(self) -> None:
            self._handle_body("POST")

        def do_PATCH(self) -> None:
            self._handle_body("PATCH")

        def _handle_body(self, method: str) -> None:
            parsed = urllib.parse.urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
                if method == "POST" and parsed.path == "/api/auth/login":
                    self._send_json(200, "success", store.login(body.get("email", ""), body.get("password", "")))
                    return
                if method == "POST" and parsed.path == "/api/firmware":
                    self._send_json(201, "created", store.upload_firmware(self._jwt_claims(), body))
                    return
                if method == "PATCH" and parsed.path.startswith("/api/firmware/") and parsed.path.endswith("/approve"):
                    fw_id = parsed.path.split("/")[3]
                    self._send_json(200, "success", store.approve_firmware(self._jwt_claims(), fw_id))
                    return
                if method == "PATCH" and parsed.path.startswith("/api/firmware/") and parsed.path.endswith("/deprecate"):
                    fw_id = parsed.path.split("/")[3]
                    self._send_json(200, "success", store.deprecate_firmware(self._jwt_claims(), fw_id, body.get("reason", "")))
                    return
                if method == "POST" and parsed.path == "/api/campaigns":
                    self._send_json(201, "created", store.create_and_start_campaign(self._jwt_claims(), body))
                    return
                if method == "POST" and parsed.path == "/api/device-agent/check-in":
                    hdrs = {k.lower(): v for k, v in self.headers.items()}
                    dev = store.verify_device_headers(hdrs, "POST", parsed.path, raw)
                    self._send_json(200, "success", store.device_checkin(dev, body))
                    return
                if method == "POST" and parsed.path.startswith("/api/device-agent/tasks/") and parsed.path.endswith("/result"):
                    hdrs = {k.lower(): v for k, v in self.headers.items()}
                    dev = store.verify_device_headers(hdrs, "POST", parsed.path, raw)
                    task_id = parsed.path.split("/")[4]
                    self._send_json(200, "success", store.device_report(dev, task_id, body))
                    return
                if method == "POST" and parsed.path == "/api/ai/validate":
                    res = validate_output.validate_document(body.get("output"), body.get("input"))
                    self._send_json(200 if res["valid"] else 422,
                                    "valid" if res["valid"] else "rejected", res)
                    return
                raise ApiHttpError(404, "Endpoint không tồn tại")
            except ApiHttpError as exc:
                self._send_json(exc.status, exc.message, exc.data)

    return DemoHandler


def run_self_test() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 86)
    print("KIỂM THỬ TỰ ĐỘNG END-TO-END — RBAC, FOUR-EYES, HMAC REPLAY, ROLLBACK & AUDIT IMMUTABLE")
    print("=" * 86)
    store = PlatformStore(":memory:")

    # 1. Login 4 vai trò
    dev_tok = store.login("dev@dasan.local", "Dev@123")
    qa_tok = store.login("qa1@dasan.local", "Qa1@123")
    op_tok = store.login("operator@dasan.local", "Op@123")
    adm_tok = store.login("admin@dasan.local", "Admin@123")
    dev_claims = verify_jwt(dev_tok["accessToken"])
    qa_claims = verify_jwt(qa_tok["accessToken"])
    op_claims = verify_jwt(op_tok["accessToken"])
    adm_claims = verify_jwt(adm_tok["accessToken"])
    print("[PASS 1] Đăng nhập JWT cho 4 vai trò (DEVELOPER, QA, OPERATOR, ADMIN)")

    # 2. Chặn OPERATOR gọi API upload firmware của DEVELOPER -> 403
    try:
        store.upload_firmware(op_claims, {"model": "DASAN-H660GM", "versionNo": "2.4.1",
                                          "checksum": "sha256-241", "fileUrl": "https://cdn/241.bin"})
        raise AssertionError("Phải chặn OPERATOR upload")
    except ApiHttpError as exc:
        assert exc.status == 403 and exc.data.get("code") == "ROLE_NOT_ALLOWED"
    print("[PASS 2] RBAC chặn OPERATOR upload firmware -> 403 ROLE_NOT_ALLOWED (+ ghi audit ACCESS_DENIED)")

    # 3. DEVELOPER upload v2.4.1 -> kiểm tra Four-Eyes (giả sử cùng actorId duyệt -> 403 FOUR_EYES_VIOLATION)
    fw = store.upload_firmware(dev_claims, {
        "model": "DASAN-H660GM", "versionNo": "2.4.1",
        "checksum": "sha256-v241-good", "fileUrl": "https://cdn.dasan.local/fw/2.4.1.bin",
        "minRequiredVersion": "2.3.0",
    })
    # Giả lập người upload có role QA (dual-hat) vẫn bị chặn bởi uploadedBy != approvedBy
    same_person_qa = {"sub": dev_claims["sub"], "role": "QA"}
    try:
        store.approve_firmware(same_person_qa, fw["id"])
        raise AssertionError("Phải chặn tự duyệt Four-Eyes")
    except ApiHttpError as exc:
        assert exc.status == 403 and exc.data.get("code") == "FOUR_EYES_VIOLATION"
    # QA độc lập duyệt thành công
    approved = store.approve_firmware(qa_claims, fw["id"])
    assert approved["status"] == "APPROVED"
    print("[PASS 3] Nguyên tắc 4-mắt chặn tự duyệt (403 FOUR_EYES_VIOLATION) & cho phép QA độc lập duyệt")

    # 4. OPERATOR tạo & chạy Campaign nâng cấp v2.3.0 -> v2.4.1
    cmp_up = store.create_and_start_campaign(op_claims, {
        "name": "Upgrade H660GM to 2.4.1", "firmwareId": fw["id"],
        "targetGroupId": "grp-hanoi", "mode": "UPGRADE",
    })
    assert cmp_up["tasksCreated"] == 2
    print(f"[PASS 4] OPERATOR mở chiến dịch nâng cấp -> sinh {cmp_up['tasksCreated']} device_tasks PENDING")

    # 5. Thiết bị DSN-H660-0001 check-in bằng HMAC 6 thành phần & thử Replay cùng Nonce -> 401 NONCE_REUSED
    checkin_body = json.dumps({"serialNo": "DSN-H660-0001", "currentVersion": "2.3.0"}).encode("utf-8")
    ts = str(int(time.time()))
    nonce = "nonce-unique-0001"
    sig = sign_device_hmac("demo-secret-0001-not-real", "DSN-H660-0001", ts, nonce,
                           "POST", "/api/device-agent/check-in", checkin_body)
    hdrs = {"x-device-serial": "DSN-H660-0001", "x-timestamp": ts, "x-nonce": nonce, "x-signature": sig}
    dev_row = store.verify_device_headers(hdrs, "POST", "/api/device-agent/check-in", checkin_body)
    ci_res = store.device_checkin(dev_row, json.loads(checkin_body))
    assert ci_res["action"] == "UPDATE" and ci_res["targetVersion"] == "2.4.1"
    try:
        store.verify_device_headers(hdrs, "POST", "/api/device-agent/check-in", checkin_body)
        raise AssertionError("Phải chặn Replay cùng Nonce")
    except ApiHttpError as exc:
        assert exc.status == 401 and exc.data.get("reason") == "NONCE_REUSED"
    print("[PASS 5] Thiết bị check-in HMAC-SHA256 6 thành phần nhận Pre-signed URL; chặn Replay Nonce -> 401")

    # 6. Thiết bị hoàn tất DOWNLOADED -> VERIFYING -> SUCCESS (kèm kiểm tra Idempotency gửi trùng)
    task_id = ci_res["taskId"]
    r1 = store.device_report(dev_row, task_id, {"stage": "DOWNLOADED"})
    r1_dup = store.device_report(dev_row, task_id, {"stage": "DOWNLOADED"})
    assert r1["status"] == "INSTALLING" and r1_dup["idempotentDuplicate"] is True
    store.device_report(dev_row, task_id, {"stage": "VERIFYING"})
    r_ok = store.device_report(dev_row, task_id, {"stage": "SUCCESS"})
    assert r_ok["status"] == "SUCCESS"
    print("[PASS 6] Máy trạng thái Device Task: DOWNLOADING -> INSTALLING (lũy đẳng) -> VERIFYING -> SUCCESS")

    # 7. Điểm cộng #13: Phát hiện lỗi hậu triển khai -> ADMIN deprecate v2.4.1 & OPERATOR tạo Rollback Campaign
    store.deprecate_firmware(adm_claims, fw["id"], "Phát hiện rò bộ nhớ PPPoE sau 72h")
    cmp_rb = store.create_and_start_campaign(op_claims, {
        "name": "Emergency Rollback from 2.4.1",
        "firmwareId": "fw-230",          # Safe anchor APPROVED
        "badFirmwareId": fw["id"],       # Chỉ lùi máy đang ở 2.4.1 (DSN-H660-0001; DSN-H660-0002 vẫn ở 2.3.0 nên bỏ qua)
        "targetGroupId": "grp-hanoi",
        "mode": "ROLLBACK",
    })
    assert cmp_rb["tasksCreated"] == 1
    print("[PASS 7] Emergency Rollback (#13): ADMIN thu hồi v2.4.1 + chỉ tạo task quay lui cho đúng 1 máy đang ở 2.4.1")

    # 8. Kiểm chứng Trigger Append-Only trên bảng audit_logs (cấm UPDATE & DELETE kể cả ở tầng SQL)
    audits = store.list_audits(adm_claims)
    assert len(audits) >= 10
    for sql_attack in ("UPDATE audit_logs SET action = 'TAMPERED'", "DELETE FROM audit_logs"):
        try:
            store.conn.execute(sql_attack)
            raise AssertionError("Phải chặn sửa/xóa audit_logs")
        except sqlite3.IntegrityError:
            pass
    print(f"[PASS 8] Bảng audit_logs ghi nhận {len(audits)} sự kiện và chặn tuyệt đối UPDATE/DELETE bằng Trigger DB")

    # 9. Kiểm chứng tích hợp AI Validator trên output thật Prompt v2 (Sample 05 Prompt Injection)
    sample5_in = json.loads((THIS_DIR / "ai-samples" / "05_hard_input_injection.json").read_text(encoding="utf-8"))
    sample5_out = json.loads((THIS_DIR / "ai-outputs" / "v2" / "05_out_v2.json").read_text(encoding="utf-8"))
    val = validate_output.validate_document(sample5_out, sample5_in)
    assert val["valid"] is True and len(val["errors"]) == 0
    print("[PASS 9] Cổng kiểm định AI chấp nhận Output thật Prompt v2 (Sample 05 chống Prompt Injection)")
    print("=" * 86)
    print("KẾT QUẢ: 9 / 9 KỊCH BẢN PASS HOÀN TOÀN!")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DASAN Firmware Rollout — Mock Platform & Swagger Demo")
    parser.add_argument("--port", type=int, default=8080, help="Cổng chạy HTTP Swagger UI (mặc định 8080)")
    parser.add_argument("--self-test", action="store_true", help="Chạy kiểm thử tự động 9 kịch bản rồi thoát")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    store = PlatformStore(":memory:")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store))
    print(f"Swagger UI đang chạy tại: http://localhost:{args.port}/docs  (Nhấn Ctrl+C để dừng)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
