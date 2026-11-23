# Prototype Device Agent API (Thành viên B)

Prototype phần **phía thiết bị** của nền tảng Firmware Rollout: check-in theo cơ chế PULL, máy trạng thái `device_tasks`, retry/timeout, hạn chót wave, đối soát và tính lũy đẳng. Bám quy ước Q1–Q10 trong [DASAN_OJT1_Team_Role_Assignment.md](../DASAN_OJT1_Team_Role_Assignment.md).
Thiết kế: [docs/member-b/DEVICE_AGENT_DESIGN.md](../docs/member-b/DEVICE_AGENT_DESIGN.md) · Quyết định code: [docs/member-b/DEVICE_AGENT_CODE_DECISIONS.md](../docs/member-b/DEVICE_AGENT_CODE_DECISIONS.md)

## 1. Cài đặt
```bash
cd prototype
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Chạy server + Swagger
```bash
python -m device_agent.seed                  # tạo dasan_proto.db (50 thiết bị, chỉ wave 1 đang chạy)
uvicorn device_agent.main:app --port 8000    # Swagger: http://localhost:8000/docs
```
Endpoint thiết bị yêu cầu chữ ký HMAC nên khó gọi tay trên Swagger; dùng simulator để gọi.

## 3. Chạy mô phỏng thiết bị (tua nhanh x60)
```bash
export DASAN_TIME_SCALE=60                   # server và simulator PHẢI dùng cùng giá trị
python -m device_agent.seed --open-all-waves
uvicorn device_agent.main:app --port 8000 &
python -m simulator.device_sim --devices 50 --duration 45 --bootloop 0.05
```
Kết quả mẫu (45 giây ≈ 45 phút thật):
```
Check-in: 439 | không có việc: 387 | bắt đầu cập nhật: 52
Báo cáo gửi: 215 | báo cáo gửi lại được server nhận là trùng: 19 | 409: 0
Kết cục từng lượt: {'success': 46, 'download_interrupted': 4, 'rolled_back': 2}
Khoảng cách giữa 2 lần check-in: min=271s avg=307s max=410s
device_tasks: SUCCESS 46 · ROLLED_BACK 2 · FAILED 2 (INCOMPATIBLE)
Số task đang chạy tối đa trên 1 thiết bị: 0 (phải <= 1)
```

## 4. Cấu trúc thư mục
```
device_agent/
  config.py         hằng số: chu kỳ check-in, jitter, timeout 15/10/5', backoff 1/5/15', HMAC
  state_machine.py  máy trạng thái device_tasks (thuần logic)
  db.py             SQLite + schema + partial unique index
  schemas.py        DTO request/response
  errors.py         định dạng phản hồi { status, message, data }
  auth.py           xác thực thiết bị HMAC-SHA256 (serial + timestamp + nonce)
  service.py        nghiệp vụ check-in / report / retry / đối soát
  sweeper.py        quét TIMEOUT (lastHeartbeatAt), hạn chót wave, OFFLINE
  router.py         2 endpoint /api/device-agent/*
  main.py           app FastAPI độc lập
  seed.py           dữ liệu giả lập
  timeutil.py       tiện ích thời gian (UTC, ISO)
simulator/device_sim.py   mô phỏng N thiết bị (jitter, dual-bank, watchdog, tiêm lỗi)
```

## 5. Biến môi trường
| Biến | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `DASAN_DB_PATH` | `dasan_proto.db` | File SQLite |
| `DASAN_TIME_SCALE` | `1` | Hệ số tua nhanh thời gian khi demo |
