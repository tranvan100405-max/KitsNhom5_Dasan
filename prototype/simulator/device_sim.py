import argparse
import asyncio
import hashlib
import json
import random
import sqlite3
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

from device_agent import config
from device_agent.auth import signed_headers

WATCHDOG_MAX_BOOT_TRIES = 3


@dataclass
class Args:
    base_url: str
    db: str
    devices: int
    speed: float
    duration: float
    fail_download: float
    bad_checksum: float
    bootloop: float
    lost_response: float
    seed: int


@dataclass
class Stats:
    checkins: int = 0
    no_action: int = 0
    updates_started: int = 0
    reports_sent: int = 0
    duplicates_acked: int = 0
    conflicts_409: int = 0
    http_errors: int = 0
    outcomes: Counter = field(default_factory=Counter)
    checkin_gaps: list[float] = field(default_factory=list)


class SimDevice:
    def __init__(self, serial: str, secret: str, model: str, version: str,
                 client: httpx.AsyncClient, args: Args, stats: Stats, rng: random.Random):
        self.serial, self.secret, self.model = serial, secret, model
        self.banks = {"A": version, "B": None}
        self.active = "A"
        self.client, self.args, self.stats, self.rng = client, args, stats, rng
        self.last_checkin: float | None = None

    @property
    def version(self) -> str:
        return self.banks[self.active]

    @property
    def inactive(self) -> str:
        return "B" if self.active == "A" else "A"

    def _sim(self, seconds: float) -> float:
        return seconds / self.args.speed

    async def _post(self, path: str, payload: dict) -> httpx.Response | None:
        body = json.dumps(payload).encode()
        for _ in range(3):
            try:
                headers = signed_headers(self.serial, self.secret, "POST", path, body)
                return await self.client.post(path, content=body, headers=headers)
            except httpx.HTTPError:
                self.stats.http_errors += 1
                await asyncio.sleep(self._sim(5))
        return None

    async def report(self, task_id: str, attempt: int, stage: str,
                     error_code: str | None = None, error_message: str | None = None) -> dict | None:
        payload = {"attempt": attempt, "stage": stage, "reportedVersion": self.version,
                   "activePartition": self.active, "errorCode": error_code,
                   "errorMessage": error_message}
        path = f"/api/device-agent/tasks/{task_id}/result"
        sends = 2 if self.rng.random() < self.args.lost_response else 1
        result = None
        for i in range(sends):
            resp = await self._post(path, payload)
            self.stats.reports_sent += 1
            if resp is None:
                continue
            body = resp.json()
            if resp.status_code == 409:
                self.stats.conflicts_409 += 1
            elif resp.status_code == 200 and body["data"]["duplicate"] and i > 0:
                self.stats.duplicates_acked += 1
            result = body
        return result

    async def run(self, deadline: float) -> None:
        await asyncio.sleep(self.rng.uniform(0, config.CHECKIN_INTERVAL_SECONDS))
        while time.monotonic() < deadline:
            interval = await self.check_in()
            jitter = self.rng.uniform(-config.CHECKIN_JITTER_SECONDS, config.CHECKIN_JITTER_SECONDS)
            await asyncio.sleep(max(0.05, interval + jitter))

    async def check_in(self) -> float:
        now = time.monotonic()
        if self.last_checkin is not None:
            self.stats.checkin_gaps.append((now - self.last_checkin) * self.args.speed)
        self.last_checkin = now
        resp = await self._post("/api/device-agent/check-in", {
            "serialNo": self.serial, "model": self.model,
            "currentVersion": self.version, "activePartition": self.active})
        self.stats.checkins += 1
        if resp is None or resp.status_code != 200:
            return config.CHECKIN_INTERVAL_SECONDS
        data = resp.json()["data"]
        if data["action"] == "UPDATE":
            await self.perform_update(data["task"])
        else:
            self.stats.no_action += 1
        return data["nextCheckInSeconds"]

    async def perform_update(self, task: dict) -> None:
        tid, attempt, target = task["taskId"], task["attempt"], task["toVersion"]
        self.stats.updates_started += 1

        await asyncio.sleep(self._sim(10))
        if self.rng.random() < self.args.fail_download:
            self.stats.outcomes["download_interrupted"] += 1
            await self.report(tid, attempt, "FAILED", "ERR_DOWNLOAD_INTERRUPTED",
                              "Mất kết nối khi đang tải")
            return
        downloaded = hashlib.sha256(f"{self.model}-{target}".encode()).hexdigest()
        if self.rng.random() < self.args.bad_checksum:
            downloaded = "corrupted"
        if downloaded != task["checksum"]:
            self.stats.outcomes["checksum_mismatch"] += 1
            await self.report(tid, attempt, "FAILED", "ERR_CHECKSUM_MISMATCH",
                              "SHA-256 không khớp, bỏ file")
            return

        await self.report(tid, attempt, "DOWNLOADED")
        await asyncio.sleep(self._sim(5))
        await self.report(tid, attempt, "INSTALLING")
        await asyncio.sleep(self._sim(5))
        self.banks[self.inactive] = target
        await self.report(tid, attempt, "VERIFYING")

        bootloops = self.rng.random() < self.args.bootloop
        for _ in range(WATCHDOG_MAX_BOOT_TRIES):
            await asyncio.sleep(self._sim(10 / WATCHDOG_MAX_BOOT_TRIES))
            if not bootloops:
                break
        if bootloops:
            self.stats.outcomes["rolled_back"] += 1
            await self.report(tid, attempt, "ROLLED_BACK", "ERR_WATCHDOG_BOOT_TIMEOUT",
                              f"Watchdog: {WATCHDOG_MAX_BOOT_TRIES} lần boot lỗi trên bank {self.inactive}")
            return

        self.active = self.inactive
        self.stats.outcomes["success"] += 1
        await self.report(tid, attempt, "SUCCESS")


def load_devices(db_path: str, limit: int) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT d.serialNo, d.model, f.versionNo, c.secret FROM devices d"
        " JOIN device_credentials c ON c.deviceId = d.id"
        " JOIN firmware_versions f ON f.id = d.currentFirmwareId"
        " ORDER BY d.serialNo LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows


def db_summary(db_path: str) -> tuple[Counter, int]:
    conn = sqlite3.connect(db_path)
    by_status = Counter(dict(conn.execute(
        "SELECT status, COUNT(*) FROM device_tasks GROUP BY status").fetchall()))
    max_active = conn.execute(
        "SELECT COALESCE(MAX(n), 0) FROM (SELECT COUNT(*) n FROM device_tasks WHERE status IN"
        " ('PENDING','DOWNLOADING','INSTALLING','VERIFYING') GROUP BY deviceId)").fetchone()[0]
    conn.close()
    return by_status, max_active


def print_report(stats: Stats, args: Args) -> None:
    print("\n=== KẾT QUẢ MÔ PHỎNG (phía thiết bị) ===")
    print(f"Check-in: {stats.checkins} | không có việc: {stats.no_action} | "
          f"bắt đầu cập nhật: {stats.updates_started}")
    print(f"Báo cáo gửi: {stats.reports_sent} | báo cáo gửi lại được server nhận là trùng: "
          f"{stats.duplicates_acked} | 409: {stats.conflicts_409} | lỗi mạng: {stats.http_errors}")
    print(f"Kết cục từng lượt: {dict(stats.outcomes)}")
    if len(stats.checkin_gaps) >= 2:
        gaps = stats.checkin_gaps
        print(f"Khoảng cách giữa 2 lần check-in (quy về giây thật): min={min(gaps):.0f}s "
              f"avg={statistics.mean(gaps):.0f}s max={max(gaps):.0f}s "
              f"(kỳ vọng ~300s ±30s, cộng thời gian cập nhật nếu có)")

    by_status, max_active = db_summary(args.db)
    print("\n=== TRẠNG THÁI device_tasks TRONG DB (phía server) ===")
    for status, n in sorted(by_status.items()):
        print(f"  {status:<12} {n}")
    print(f"Số task đang chạy tối đa trên 1 thiết bị: {max_active} (phải <= 1)")


async def main_async(args: Args) -> None:
    rows = load_devices(args.db, args.devices)
    if not rows:
        raise SystemExit(f"Không có thiết bị trong {args.db}. Chạy `python -m device_agent.seed` trước.")
    stats = Stats()
    rng = random.Random(args.seed)
    deadline = time.monotonic() + args.duration
    async with httpx.AsyncClient(base_url=args.base_url, timeout=10) as client:
        devices = [SimDevice(r["serialNo"], r["secret"], r["model"], r["versionNo"],
                             client, args, stats, random.Random(rng.random())) for r in rows]
        print(f"Mô phỏng {len(devices)} thiết bị trong {args.duration:.0f}s "
              f"(x{args.speed:g} => ~{args.duration * args.speed / 60:.0f} phút thời gian thật)...")
        await asyncio.gather(*(d.run(deadline) for d in devices))
    print_report(stats, args)


def parse_args() -> Args:
    p = argparse.ArgumentParser(description="Mô phỏng thiết bị DASAN chạy Device Agent")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--db", default=config.DB_PATH)
    p.add_argument("--devices", type=int, default=50)
    p.add_argument("--duration", type=float, default=60, help="thời gian chạy (giây đồng hồ)")
    p.add_argument("--fail-download", type=float, default=0.05)
    p.add_argument("--bad-checksum", type=float, default=0.02)
    p.add_argument("--bootloop", type=float, default=0.05)
    p.add_argument("--lost-response", type=float, default=0.10)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    return Args(a.base_url, a.db, a.devices, config.TIME_SCALE, a.duration, a.fail_download,
                a.bad_checksum, a.bootloop, a.lost_response, a.seed)


def main() -> None:
    asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    main()
