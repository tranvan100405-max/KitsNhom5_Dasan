from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    INSTALLING = "INSTALLING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    ROLLED_BACK = "ROLLED_BACK"


S = TaskStatus

ACTIVE_STATUSES = frozenset({S.PENDING, S.DOWNLOADING, S.INSTALLING, S.VERIFYING})

IN_PROGRESS_STATUSES = frozenset({S.DOWNLOADING, S.INSTALLING, S.VERIFYING})

DOWNLOAD_SLOT_STATUSES = frozenset({S.DOWNLOADING})

TERMINAL_STATUSES = frozenset({S.SUCCESS, S.FAILED, S.TIMEOUT, S.ROLLED_BACK})

FAILURE_STATUSES = frozenset({S.FAILED, S.TIMEOUT, S.ROLLED_BACK})


class Stage(str, Enum):
    DOWNLOADED = "DOWNLOADED"
    INSTALLING = "INSTALLING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


STAGE_TO_STATUS: dict[Stage, TaskStatus] = {
    Stage.DOWNLOADED: S.INSTALLING,
    Stage.INSTALLING: S.INSTALLING,
    Stage.VERIFYING: S.VERIFYING,
    Stage.SUCCESS: S.SUCCESS,
    Stage.FAILED: S.FAILED,
    Stage.ROLLED_BACK: S.ROLLED_BACK,
}

ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    S.PENDING: frozenset({S.DOWNLOADING, S.FAILED, S.TIMEOUT}),
    S.DOWNLOADING: frozenset(
        {S.INSTALLING, S.VERIFYING, S.SUCCESS, S.FAILED, S.TIMEOUT, S.ROLLED_BACK}
    ),
    S.INSTALLING: frozenset({S.VERIFYING, S.SUCCESS, S.FAILED, S.TIMEOUT, S.ROLLED_BACK}),
    S.VERIFYING: frozenset({S.SUCCESS, S.ROLLED_BACK, S.TIMEOUT}),
    S.FAILED: frozenset({S.PENDING}),
    S.TIMEOUT: frozenset({S.PENDING, S.SUCCESS, S.ROLLED_BACK}),
    S.SUCCESS: frozenset(),
    S.ROLLED_BACK: frozenset(),
}

RECONCILE_SUCCESS_FROM = ACTIVE_STATUSES | {S.TIMEOUT}


class InvalidTransition(Exception):
    def __init__(self, current: TaskStatus, new: TaskStatus):
        super().__init__(f"Không thể chuyển trạng thái {current.value} -> {new.value}")
        self.current = current
        self.new = new


def is_duplicate(current: TaskStatus, new: TaskStatus) -> bool:
    return TaskStatus(current) == TaskStatus(new)


def can_transition(current: TaskStatus, new: TaskStatus) -> bool:
    return TaskStatus(new) in ALLOWED_TRANSITIONS[TaskStatus(current)]


def validate_transition(current: TaskStatus, new: TaskStatus) -> None:
    if not can_transition(current, new):
        raise InvalidTransition(TaskStatus(current), TaskStatus(new))
