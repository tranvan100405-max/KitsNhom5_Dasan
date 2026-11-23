import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import config, db, timeutil
from .errors import install_error_handlers
from .router import router
from .sweeper import sweep_timeouts

log = logging.getLogger("device_agent.sweeper")
SWEEP_INTERVAL_SECONDS = max(1.0, 30 / config.TIME_SCALE)


def _sweep_once() -> dict:
    conn = db.connect()
    try:
        return sweep_timeouts(conn, timeutil.now())
    finally:
        conn.close()


async def _sweeper_loop() -> None:
    while True:
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            result = await asyncio.to_thread(_sweep_once)
            if any(result.values()):
                log.warning("sweeper: %s", result)
        except Exception:
            log.exception("sweeper failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    conn = db.connect()
    db.init_schema(conn)
    conn.close()
    task = asyncio.create_task(_sweeper_loop())
    yield
    task.cancel()


app = FastAPI(
    title="DASAN Firmware Rollout - Device Agent API (prototype)",
    version="0.1.0",
    description="Prototype phần Thành viên B: check-in (PULL) và báo cáo kết quả task.",
    lifespan=lifespan,
)
install_error_handlers(app)
app.include_router(router)
