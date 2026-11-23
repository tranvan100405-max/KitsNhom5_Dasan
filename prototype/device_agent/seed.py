import argparse
import hashlib
import math
import os
import secrets
import uuid

from . import config, db, timeutil

MODEL = "DASAN-H660GM"
OLD_VERSION = "1.9.0"
CURRENT_VERSION = "2.3.0"
TARGET_VERSION = "2.4.1"


def _id() -> str:
    return str(uuid.uuid4())


def version_code(version: str) -> int:
    major, minor, patch = (int(x) for x in version.split("."))
    return major * 10000 + minor * 100 + patch


def seed(conn, devices: int = 50, incompatible: int = 2, open_all_waves: bool = False,
         max_concurrent: int = 10, wave1_percent: float = 10.0) -> dict:
    now_dt = timeutil.now()
    now = timeutil.to_iso(now_dt)
    deadline = timeutil.to_iso(timeutil.plus_seconds(now_dt, config.DEFAULT_WAVE_DEADLINE_SECONDS))
    db.init_schema(conn)
    with db.transaction(conn):
        members = {role: _id() for role in ("ADMIN", "DEVELOPER", "QA", "OPERATOR")}
        for role, mid in members.items():
            conn.execute("INSERT INTO members VALUES (?,?,?,?,?)",
                         (mid, f"{role.lower()}@example.local", f"Demo {role.title()}", role, now))

        group_id = _id()
        conn.execute(
            "INSERT INTO device_groups (id, name, customerName, region, timezone, maintenanceWindow)"
            " VALUES (?,?,?,?,?,?)",
            (group_id, "ISP-Alpha FTTH Hanoi", "ISP Alpha (giả lập)", "Hanoi",
             "Asia/Ho_Chi_Minh", None))

        fw = {}
        for version, min_req in ((OLD_VERSION, None), (CURRENT_VERSION, OLD_VERSION),
                                 (TARGET_VERSION, CURRENT_VERSION)):
            fw[version] = _id()
            conn.execute(
                "INSERT INTO firmware_versions (id, model, versionNo, versionCode, releaseNotes,"
                " checksum, fileUrl, minRequiredVersion, minRequiredVersionCode, status,"
                " uploadedBy, approvedBy, createdAt) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (fw[version], MODEL, version, version_code(version),
                 f"Release notes {version} (giả lập)",
                 hashlib.sha256(f"{MODEL}-{version}".encode()).hexdigest(),
                 f"s3://firmware/{MODEL}/{version}.bin", min_req,
                 version_code(min_req) if min_req else None, "APPROVED",
                 members["DEVELOPER"], members["QA"], now),
            )

        campaign_id = _id()
        conn.execute(
            "INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (campaign_id, f"Rollout {TARGET_VERSION} - ISP Alpha", fw[TARGET_VERSION], group_id,
             "RUNNING", 5.0, max_concurrent, members["OPERATOR"], None, now, None),
        )
        wave_ids = [_id(), _id()]
        wave_sql = ("INSERT INTO campaign_waves (id, campaignId, waveOrder, rolloutPercentage,"
                    " minSuccessRateToProceed, status, deadlineAt, startedAt, finishedAt)"
                    " VALUES (?,?,?,?,?,?,?,?,?)")
        conn.execute(wave_sql, (wave_ids[0], campaign_id, 1, wave1_percent, 95.0, "RUNNING",
                                deadline, now, None))
        conn.execute(wave_sql, (wave_ids[1], campaign_id, 2, 100.0, 95.0,
                                "RUNNING" if open_all_waves else "PENDING",
                                deadline if open_all_waves else None,
                                now if open_all_waves else None, None))

        wave1_count = max(1, math.ceil(devices * wave1_percent / 100))
        credentials = []
        for i in range(devices):
            device_id = _id()
            serial = f"DSN-H660-{i + 1:04d}"
            version = OLD_VERSION if i >= devices - incompatible else CURRENT_VERSION
            secret = secrets.token_hex(16)
            conn.execute(
                "INSERT INTO devices (id, serialNo, model, deviceType, groupId, currentFirmwareId,"
                " connectivity, activePartition) VALUES (?,?,?,?,?,?,?,?)",
                (device_id, serial, MODEL, "ONT", group_id, fw[version], "OFFLINE", "A"),
            )
            conn.execute("INSERT INTO device_credentials VALUES (?,?,?)", (device_id, secret, now))
            conn.execute(
                "INSERT INTO device_tasks (id, campaignId, waveId, deviceId, fromFirmwareId,"
                " toFirmwareId, status, attemptCount) VALUES (?,?,?,?,?,?,?,?)",
                (_id(), campaign_id, wave_ids[0] if i < wave1_count else wave_ids[1], device_id,
                 fw[version], fw[TARGET_VERSION], "PENDING", 1),
            )
            credentials.append({"serialNo": serial, "secret": secret, "version": version})

    return {"campaignId": campaign_id, "waveIds": wave_ids, "firmware": fw,
            "groupId": group_id, "members": members, "devices": credentials}


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo DB giả lập cho prototype Device Agent")
    parser.add_argument("--devices", type=int, default=50)
    parser.add_argument("--incompatible", type=int, default=2,
                        help="số thiết bị đang ở firmware quá cũ (không đủ minRequiredVersion)")
    parser.add_argument("--max-concurrent", type=int, default=10)
    parser.add_argument("--open-all-waves", action="store_true")
    args = parser.parse_args()

    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    conn = db.connect()
    result = seed(conn, args.devices, args.incompatible, args.open_all_waves, args.max_concurrent)
    conn.close()
    print(f"Đã tạo {config.DB_PATH}: {args.devices} thiết bị {MODEL}, "
          f"campaign {CURRENT_VERSION} -> {TARGET_VERSION}, "
          f"maxConcurrentDevices={args.max_concurrent}, "
          f"wave 2 {'đang chạy' if args.open_all_waves else 'chưa mở'}.")


if __name__ == "__main__":
    main()
