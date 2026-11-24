# KẾ HOẠCH PHÂN CÔNG NHIỆM VỤ CHI TIẾT NHÓM 4 THÀNH VIÊN
## BÀI TẬP OJT: NỀN TẢNG TRIỂN KHAI CẬP NHẬT FIRMWARE (DASAN VIETNAM)

> **Căn cứ đề bài:** Trang 7 & 8 tài liệu đặc tả [KITS2026_OJT2_Assignments.pdf](file:///C:/Kist/KITS2026_OJT2_Assignments.pdf).
> Với nhóm **4 người**, phần việc của Thành viên D và E được gộp lại và phân bổ hợp lý, bảo đảm mỗi người chịu trách nhiệm chính một mảng kỹ thuật sâu, có sản phẩm bàn giao rõ ràng và làm chủ các slide thuyết trình của mình.

---

## 1. NGUYÊN TẮC LÀM VIỆC NHÓM & QUY ƯỚC CHUNG

1. **Thống nhất trước khi vẽ (Bắt buộc - 60 phút đầu):**
   * **Tên thực thể & bảng:** `members`, `device_groups`, `devices`, `firmware_versions`, `campaigns`, `campaign_waves`, `device_tasks`, `device_firmware_histories`, `audit_logs`.
   * **Enum trạng thái:**
     * `CampaignStatus`: `DRAFT`, `SCHEDULED`, `RUNNING`, `PAUSED`, `COMPLETED`, `ABORTED`.
     * `DeviceTaskStatus`: `PENDING`, `DOWNLOADING`, `INSTALLING`, `VERIFYING`, `SUCCESS`, `FAILED`, `TIMEOUT`, `ROLLED_BACK`.
     * `WaveStatus`: `PENDING`, `RUNNING`, `PAUSED`, `COMPLETED` *(không dùng `FAILED` — wave lỗi thì Campaign chuyển `PAUSED`)*.
     * `FirmwareStatus`: `UPLOADED`, `APPROVED`, `DEPRECATED`.
   * **Cơ chế xác thực:** Admin/Operator dùng `JWT`; Thiết bị dùng `mTLS` hoặc `HMAC-SHA256(serialNo + timestamp + nonce + METHOD + PATH + SHA256(body))` (chống replay + chống sửa body, `secret` lưu tách biệt tại `device_credentials` / KMS).
   * **Các định nghĩa nghiệp vụ đã chốt (mọi sơ đồ/slide phải dùng đúng):**

     | # | Vấn đề | Quy ước chốt |
     | :-: | :--- | :--- |
     | Q1 | % của Wave | `rolloutPercentage` là **cộng dồn**: 1% → 10% → 50% → 100% ⇒ kích thước từng đợt = 1% / 9% / 40% / 50%. |
     | Q2 | Ngưỡng chuyển Wave | Trường cấu hình `campaign_waves.minSuccessRateToProceed`, **mặc định 95% cho mọi wave** + Soak Time ≥ 2h (wave 1, 2). |
     | Q3 | Phạm vi tính tỷ lệ lỗi | Auto-pause đánh giá theo **Wave đang chạy** (phản ánh nhanh firmware lỗi); Dashboard hiển thị thêm tỷ lệ lỗi cộng dồn của Campaign. |
     | Q4 | Retry có tính vào FailureRate? | **Không tính từng lần thử.** Chỉ đếm task ở trạng thái **kết thúc cuối cùng**: `SUCCESS`, `ROLLED_BACK`, `FAILED`/`TIMEOUT` **đã hết lượt retry** (`attemptCount = maxAttempts = 3`). |
     | Q5 | Server biết `INSTALLING`/`VERIFYING` thế nào? | `POST /api/device-agent/tasks/{taskId}/result` nhận cả **trạng thái trung gian** qua trường `stage` (`DOWNLOADED`, `INSTALLING`, `VERIFYING`) và **kết quả cuối** (`SUCCESS`/`FAILED`/`ROLLED_BACK`). Mỗi lần gọi cập nhật `lastHeartbeatAt`. |
     | Q6 | Khi nào trả slot `maxConcurrentDevices`? | Slot là **slot tải xuống**: cấp khi task → `DOWNLOADING`; **trả khi thiết bị báo tải xong (`stage = DOWNLOADED` / `INSTALLING`)**, hoặc khi `FAILED`/`TIMEOUT` ở bước tải. Semaphore tính **theo từng campaign**: key `sem:campaign:{id}`. |
     | Q7 | Thiết bị OFFLINE, hạn chót & `ABORTED` | Chỉ tạo task cho thiết bị đủ điều kiện, kể cả OFFLINE (nhận task khi online lại). Mỗi wave có **hạn chót** `deadlineAt` (`NULL` khi `PENDING`, mặc định `startedAt + 24h` khi `RUNNING`; có thể cấu hình ngắn hơn vd `1h` cho straggler): task chưa bắt đầu khi hết hạn → `TIMEOUT` (`WAVE_DEADLINE_EXCEEDED`, không retry). Khi Campaign bị `ABORTED`, các task `PENDING` chưa chạy chuyển sang `FAILED` (`CAMPAIGN_ABORTED`) để giải phóng khóa `uq_active_device_task`. |
     | Q8 | So sánh phiên bản | Thêm `firmware_versions.versionCode INT` (vd v2.4.1 → 20401) và `minRequiredVersionCode INT`; **so sánh số**, không so sánh chuỗi. |
     | Q9 | Timeout & Retry thiết bị | Tải: 15 phút · Cài: 10 phút · Verify (boot + self-test): 5 phút. Retry tối đa 3 lần, backoff 1 → 5 → 15 phút. `ROLLED_BACK` **không** retry tự động. |
     | Q10 | Tên file sơ đồ | Theo checklist mục 4 (đã cập nhật đúng tên file thực tế). |
2. **Quy ước công cụ & Git:**
   * Mỗi thành viên tạo nhánh riêng: `feature/tv-a-domain`, `feature/tv-b-device`, `feature/tv-c-campaign`, `feature/tv-d-reliability`.
   * Lưu trữ sơ đồ nguồn tại thư mục `diagrams/` dưới định dạng `.drawio` hoặc `.dbml` (để commit lên Git tính đóng góp cá nhân).
   * Slide làm chung trên Google Slides / PowerPoint Template đồng nhất font chữ, bảng màu và icon.

---

## 2. BẢNG PHÂN CÔNG CHI TIẾT THEO TỪNG THÀNH VIÊN

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CƠ CẤU NHÓM 4 NGƯỜI                                   │
├─────────────────────┬─────────────────────┬─────────────────────┬──────────────────────┤
│    THÀNH VIÊN A     │    THÀNH VIÊN B     │    THÀNH VIÊN C     │     THÀNH VIÊN D     │
│   Domain & Data     │  Device & Agent     │   Campaign Engine   │ Reliability, Scale,  │
│    Architecture     │      Protocol       │    & Concurrency    │  Security, AI & PPT  │
└─────────────────────┴─────────────────────┴─────────────────────┴──────────────────────┘
```

---

### 👤 THÀNH VIÊN A: Chủ trì Mô hình dữ liệu & Luồng phát hành Firmware
* **Chức danh vai trò:** *Domain & Data Architect*
* **Trọng số điểm liên quan:** 20% (Mô hình ERD) + 10% (Kiến trúc & Luồng 1)

#### 📌 Nhiệm vụ cụ thể:
1. **Thiết kế ERD chuẩn hóa:**
   * Xây dựng sơ đồ quan hệ thực thể đầy đủ PK/FK, kiểu dữ liệu cho 9 bảng (`members`, `device_groups`, `devices`, `firmware_versions`, `campaigns`, `campaign_waves`, `device_tasks`, `device_firmware_histories`, `audit_logs`).
   * Viết file mã nguồn `diagrams/erd.dbml` hoặc `diagrams/erd.drawio`.
2. **Giải trình 5 câu hỏi thiết kế Bước 1 (ghi chú trực tiếp trên slide ERD):**
   * Vì sao tách bảng `campaign_waves`?
   * Tách biệt trạng thái chiến dịch (`campaigns.status`) và trạng thái thiết bị (`device_tasks.status`) như thế nào?
   * Các trường tính toán động (tỷ lệ thành công, đếm lỗi...) không nên lưu cứng ở đâu?
   * Cơ chế lưu lịch sử firmware (`device_firmware_histories`).
   * Bảng nào tăng nhanh nhất (`device_tasks`, `audit_logs`) và chiến lược Indexing / Partitioning.
3. **Thiết kế Luồng 1 - Phát hành & Phê duyệt (Sequence Diagram 1):**
   * Developer tải file firmware & checksum SHA-256 $\to$ Hệ thống kiểm tra hợp lệ $\to$ QA phê duyệt (nguyên tắc 4-mắt `uploadedBy != approvedBy`) $\to$ Đổi trạng thái `APPROVED` $\to$ Sẵn sàng cho chiến dịch.
   * Xây dựng ma trận quy tắc tương thích: Chỉ đúng Model, phiên bản hiện tại $\ge$ `minRequiredVersion`, không dùng firmware `DEPRECATED`.
4. **Phụ trách Slide thuyết trình:**
   * **Slide 3:** Tác nhân & Bảng thuật ngữ (Actors & Use Cases).
   * **Slide 4:** Mô hình miền nghiệp vụ / ERD & Trả lời 5 câu hỏi thiết kế.
   * **Slide 6:** Luồng 1 - Phát hành và phê duyệt firmware (Four-eyes approval, quy tắc tương thích).
5. **Bộ câu hỏi phản biện dự kiến cần chuẩn bị:**
   * *“Tại sao nhóm không lưu các đợt (waves) thành trường JSON trong bảng campaigns cho gọn nhẹ?”*
   * *“Nếu Developer kiêm luôn quyền QA thì hệ thống chặn ở tầng nào (Database constraint hay Application logic)?”*

---

### 👤 THÀNH VIÊN B: Phía Thiết bị, Giao thức Báo danh & Phân vùng A/B
* **Chức danh vai trò:** *Device Agent & Edge Protocol Specialist*
* **Trọng số điểm liên quan:** 20% (Máy trạng thái & Xử lý lỗi phía thiết bị) + 10% (Kiến trúc Pull)

#### 📌 Nhiệm vụ cụ thể:
1. **Thiết kế Luồng báo danh (Sequence Diagram 2 - Device Check-in & Update):**
   * Thiết bị check-in $\to$ Máy chủ trả về task (hoặc rỗng) $\to$ Thiết bị nhận Pre-signed URL $\to$ Tải trực tiếp từ Object Storage $\to$ Kiểm tra SHA-256 $\to$ Flash ROM $\to$ Khởi động lại $\to$ Báo cáo kết quả.
2. **Lập luận bắt buộc Push vs. Pull:**
   * Giải thích tường tận vì sao dùng cơ chế **PULL thuần túy kết hợp Random Jitter (±30s)**: Thiết bị ONT/ONU nằm sau NAT/Firewall khách hàng, IP động, không thể mở port inbound từ internet; PULL tiết kiệm tài nguyên so với duy trì kết nối persistent MQTT.
3. **Thiết kế Máy trạng thái Tác vụ Thiết bị (Device Task State Machine):**
   * Vẽ sơ đồ chuyển trạng thái chi tiết: `PENDING` $\to$ `DOWNLOADING` $\to$ `INSTALLING` $\to$ `VERIFYING` $\to$ `SUCCESS` / `FAILED` / `TIMEOUT` / `ROLLED_BACK`.
   * Timeout cho **cả 3 bước** theo quy ước Q9 (Tải 15' · Cài 10' · Verify 5') — Worker quét `lastHeartbeatAt` để phát hiện thiết bị im lặng; Retry tối đa 3 lần, backoff 1 → 5 → 15 phút; `ROLLED_BACK` không retry tự động.
   * Ghi chú bắt buộc: firmware cũ được giữ nguyên ở bank đang chạy cho đến khi `VERIFYING` thành công (Yêu cầu Cốt lõi #5).
4. **Thiết kế an toàn phần cứng (Dual-Bank A/B Partition \& Watchdog):**
   * Trình bày cơ chế giữ firmware cũ ở Bank A, nạp firmware mới vào Bank B.
   * Cơ chế Watchdog Timer của Bootloader: Nếu khởi động vào Bank B bị boot-loop quá 3 lần $\to$ Bootloader tự động rollback về Bank A và đánh dấu cờ lỗi gửi về server (`ROLLED_BACK`).
5. **Xử lý tính lũy đẳng (Idempotency):**
   * Check-in lặp lại $\to$ server trả lại **đúng task đang hoạt động** của thiết bị, không tạo task mới.
   * Gửi `result` lặp lại $\to$ khóa theo `(taskId, attemptCount, stage)`; chỉ cập nhật khi chuyển trạng thái hợp lệ (`UPDATE ... WHERE status = <trạng thái mong đợi>`); bản trùng trả `200` kèm trạng thái hiện tại, không tăng biến đếm.
   * Nếu `currentVersion` trong check-in **đã bằng** `toFirmware` $\to$ coi như `SUCCESS` (kết quả trước đó bị mất trên đường truyền).
6. **Chủ trì Bảng tình huống lỗi (Slide 9)** — mỗi dòng: *Xảy ra gì / Phát hiện thế nào / Khôi phục ra sao*:
   * Mất kết nối khi đang tải · Thiết bị không báo lại (timeout) · Không vượt qua xác minh (sai checksum/verify) · Boot-loop sau cập nhật (Watchdog rollback).
   * (C bổ sung dòng *Xung đột 2 chiến dịch* + khối Auto-pause; D bổ sung dòng *Firmware lỗi phát hiện sau khi chiến dịch kết thúc*.)
7. **Phác thảo API (Slide 12 — chuyển từ D sang B):** Danh sách endpoint, nguyên tắc RESTful, request/response/status code cho 3 endpoint `*` (`POST /api/campaigns` lấy nội dung từ C), giải thích vì sao endpoint thiết bị dùng xác thực khác endpoint quản trị.
8. **Phụ trách Slide thuyết trình:**
   * **Slide 5:** Tổng quan kiến trúc hệ thống \& Lập luận chọn cơ chế PULL + Tách tải S3/CDN.
   * **Slide 8 (nửa phải):** Máy trạng thái Device Task (timeout, retry, rollback).
   * **Slide 9 (chủ trì):** Bảng tình huống lỗi \& Dual-Bank A/B Rollback.
   * **Slide 12:** Phác thảo API \& nguyên tắc RESTful.
9. **Bộ câu hỏi phản biện dự kiến cần chuẩn bị:**
   * *“Nếu thiết bị mất điện đúng lúc đang flash firmware thì có bị biến thành 'cục gạch' (brick) không?”*
   * *“Khi 10.000 thiết bị cùng check-in một lúc sau sự cố mất điện lưới ISP, làm sao server của bạn không bị sập?”*

---

### 👤 THÀNH VIÊN C: Bộ máy Điều phối Chiến dịch & Xử lý Đồng thời
* **Chức danh vai trò:** *Campaign Engine & Concurrency Engineer*
* **Trọng số điểm liên quan:** 20% (Điều phối chiến dịch, đợt cập nhật & Tự tạm dừng) + 15% (Đồng thời)

#### 📌 Nhiệm vụ cụ thể:
1. **Thiết kế Luồng chạy Chiến dịch (Sequence Diagram 3 - Campaign Rollout):**
   * Operator bấm Start chiến dịch $\to$ Lọc thiết bị thỏa mãn điều kiện $\to$ Tạo các task `PENDING` $\to$ Mở đợt 1 (Canary 1%) $\to$ Đạt `minSuccessRateToProceed` (mặc định $\ge 95\%$) + Soak Time $\to$ Tự động mở đợt tiếp theo (cộng dồn 10% $\to$ 50% $\to$ 100% — quy ước Q1, Q2).
   * Đoạn check-in trong sơ đồ phải **khớp từng bước** với `sequence_checkin.drawio` của B (endpoint, thời điểm đổi `DOWNLOADING`, trường `stage`).
2. **Thiết kế Máy trạng thái Chiến dịch (Campaign State Machine):**
   * Các trạng thái: `DRAFT` $\to$ `SCHEDULED` $\to$ `RUNNING` $\leftrightarrow$ `PAUSED` $\to$ `COMPLETED` / `ABORTED`; bổ sung `SCHEDULED` $\to$ `DRAFT` (Operator hủy lịch hẹn).
   * Xác định rõ tác nhân kích hoạt từng chuyển trạng thái (Operator trigger vs. System Auto trigger).
   * Điều kiện `COMPLETED` theo quy ước Q7 (hạn chót wave — thiết bị OFFLINE không làm kẹt chiến dịch).
3. **Cơ chế Tự động tạm dừng (Auto-pause Engine):**
   * Công thức (quy ước Q3, Q4): $\text{FailureRate} = \frac{\text{FAILED}_{final} + \text{TIMEOUT}_{final} + \text{ROLLED\_BACK}}{\text{Số task đã ở trạng thái kết thúc cuối cùng trong Wave}}$ — task đang chờ retry **không** được tính.
   * Thiết lập điều kiện kích hoạt: Đánh giá sau khi có cỡ mẫu tối thiểu (ví dụ: ít nhất 50 thiết bị đã trả kết quả) để tránh lỗi thống kê mẫu nhỏ; nếu $\text{FailureRate} > \text{failureThresholdPercent} \to$ Hệ thống tự động chuyển chiến dịch sang `PAUSED`, ghi `audit_logs` (`actorType = SYSTEM`), gửi webhook/alert tới Operator.
   * **Auto-pause là luật cơ học, không phụ thuộc vào AI** (AI của D chỉ đưa gợi ý).
4. **Kiểm soát tải tải xuống (`maxConcurrentDevices`) & Xử lý đồng thời (Concurrency Control):**
   * Cơ chế cấp phát lượt tải: Redis Semaphore **theo từng campaign** (`sem:campaign:{id}`); cấp slot khi task $\to$ `DOWNLOADING`, **trả slot khi thiết bị báo `INSTALLING`** hoặc `FAILED`/`TIMEOUT` ở bước tải (quy ước Q6). Worker timeout thu hồi slot bị "rò".
   * Xử lý xung đột khi 2 Operator cùng bấm Start 2 chiến dịch có chung thiết bị: **Distributed Lock** theo `targetGroupId` (đủ vì mỗi thiết bị chỉ thuộc 1 group) **và** **Partial Unique Database Index** (`deviceId` chỉ có tối đa 1 task đang hoạt động) làm chốt chặn cuối.
5. **Khả năng quan sát — Observability (Yêu cầu Mở rộng #11, mới giao cho C):**
   * Dashboard Operator: số task theo từng trạng thái, success/failure rate **theo wave** và **cộng dồn campaign**, số lượt tải đang chạy / `maxConcurrentDevices`, top mã lỗi, thời gian cập nhật trung bình, tỷ lệ thiết bị OFFLINE, thời gian còn lại tới hạn chót wave.
   * Chỉ số báo cần dừng: FailureRate tiến sát ngưỡng, tỷ lệ `ROLLED_BACK` > 0 tăng nhanh, tỷ lệ `TIMEOUT` tăng đột biến, một mã lỗi chiếm đa số.
6. **Điểm cộng #14 — Khung giờ bảo trì & đa múi giờ (giao cho C):**
   * Thêm `device_groups.maintenanceWindow` (vd `"01:00-05:00"`) + `timezone` (chuẩn IANA, vd `"Asia/Ho_Chi_Minh"`, đã khớp ERD của A). Khi thiết bị check-in ngoài khung giờ bảo trì theo giờ địa phương của group $\to$ trả `NO_TASK`.
7. **Phụ trách Slide thuyết trình:**
   * **Slide 7:** Luồng 2 - Triển khai chiến dịch, Canary Wave, Logic chọn thiết bị & Giới hạn `maxConcurrentDevices` (+ ghi chú khung giờ bảo trì).
   * **Slide 8 (nửa trái):** Máy trạng thái Campaign (trigger Operator vs. System).
   * **Slide 9 (phần của C):** Khối Auto-pause + chỉ số Dashboard; dòng *Xung đột 2 chiến dịch chung thiết bị* trong bảng tình huống lỗi của B.
8. **Bộ câu hỏi phản biện dự kiến cần chuẩn bị:**
   * *“Nếu chiến dịch đang chạy bị Auto-pause thì những thiết bị đang tải dở có bị dừng ngay lập tức không?”*
   * *“Làm sao để đảm bảo thiết bị thuộc nhóm VIP hoặc khách hàng quan trọng không bị chọn vào đợt Canary 1% thử nghiệm?”*

---

### 👤 THÀNH VIÊN D: Năng lực, Bảo mật, Ứng dụng AI & Điều phối Slide
* **Chức danh vai trò:** *System Reliability, Security, AI Lead & Project Coordinator*
* **Trọng số điểm liên quan:** 15% (Quy mô & Năng lực) + 10% (Bảo mật/Kiểm toán) + 5% (AI/LLM) + 10% (Thuyết trình & Mock API)

#### 📌 Nhiệm vụ cụ thể:
1. **Tính toán Quy mô & Năng lực (Capacity Estimation):**
   * Lập bảng tính toán chi tiết từ thông số đề bài:
     * Check-in trung bình: $100.000 / 300\text{s} \approx 333$ RPS.
     * Check-in cao điểm (Thundering Herd): $1.500 - 3.000$ RPS.
     * Băng thông đợt 10% của 50.000 thiết bị: $5.000 \times 50\text{ MB} = 250\text{ GB}$.
     * Tăng trưởng dữ liệu `device_tasks`: $\approx 500.000$ bản ghi/năm.
   * Chỉ rõ các điểm nghẽn (DB Write bottleneck, Bandwidth bottleneck — 500 lượt tải $\times$ 5 MB/s $\approx$ 2,5 GB/s $\approx$ 20 Gbps nên bắt buộc có CDN) và giải pháp khắc phục; dùng thời gian cài/reboot thực tế theo timeout của B (quy ước Q9) và nêu rõ **kịch bản tăng quy mô gấp 10 lần (1.000.000 thiết bị)**.
2. **Bảo mật, Ma trận phân quyền & Nhật ký kiểm toán (Audit Trail):**
   * Thiết lập ma trận phân quyền RBAC: 4 vai trò `ADMIN`, `DEVELOPER`, `QA`, `OPERATOR` theo từng endpoint.
   * Lập luận giải pháp tách biệt xác thực: Web Admin dùng JWT; Thiết bị dùng mTLS / `HMAC-SHA256(serialNo + timestamp + nonce + METHOD + PATH + SHA256(body))` chống replay & chống sửa body.
   * Thiết kế bảng `audit_logs` (chỉ ghi thêm / append-only, `actorId` nullable kèm `actorType`: `MEMBER | SYSTEM | DEVICE`).
3. **Thiết kế & Thực nghiệm Tính năng AI / LLM (Phương án C kết hợp B):**
   * Xây dựng Prompt đủ 5 thành phần (mục đích, bối cảnh, trường đầu vào, tiêu chí, định dạng **JSON Schema**) và bộ lọc Backend validate.
   * **Chạy thử với model AI thật** (ChatGPT/Claude/Gemini), lưu lại Input/Output thực tế (đã ẩn danh serial/dữ liệu khách hàng) — không dùng output tự bịa.
   * Thiết kế cơ chế Human-in-the-loop và Fallback khi dịch vụ AI bị timeout/lỗi (chỉ ẩn khung gợi ý AI trên Dashboard; **Auto-pause cơ học của C vẫn chạy độc lập, không phụ thuộc AI**).
   * Viết tài liệu **Nhật ký Prompt AI (`docs/prompt-log.md`, 1–2 trang)**: Ghi lại quá trình thử nghiệm, nêu rõ ít nhất **1 trường hợp AI gợi ý sai/chưa đủ** (ví dụ: AI tự suy diễn/ảo giác *"sản xuất trước năm 2024"* dù input không có năm sản xuất, hoặc đề xuất tự rollback hàng loạt) và cách nhóm phản biện, sửa đổi.
4. **Điểm cộng #13 — Dừng khẩn cấp & Rollback hàng loạt sau khi chiến dịch kết thúc:**
   * Tạo "Rollback Campaign" nhắm tới phiên bản firmware trước đó lấy từ `device_firmware_histories` (phối hợp bổ sung 1 dòng vào Bảng tình huống lỗi trên Slide 9).
5. **Tổng hợp Slide & Dựng Mock API Skeleton (Điểm cộng mục 15):**
   * Chuẩn hóa cấu trúc bộ slide (tối đa **16 slide**), kiểm tra tính nhất quán giữa các sơ đồ của A, B, C.
   * Dựng nhanh Mock API tối giản (FastAPI hoặc Node.js) demo 1 luồng: *Check-in $\to$ Trả task $\to$ Báo cáo kết quả* trên Swagger UI (chỉ làm sau khi 16 slide cốt lõi đã xong).
6. **Phụ trách Slide thuyết trình:**
   * **Slide 1:** Trang bìa giới thiệu nhóm.
   * **Slide 2:** Xác định vấn đề thực tế, mục tiêu & phạm vi giải pháp.
   * **Slide 10:** Quy mô, năng lực, phân tích điểm nghẽn & mở rộng gấp 10 lần (Capacity Estimation).
   * **Slide 11:** Ma trận bảo mật RBAC, xác thực thiết bị & Audit Trail.
   * **Slide 13:** Ứng dụng AI/LLM, Prompt, JSON Schema, Output thực tế & Nhật ký sửa lỗi AI.
   * **Slide 14:** Đánh đổi thiết kế (Trade-offs) & Lộ trình MVP.
   * **Slide 15:** Đóng góp cá nhân của từng thành viên & Bài học kinh nghiệm.
   * **Slide 16:** Tổng kết, Demo Mock API & Hỏi đáp (Q&A).
   *(Lưu ý: Slide 12 — Phác thảo API đã chuyển sang Thành viên B phụ trách để cân bằng thời lượng thuyết trình.)*
7. **Bộ câu hỏi phản biện dự kiến cần chuẩn bị:**
   * *“Nếu hệ thống tăng quy mô lên 1.000.000 thiết bị (gấp 10 lần), những thành phần nào trong kiến trúc này sẽ gãy đầu tiên?”*
   * *“Tại sao không cho AI tự động kích hoạt hủy chiến dịch khi phát hiện lỗi nghiêm trọng?”*

---

## 3. LỊCH TRÌNH LÀM VIỆC THEO KHUNG 8 TIẾNG (480 PHÚT)

| Thời gian | Giai đoạn | Hành động cụ thể của cả nhóm | Người chủ trì |
| :---: | :--- | :--- | :---: |
| **00:00 – 01:00**<br>*(60 phút)* | **Khởi động & Chốt quy ước** | Họp cả nhóm: Thống nhất từ điển thuật ngữ, tên bảng, tên trường, danh sách Enum trạng thái, công nghệ sơ đồ (draw.io / dbdiagram). | **Thành viên D** |
| **01:00 – 03:30**<br>*(150 phút)* | **Thiết kế cá nhân chuyên sâu** | - **A:** Hoàn thành ERD và sơ đồ Luồng 1 (Phát hành/Phê duyệt).<br>- **B:** Hoàn thành sơ đồ Luồng 2 (Check-in), State Machine Device và A/B partition.<br>- **C:** Hoàn thành sơ đồ Luồng 3 (Wave rollout), State Machine Campaign và Auto-pause.<br>- **D:** Tính toán bảng Năng lực, viết Prompt AI chạy thử nghiệm, thiết kế RBAC. | **Từng cá nhân** |
| **03:30 – 04:30**<br>*(60 phút)* | **Rà soát chéo (Cross-review)** | - A và B đối chiếu bảng `devices`, `device_tasks` với State Machine.<br>- B và C kiểm tra ăn khớp giữa `maxConcurrentDevices` và luồng check-in.<br>- C và D kiểm tra ngưỡng Auto-pause và cơ chế Fallback của AI. | **Cả nhóm** |
| **04:30 – 05:00**<br>*(30 phút)* | **Thực nghiệm AI & Mock API** | Thành viên D chạy thử Prompt trên ChatGPT/Claude/Gemini, chụp lại Input/Output thực tế, ghi lại 1 lỗi AI; chạy test bộ khung Mock API Skeleton. | **Thành viên D** |
| **05:00 – 07:00**<br>*(120 phút)* | **Lắp ghép 16 Slide PPT** | Đưa các sơ đồ đã vẽ vào đúng thứ tự 16 slide. Từng thành viên viết bullet points giải thích ngắn gọn, súc tích (ưu tiên "Vì sao" thay vì chỉ mô tả). | **Thành viên D** chủ trì, cả nhóm viết |
| **07:00 – 07:30**<br>*(30 phút)* | **Tập dượt thuyết trình (Dry-run)** | Bấm giờ nghiêm ngặt: Mỗi thành viên thuyết trình 2.5 phút (tổng đúng 10 phút). Góp ý cách ngắt nhịp và chuyển tiếp giữa các phần. | **Cả nhóm** |
| **07:30 – 08:00**<br>*(30 phút)* | **Luyện hỏi đáp (Q&A Drill)** | Đặt các câu hỏi "Vì sao" xoáy sâu vào các điểm đánh đổi thiết kế và luồng xử lý lỗi để từng thành viên trả lời thuần thục. | **Cả nhóm** |

---

## 4. CHECKLIST SẢN PHẨM NỘP BÀI (DELIVERABLES)

- [ ] **1. File Slide PPT:** Đúng 16 slide theo cấu trúc chuẩn, xuất định dạng `.pptx` và `.pdf`.
- [ ] **2. Thư mục mã nguồn sơ đồ (`diagrams/`):**
  - [ ] `erd.drawio` (hoặc `erd.dbml`) - do Thành viên A nộp.
  - [ ] `architecture.drawio` - do Thành viên B nộp.
  - [ ] `sequence_release.drawio` - do Thành viên A nộp.
  - [ ] `sequence_checkin.drawio` & `device_state_machine.drawio` - do Thành viên B nộp.
  - [x] `sequence_campaign_rollout.drawio` & `campaign_state_machine.drawio` - do Thành viên C nộp.
- [ ] **3. Tài liệu Nhật ký Prompt AI (`docs/prompt-log.md`):** 1–2 trang ghi rõ prompt, output, phân tích điểm AI gợi ý sai và cách chỉnh sửa - do Thành viên D nộp.
- [ ] **4. Thư mục Mock API Skeleton (`prototype/` - Điểm cộng):** Code chạy được giao diện Swagger UI cho 1 luồng check-in - do Thành viên D nộp.
