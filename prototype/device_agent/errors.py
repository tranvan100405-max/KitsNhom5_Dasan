from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, message: str, data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.data = data


def ok(data: Any, message: str = "success", status_code: int = 200) -> dict:
    return {"status": status_code, "message": message, "data": data}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": exc.status_code, "message": exc.message, "data": exc.data},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "error": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content={"status": 400, "message": "Dữ liệu đầu vào không hợp lệ", "data": errors},
        )
