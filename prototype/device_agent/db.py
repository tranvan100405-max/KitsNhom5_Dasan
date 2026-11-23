import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from . import config

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS members (
    id          TEXT PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('ADMIN','DEVELOPER','QA','OPERATOR')),
    createdAt   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_groups (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    customerName TEXT NOT NULL,
    region       TEXT,
    timezone          TEXT,
    maintenanceWindow TEXT
);

CREATE TABLE IF NOT EXISTS firmware_versions (
    id                 TEXT PRIMARY KEY,
    model              TEXT NOT NULL,
    versionNo          TEXT NOT NULL,
    versionCode        INTEGER NOT NULL,
    releaseNotes       TEXT,
    checksum           TEXT NOT NULL,
    fileUrl            TEXT NOT NULL,
    minRequiredVersion TEXT,
    minRequiredVersionCode INTEGER,
    status             TEXT NOT NULL CHECK (status IN ('UPLOADED','APPROVED','DEPRECATED')),
    uploadedBy         TEXT NOT NULL REFERENCES members(id),
    approvedBy         TEXT REFERENCES members(id),
    createdAt          TEXT NOT NULL,
    UNIQUE (model, versionNo)
);

CREATE TABLE IF NOT EXISTS devices (
    id                TEXT PRIMARY KEY,
    serialNo          TEXT NOT NULL UNIQUE,
    model             TEXT NOT NULL,
    deviceType        TEXT NOT NULL CHECK (deviceType IN ('SWITCH','ROUTER','ONT','ONU')),
    groupId           TEXT NOT NULL REFERENCES device_groups(id),
    currentFirmwareId TEXT REFERENCES firmware_versions(id),
    connectivity      TEXT NOT NULL DEFAULT 'OFFLINE' CHECK (connectivity IN ('ONLINE','OFFLINE')),
    lastCheckInAt     TEXT,
    activePartition   TEXT NOT NULL DEFAULT 'A' CHECK (activePartition IN ('A','B'))
);

CREATE TABLE IF NOT EXISTS device_credentials (
    deviceId  TEXT PRIMARY KEY REFERENCES devices(id),
    secret    TEXT NOT NULL,
    createdAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                      TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    firmwareId              TEXT NOT NULL REFERENCES firmware_versions(id),
    targetGroupId           TEXT NOT NULL REFERENCES device_groups(id),
    status                  TEXT NOT NULL CHECK (status IN
                              ('DRAFT','SCHEDULED','RUNNING','PAUSED','COMPLETED','ABORTED')),
    failureThresholdPercent REAL NOT NULL,
    maxConcurrentDevices    INTEGER NOT NULL CHECK (maxConcurrentDevices > 0),
    createdBy               TEXT NOT NULL REFERENCES members(id),
    scheduledAt             TEXT,
    startedAt               TEXT,
    finishedAt              TEXT
);

CREATE TABLE IF NOT EXISTS campaign_waves (
    id                      TEXT PRIMARY KEY,
    campaignId              TEXT NOT NULL REFERENCES campaigns(id),
    waveOrder               INTEGER NOT NULL,
    rolloutPercentage       REAL NOT NULL,
    minSuccessRateToProceed REAL NOT NULL,
    status                  TEXT NOT NULL CHECK (status IN
                              ('PENDING','RUNNING','PAUSED','COMPLETED')),
    deadlineAt              TEXT,
    startedAt               TEXT,
    finishedAt              TEXT,
    UNIQUE (campaignId, waveOrder)
);

CREATE TABLE IF NOT EXISTS device_tasks (
    id              TEXT PRIMARY KEY,
    campaignId      TEXT NOT NULL REFERENCES campaigns(id),
    waveId          TEXT NOT NULL REFERENCES campaign_waves(id),
    deviceId        TEXT NOT NULL REFERENCES devices(id),
    fromFirmwareId  TEXT REFERENCES firmware_versions(id),
    toFirmwareId    TEXT NOT NULL REFERENCES firmware_versions(id),
    status          TEXT NOT NULL CHECK (status IN ('PENDING','DOWNLOADING','INSTALLING',
                      'VERIFYING','SUCCESS','FAILED','TIMEOUT','ROLLED_BACK')),
    attemptCount    INTEGER NOT NULL DEFAULT 1,
    errorCode       TEXT,
    errorMessage    TEXT,
    startedAt       TEXT,
    finishedAt      TEXT,
    lastHeartbeatAt TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_device_tasks_one_active_per_device
    ON device_tasks(deviceId)
    WHERE status IN ('PENDING','DOWNLOADING','INSTALLING','VERIFYING');

CREATE INDEX IF NOT EXISTS ix_device_tasks_campaign_status ON device_tasks(campaignId, status);
CREATE INDEX IF NOT EXISTS ix_device_tasks_wave_status     ON device_tasks(waveId, status);
CREATE INDEX IF NOT EXISTS ix_device_tasks_device_status   ON device_tasks(deviceId, status);

CREATE TABLE IF NOT EXISTS device_firmware_histories (
    id          TEXT PRIMARY KEY,
    deviceId    TEXT NOT NULL REFERENCES devices(id),
    firmwareId  TEXT NOT NULL REFERENCES firmware_versions(id),
    taskId      TEXT UNIQUE REFERENCES device_tasks(id),
    installedAt TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_histories_device ON device_firmware_histories(deviceId, installedAt);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(
        path or config.DB_PATH,
        isolation_level=None,
        check_same_thread=False,
        timeout=5.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
