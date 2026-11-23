import sqlite3

from fastapi import APIRouter, Depends

from . import service, timeutil
from .auth import DeviceIdentity, verify_device
from .db import get_db
from .errors import ok
from .schemas import CheckInRequest, CheckInResponse, TaskResultRequest, TaskResultResponse

router = APIRouter(prefix="/api/device-agent", tags=["Device Agent"])

_ERRORS = {
    400: {"description": "Dữ liệu đầu vào không hợp lệ"},
    401: {"description": "Chữ ký HMAC sai / thiếu header / timestamp ngoài cửa sổ 5 phút"},
    403: {"description": "Thiết bị không có quyền với tài nguyên này"},
}


@router.post("/check-in", response_model=CheckInResponse,
             responses=_ERRORS,
             summary="Thiết bị báo danh định kỳ (PULL) và nhận task nếu có")
def check_in(req: CheckInRequest,
             device: DeviceIdentity = Depends(verify_device),
             conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return ok(service.check_in(conn, device, req, timeutil.now()))


@router.post("/tasks/{taskId}/result", response_model=TaskResultResponse,
             responses={**_ERRORS,
                        404: {"description": "Không tìm thấy task"},
                        409: {"description": "Chuyển trạng thái không hợp lệ / attempt cũ / sai phiên bản"}},
             summary="Thiết bị báo tiến độ hoặc kết quả cuối của một task (idempotent)")
def report_result(taskId: str, req: TaskResultRequest,
                  device: DeviceIdentity = Depends(verify_device),
                  conn: sqlite3.Connection = Depends(get_db)) -> dict:
    data = service.report_result(conn, device, taskId, req, timeutil.now())
    return ok(data, message="duplicate" if data["duplicate"] else "success")
