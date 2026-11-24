# GIẢI TRÌNH 5 CÂU HỎI THIẾT KẾ MÔ HÌNH DỮ LIỆU (ERD)
## DASAN Firmware Rollout Platform — Bước 1 & Slide 4 (Đã đồng bộ Cross-review)

---

## Câu 1. Mô hình hóa các đợt cập nhật bằng bảng riêng hay là một phần của `campaigns`? Vì sao?

**Lựa chọn:** Tách thành bảng riêng **`campaign_waves`** (`campaigns` 1 : N `campaign_waves`, `campaign_waves` 1 : N `device_tasks`).

* Một chiến dịch triển khai theo nhiều đợt cộng dồn nối tiếp nhau (quy ước Q1: `1% → 10% → 50% → 100%`, tương ứng cỡ từng đợt `1% / 9% / 40% / 50%`) và chỉ mở đợt kế tiếp khi đợt hiện tại đạt ngưỡng `minSuccessRateToProceed` (mặc định `95%`) cộng thời gian ngâm (*Soak Time*).
* `campaigns` lưu thông tin điều phối chung: firmware đích, nhóm thiết bị đích, ngưỡng lỗi tự dừng (`failureThresholdPercent`), giới hạn tải đồng thời (`maxConcurrentDevices`), người tạo và trạng thái tổng thể.
* `campaign_waves` lưu cấu hình và vòng đời độc lập của từng đợt: `waveOrder`, `rolloutPercentage`, `minSuccessRateToProceed`, `status` (`PENDING | RUNNING | PAUSED | COMPLETED`), hạn chót `deadlineAt` (mặc định `+24h` khi bắt đầu chạy — Q7), `startedAt`, `finishedAt`.

**Lý do tách bảng (thay vì lưu cột JSON trong `campaigns`):**
1. **Truy vấn & thống kê trực tiếp bằng SQL:** Join trực tiếp `campaign_waves` với `device_tasks` qua `waveId` để tính tỷ lệ thành công/lỗi theo từng wave phục vụ Promotion Gate và Auto-pause (Q3).
2. **Ràng buộc toàn vẹn dữ liệu:** Áp dụng được `UNIQUE (campaignId, waveOrder)`, khóa ngoại `device_tasks.waveId` và kiểm soát `WaveStatus` chặt chẽ ở tầng DB — điều mà mảng JSON không làm được.
3. **Quản lý vòng đời từng đợt độc lập:** Theo dõi riêng `startedAt`, `finishedAt`, `deadlineAt` của từng đợt mà không phải đọc/ghi đè (lock contention) lên một cột JSON lớn trong bản ghi `campaigns`.

---

## Câu 2. Trạng thái chiến dịch và trạng thái tác vụ thiết bị lưu ở đâu? Hai loại trạng thái này có giống nhau không?

**Lựa chọn:** Lưu tách biệt hoàn toàn ở **hai bảng khác nhau**, không dùng chung một cột trạng thái.

1. **Trạng thái chiến dịch (`campaigns.status` — cấp độ vĩ mô / điều phối):**
   * Giá trị: `DRAFT`, `SCHEDULED`, `RUNNING`, `PAUSED`, `COMPLETED`, `ABORTED`.
   * Phản ánh vòng đời điều hành của cả đợt triển khai dưới góc nhìn Operator và Scheduler.
2. **Trạng thái tác vụ thiết bị (`device_tasks.status` — cấp độ vi mô / thực thi cạnh):**
   * Giá trị: `PENDING`, `DOWNLOADING`, `INSTALLING`, `VERIFYING`, `SUCCESS`, `FAILED`, `TIMEOUT`, `ROLLED_BACK`.
   * Phản ánh tiến trình tải, ghi flash phân vùng phụ, reboot và xác minh trên từng thiết bị cụ thể.

**Vì sao không thể gộp chung?**
* Hai trạng thái thuộc **hai cấp độ hạt (granularity)** và **tác nhân chuyển trạng thái** khác nhau: trong cùng một thời điểm `campaigns.status = RUNNING`, có thiết bị đã `SUCCESS`, thiết bị khác đang `DOWNLOADING` hoặc `VERIFYING`, thiết bị khác đang `PENDING` chờ retry hoặc `ROLLED_BACK`. Tách riêng giúp điều phối chiến dịch (Pause/Resume/Abort) mà không làm mất dấu trạng thái thực thi thực tế dưới từng thiết bị.

---

## Câu 3. Những trường nào được tính từ dữ liệu khác và không nên lưu trữ cứng?

**Lựa chọn:** Giữ `device_tasks` làm **Single Source of Truth**; **không lưu thành cột vật lý** trong `campaigns` hoặc `campaign_waves` các chỉ số tổng hợp động sau:
* *Current Success Rate* (Tỷ lệ thành công hiện tại)
* *Current Failure Rate* (Tỷ lệ lỗi hiện tại)
* *Completed Devices Count* / *Total Successful Devices*
* *Current Active Downloads* (Số thiết bị đang chiếm slot `DOWNLOADING`)

**Quy tắc mẫu số thống nhất toàn nhóm (Quy ước Q3 & Q4):**
* Mẫu số chỉ tính các task đã ở **trạng thái kết thúc cuối cùng (terminal states)**:
  * Thành công: `SUCCESS`
  * Thất bại cuối cùng: `ROLLED_BACK` (không retry tự động), cộng với `FAILED` và `TIMEOUT` **đã hết lượt thử lại** (`attemptCount = maxAttempts = 3`).
* Các task đang chạy (`PENDING`, `DOWNLOADING`, `INSTALLING`, `VERIFYING`) — bao gồm cả task vừa lỗi tạm thời nhưng còn lượt retry quay về `PENDING` — **không đưa vào mẫu số**.
* *Ví dụ:* Wave có `1.000` task đã kết thúc cuối cùng, trong đó `950` task `SUCCESS` $\Rightarrow$ `SuccessRate = 950 / 1.000 × 100% = 95%`.

**Lý do không lưu cứng vào bảng `campaigns`:**
* Tránh **dư thừa và bất nhất dữ liệu (write contention / lost update)** khi hàng trăm thiết bị gửi kết quả cùng lúc.
* Để tăng tốc cho Dashboard Operator (`GET /api/campaigns/{id}/progress`), hệ thống tính trước/lưu tạm trong **Redis Cache** (kèm Redis Semaphore `sem:campaign:{id}` cho số lượt tải đồng thời); Database vẫn chỉ lưu dữ liệu gốc ở `device_tasks`.

---

## Câu 4. Làm thế nào để lưu lịch sử mọi firmware mà thiết bị từng chạy?

**Lựa chọn:** Kết hợp bảng **`device_firmware_histories`** (lưu lịch sử các phiên bản đã xác minh hoạt động ổn định) và bảng **`device_tasks`** (lưu vết toàn bộ mọi lần thử cập nhật, bao gồm cả lỗi và rollback — không bao giờ xóa cứng).

**Phân tách vai trò rõ ràng giữa 3 bảng:**
* `devices.currentFirmwareId`: Phiên bản firmware đã xác minh và đang chạy chính thức trên thiết bị.
* `device_firmware_histories`: Lịch sử chuỗi các phiên bản firmware thiết bị đã chạy ổn định qua thời gian (`deviceId`, `firmwareId`, `taskId`, `installedAt`).
* `device_tasks`: Hồ sơ chi tiết từng lần thực thi cập nhật (`fromFirmwareId`, `toFirmwareId`, `attemptCount`, `status`, `errorCode`).

**Luồng ghi nhận nhất quán (khớp Yêu cầu Cốt lõi #5 & Dual-Bank A/B của Thành viên B):**
1. Thiết bị tải firmware vào phân vùng phụ (Bank B), chuyển qua `DOWNLOADING → INSTALLING → VERIFYING` (Bank A vẫn giữ nguyên firmware cũ).
2. Trong suốt bước `VERIFYING`, server **chưa** đổi `devices.currentFirmwareId` và **chưa** ghi `device_firmware_histories`.
3. Khi thiết bị boot thành công và vượt qua self-test (`stage = SUCCESS`), backend thực hiện **gói gọn trong 1 DB Transaction**:
   * `UPDATE device_tasks SET status = 'SUCCESS', finishedAt = NOW()`
   * `UPDATE devices SET currentFirmwareId = toFirmwareId, activePartition = ...`
   * `INSERT INTO device_firmware_histories (deviceId, firmwareId, taskId, installedAt)`
4. Nếu thiết bị gặp boot-loop và Watchdog tự quay về Bank A (`ROLLED_BACK`), `device_tasks` ghi nhận `status = 'ROLLED_BACK'` kèm `toFirmwareId` và `errorCode`; `currentFirmwareId` vẫn giữ đúng bản cũ trên Bank A.

**Ràng buộc quan hệ trên ERD:**
* Mỗi `device_task` sinh ra **tối đa 1 bản ghi lịch sử** khi `SUCCESS` $\Rightarrow$ quan hệ **`device_tasks` 1 : 0..1 `device_firmware_histories`** với ràng buộc `UNIQUE (taskId)`.

---

## Câu 5. Những bảng nào tăng nhanh nhất và chiến lược Indexing / Partitioning / Archiving?

Hai bảng tăng trưởng nhanh nhất theo thời gian vận hành là **`device_tasks`** và **`audit_logs`** (đồng bộ số liệu với Slide 10 — `CAPACITY_ESTIMATION.md`):
1. **`device_tasks`:** Với `100.000` thiết bị và giả định `10` chiến dịch × `50.000` máy/năm, bảng tăng khoảng **`500.000` bản ghi/năm** (`~550.000` bản ghi/năm kèm chiến dịch rollback; ở kịch bản mở rộng gấp 10 lần — `1.000.000` thiết bị là **`5.000.000` bản ghi/năm**). *(Lưu ý: retry chỉ tăng `attemptCount` trên cùng dòng task nên không làm nhân bội số bản ghi).*
2. **`audit_logs`:** Chỉ ghi thêm (*append-only*) cho mọi sự kiện kiểm toán (`FIRMWARE_UPLOADED`, `FIRMWARE_APPROVED`, `FIRMWARE_DEPRECATED`, thao tác điều khiển Campaign, Auto-pause, từ chối quyền 401/403 và các mốc chuyển trạng thái vòng đời tác vụ) $\Rightarrow$ ước tính cận trên khoảng **`2.500.000` dòng/năm** (`~1,4 GB/năm`, tương đương ~5 sự kiện audit/task; `25 triệu` dòng/năm ở kịch bản 10x). Tuyệt đối **không ghi check-in/heartbeat định kỳ 5 phút** (`10,51 tỷ lượt/năm`) vào `audit_logs`.

**Chiến lược Indexing trên PostgreSQL:**
* **3 Composite Indexes phục vụ truy vấn nóng của Scheduler, Check-in & Dashboard:**
  ```sql
  CREATE INDEX idx_tasks_campaign_status ON device_tasks ("campaignId", status);
  CREATE INDEX idx_tasks_device_status   ON device_tasks ("deviceId", status);
  CREATE INDEX idx_tasks_wave_status     ON device_tasks ("waveId", status);
  ```
* **Partial Unique Index chống xung đột đồng thời (Concurrency Last Line of Defense):**
  ```sql
  CREATE UNIQUE INDEX uq_active_device_task
  ON device_tasks ("deviceId")
  WHERE status IN ('PENDING', 'DOWNLOADING', 'INSTALLING', 'VERIFYING');
  ```
  *(Đảm bảo tuyệt đối tại mọi thời điểm mỗi thiết bị chỉ có tối đa 1 tác vụ đang hoạt động, ngay cả khi 2 Operator bấm Start cùng lúc).*
* **Indexes cho `audit_logs`:** `(targetType, targetId, createdAt)` và `(createdAt)` phục vụ truy vết sự cố theo đối tượng và khoảng thời gian.

**Chiến lược Partitioning & Cold Storage Archiving:**
* **Partitioning:** Phân vùng bảng (*Range Partitioning*) cho `audit_logs` theo tháng/quý (`createdAt`) và cho `device_tasks` theo thời gian/chiến dịch khi quy mô chạm ngưỡng hàng triệu dòng (lưu ý giữ bảng/index hoạt động nóng cho các task active để bảo toàn Partial Unique Index theo `deviceId`).
* **Archiving:** Các `device_tasks` của chiến dịch đã kết thúc (`COMPLETED` / `ABORTED`) trên **12 tháng** và `audit_logs` quá hạn lưu giữ nóng được chuyển sang **Cold Storage (S3 Parquet / Archive Table)** — giữ cho working set trong RAM của PostgreSQL luôn gọn nhẹ mà vẫn đảm bảo truy xuất kiểm toán khi cần.
