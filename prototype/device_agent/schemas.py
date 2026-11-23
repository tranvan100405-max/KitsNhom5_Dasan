from typing import Literal

from pydantic import BaseModel, Field

Partition = Literal["A", "B"]
ReportStage = Literal["DOWNLOADED", "INSTALLING", "VERIFYING", "SUCCESS", "FAILED", "ROLLED_BACK"]


class CheckInRequest(BaseModel):
    serialNo: str = Field(min_length=1, max_length=64, examples=["DSN-H660-0001"])
    model: str = Field(min_length=1, max_length=64, examples=["DASAN-H660GM"])
    currentVersion: str = Field(min_length=1, max_length=32, examples=["2.3.0"])
    activePartition: Partition = Field(examples=["A"])


class TaskInfo(BaseModel):
    taskId: str
    attempt: int
    taskStatus: str
    toVersion: str
    downloadUrl: str
    urlExpiresAt: str
    checksum: str
    stateDeadlineAt: str | None


class CheckInData(BaseModel):
    action: Literal["UPDATE", "NO_TASK"]
    task: TaskInfo | None = None
    nextCheckInSeconds: float
    serverTime: str


class TaskResultRequest(BaseModel):
    attempt: int = Field(ge=1, examples=[1])
    stage: ReportStage = Field(examples=["SUCCESS"])
    reportedVersion: str = Field(min_length=1, max_length=32, examples=["2.4.1"])
    activePartition: Partition = Field(examples=["B"])
    errorCode: str | None = Field(default=None, max_length=64, examples=[None])
    errorMessage: str | None = Field(default=None, max_length=1000, examples=[None])


class TaskResultData(BaseModel):
    taskId: str
    status: str
    attempt: int
    duplicate: bool
    nextEligibleAt: str | None = None


class CheckInResponse(BaseModel):
    status: int
    message: str
    data: CheckInData


class TaskResultResponse(BaseModel):
    status: int
    message: str
    data: TaskResultData
