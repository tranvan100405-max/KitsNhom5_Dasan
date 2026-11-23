# BÀI LÀM HOÀN CHỈNH CỦA THÀNH VIÊN C (KÈM GIẢI THÍCH TẠI SAO)
## Vai trò: Campaign Engine & Concurrency Engineer — Đề tài DASAN Firmware Rollout

Tài liệu này cung cấp **trọn bộ nội dung đã hoàn thiện** cho phần việc của Thành viên C, bao gồm:
1. Hai file sơ đồ nguồn chuẩn `draw.io` đã tạo sẵn trong thư mục `diagrams/`:
   * [sequence_campaign_rollout.drawio](file:///c:/Kist/diagrams/sequence_campaign_rollout.drawio) *(Dùng cho Slide 7)*
   * [campaign_state_machine.drawio](file:///c:/Kist/diagrams/campaign_state_machine.drawio) *(Dùng cho Slide 8 & Slide 9)*
2. Nội dung trình bày chuẩn cho **Slide 7** và **Slide 9**.
3. **Lập luận "TẠI SAO?"** cho từng quyết định thiết kế (phần quyết định điểm "Tuyển dụng: CÓ").

---

## PHẦN 1: NỘI DUNG SLIDE 7 — LUỒNG 2: TRIỂN KHAI CHIẾN DỊCH & CANARY WAVES

### 1.1. Tóm tắt luồng xử lý (Đưa lên Slide 7 cùng file `sequence_campaign_rollout.drawio`)
1. **Khởi tạo & Khóa nhóm:** Operator gửi `POST /api/campaigns` (trạng thái `DRAFT`) rồi bấm `PATCH /api/campaigns/{id}/start`. Server chiếm khóa phân tán trên Redis (`Lock(targetGroupId)`), lọc các thiết bị hợp lệ (đúng `model`, `currentVersion >= minRequiredVersion`, không có task nào đang chạy).
2. **Chia đợt & Mở Wave 1:** Sinh trước toàn bộ `device_tasks` ở trạng thái `PENDING` gắn theo `waveId` (cộng dồn `1% → 10% → 50% → 100%`, tức cỡ từng đợt là `1% / 9% / 40% / 50%`), chuyển Campaign và Wave 1 sang `RUNNING`.
3. **Cấp phát có kiểm soát:** Thiết bị `check-in` định kỳ (5 phút + Random Jitter). Server kiểm tra Redis Semaphore theo từng campaign (`sem:campaign:{id}`); còn slot thì đổi task sang `DOWNLOADING` và trả Pre-signed URL. Khi thiết bị báo đã tải xong (`stage = INSTALLING`), server trả lại slot tải.
4. **Thăng hạng đợt (Promotion Gate):** Worker chạy mỗi 30 giây. Khi Wave hiện tại đạt tỷ lệ thành công mục tiêu (ví dụ $\ge 95\%$) **và** qua thời gian ngâm (*Soak Time*), hệ thống tự động đóng Wave hiện tại (`COMPLETED`) và mở Wave tiếp theo (`RUNNING`).

### 1.2. Logic chọn thiết bị cho từng đợt (Đặc biệt là Wave 1 - Canary 1%)
* **Wave 1 (1% - Thử nghiệm nhỏ):** Ưu tiên thiết bị nội bộ/lab của ISP, khu vực dân cư ít nhạy cảm, **đại diện đủ các lô phần cứng (hardware revisions)** khác nhau. **Loại trừ tuyệt đối** thiết bị của khách hàng VIP (bệnh viện, cơ quan nhà nước, doanh nghiệp Leased Line).
* **Wave 2 (10%):** Mở rộng theo từng vùng (region) ngẫu nhiên từ nhóm khách hàng phổ thông.
* **Wave 3 (50%) & Wave 4 (100%):** Triển khai diện rộng cho toàn bộ thiết bị còn lại (bao gồm nhóm ưu tiên sau khi đã chứng minh an toàn ở 3 đợt đầu).

### 1.3. Giải thích TẠI SAO thiết kế như vậy?
| Quyết định thiết kế | Tại sao lại chọn cách này? (Lập luận bảo vệ trước hội đồng) |
| :--- | :--- |
| **Tại sao không chọn ngẫu nhiên 100% thiết bị ở Wave 1 (1%)?** | Chọn ngẫu nhiên có thể bốc trúng đường truyền của bệnh viện, ngân hàng hoặc toàn bộ thiết bị cùng một lô sản xuất mới, bỏ sót lỗi phần cứng ở các lô cũ hơn. Chọn có chủ đích (nội bộ + đa dạng phần cứng + loại trừ VIP) giúp phát hiện lỗi sớm mà vẫn bảo toàn SLA cho khách hàng trọng yếu. |
| **Tại sao phải có thời gian ngâm (Soak Time 2–4 giờ) giữa các Wave?** | Nhiều lỗi firmware nguy hiểm như rò rỉ bộ nhớ (*memory leak*), treo tiến trình PPPoE/Wi-Fi hoặc tăng nhiệt độ CPU chỉ bộc phát sau 1–3 giờ vận hành liên tục, không thể thấy ngay lúc thiết bị vừa boot xong. Nếu chuyển đợt ngay lập tức khi vừa `SUCCESS` thì Wave 2 (5.000 thiết bị) vẫn có nguy cơ dính lỗi hàng loạt. |
| **Tại sao tạo sẵn `device_tasks` cho các Wave sau ngay khi Start?** | Để chốt danh sách thiết bị mục tiêu tại thời điểm chiến dịch bắt đầu, tránh việc thiết bị mới thêm vào nhóm giữa chừng làm sai lệch tỷ lệ % và giúp DB kiểm soát ngay ràng buộc không chạy trùng 2 chiến dịch trên cùng một thiết bị. |

---

## PHẦN 2: NỘI DUNG SLIDE 8 & 9 — MÁY TRẠNG THÁI CHIẾN DỊCH, AUTO-PAUSE & ĐỒNG THỜI

### 2.1. Máy trạng thái Chiến dịch (Campaign State Machine)
*(Sử dụng sơ đồ [campaign_state_machine.drawio](file:///c:/Kist/diagrams/campaign_state_machine.drawio))*

* **6 trạng thái chính:** `DRAFT` $\leftrightarrow$ `SCHEDULED` → `RUNNING` $\leftrightarrow$ `PAUSED` → `COMPLETED` / `ABORTED` *(hỗ trợ Operator hủy lịch hẹn `SCHEDULED` → `DRAFT`)*.
* **Tác nhân kích hoạt (Triggers):**
  * `Operator`: Tạo (`DRAFT`), Hẹn giờ (`SCHEDULED`), Hủy lịch (`SCHEDULED` → `DRAFT`), Bấm `Start` / `Pause` / `Resume` / `Abort`.
  * `System Scheduler`: Tự động chuyển `SCHEDULED` → `RUNNING` khi đến `scheduledAt` (khung giờ bảo trì ban đêm).
  * `Auto-Pause Worker`: Tự động chuyển `RUNNING` → `PAUSED` khi tỷ lệ lỗi vượt ngưỡng `failureThresholdPercent` (chạy cơ học, độc lập với AI).
  * `Wave Completion Worker`: Chuyển `RUNNING` → `COMPLETED` khi Wave cuối `COMPLETED` (mọi task kết thúc hoặc quá hạn `deadlineAt` mặc định 24h — thiết bị OFFLINE không làm kẹt chiến dịch).
* **Bảo vệ chuyển trạng thái:** Mọi API điều khiển vòng đời (`PATCH /api/campaigns/{id}/start|pause|resume|abort`) đều kiểm tra máy trạng thái hợp lệ; chuyển sai (ví dụ Resume một chiến dịch đã `ABORTED`) trả về `409 Conflict`.

### 2.2. Thuật toán Tự động Tạm dừng (Auto-Pause Engine)
* **Công thức tính tỷ lệ lỗi:**
  $$\text{FailureRate} = \frac{\text{Count}(\text{FAILED}_{final}) + \text{Count}(\text{TIMEOUT}_{final}) + \text{Count}(\text{ROLLED\_BACK})}{\text{Count}(\text{SUCCESS}) + \text{Count}(\text{FAILED}_{final}) + \text{Count}(\text{TIMEOUT}_{final}) + \text{Count}(\text{ROLLED\_BACK})} \times 100\%$$
  *(Chỉ tính task ở trạng thái kết thúc cuối cùng trong Wave hiện tại; task đang chờ retry không bị tính vào lỗi.)*
* **Thời điểm đánh giá:** Background Worker chạy định kỳ **30 giây/lần**, nhưng **chỉ kích hoạt Auto-Pause khi đạt cỡ mẫu tối thiểu (Cold-Start Guard: $N \ge 50$ thiết bị đã có kết quả trong Wave)** — *hoặc toàn bộ Wave nếu Wave có ít hơn 50 máy đã hoàn tất ít nhất 50%*.
* **Hành động khi kích hoạt:** Đổi `campaigns.status = PAUSED`, `campaign_waves.status = PAUSED`, ghi `audit_logs`, bắn cảnh báo khẩn lên Dashboard cho Operator.

#### Tại sao lại thiết kế công thức và ngưỡng như vậy?
1. **Tại sao mẫu số là "tổng thiết bị ĐÃ KẾT THÚC xử lý", không phải "tổng thiết bị của chiến dịch"?**
   * *Lập luận:* Nếu chiến dịch có 10.000 máy, Wave 1 có 100 máy mới chạy xong 20 máy và **cả 20 máy đều lỗi**. Nếu lấy mẫu số là 10.000 thì tỷ lệ lỗi chỉ là $20/10.000 = 0.2\%$ $\to$ hệ thống tưởng an toàn và tiếp tục đẩy firmware lỗi ra hàng nghìn máy khác! Lấy mẫu số là số máy đã kết thúc trong Wave mới phản ánh đúng xác suất lỗi thực tế ($20/20 = 100\%$).
2. **Tại sao phải có cỡ mẫu tối thiểu ($N \ge 50$)?**
   * *Lập luận:* Tránh **báo động giả (False Positive)**. Khi mới mở đợt, giả sử 2 thiết bị đầu tiên tình cờ bị mất điện nhà dân đúng lúc cập nhật $\to$ tỷ lệ lỗi là $2/2 = 100\%$ và chiến dịch bị dừng oan dù firmware hoàn toàn bình thường.

### 2.3. Xử lý Đồng thời & Kiểm soát Tải tải xuống

#### A. Ngăn 2 Operator cùng Start 2 chiến dịch chứa chung thiết bị (Concurrency Control)
Triển khai **bảo vệ 2 lớp (Defense-in-Depth)**:
1. **Lớp ứng dụng (Redis Distributed Lock):** Khi gọi `PATCH /api/campaigns/{id}/start`, server giữ lock theo `targetGroupId` (đủ để chống xung đột vì mỗi thiết bị chỉ thuộc 1 group). Hai lệnh Start đồng thời sẽ tuần tự hóa; lệnh sau thấy thiết bị đã có task active sẽ trả về `409 Conflict` kèm danh sách thiết bị đang bận.
2. **Lớp cơ sở dữ liệu (Partial Unique Index):**
   ```sql
   CREATE UNIQUE INDEX uq_device_active_task
   ON device_tasks (deviceId)
   WHERE status IN ('PENDING', 'DOWNLOADING', 'INSTALLING', 'VERIFYING');
   ```
* **Tại sao phải dùng cả Redis Lock lẫn Partial Unique Index?**
  * *Lập luận:* Redis Lock giúp phản hồi nhanh và tránh tranh chấp ở tầng API, nhưng trong môi trường phân tán (nhiều API instance), khóa Redis vẫn có xác suất nhỏ hết hạn (TTL expiry) hoặc trễ mạng. **Partial Unique Index ở DB là chốt chặn cuối cùng (Last Line of Defense)** đảm bảo tuyệt đối 100% ở mức dữ liệu không bao giờ có 2 task active cùng lúc trên 1 thiết bị.

#### B. Kiểm soát tải tải xuống (`maxConcurrentDevices`)
* **Cơ chế:** Dùng **Redis Semaphore theo từng chiến dịch** (`sem:campaign:{id}`) với dung lượng đúng bằng `maxConcurrentDevices` (ví dụ: 500 slots).
  * Thiết bị check-in $\to$ Chỉ khi xin được 1 token từ Redis mới chuyển sang `DOWNLOADING` và nhận Pre-signed URL. Nếu hết slot, server trả `"NO_TASK"` để thiết bị thử lại ở chu kỳ check-in sau (5 phút).
  * Thiết bị báo đã tải xong (`stage = INSTALLING`) hoặc báo lỗi/timeout ở bước tải (`FAILED` / `TIMEOUT`) $\to$ Giải phóng (trả) 1 token về lại Redis ngay để nhường lượt tải cho thiết bị kế tiếp. Worker quét timeout sẽ thu hồi token nếu thiết bị im lặng quá 15 phút.
* **Tại sao dùng Redis Semaphore thay vì `SELECT COUNT(*) FROM device_tasks WHERE status = 'DOWNLOADING'` mỗi lần check-in?**
  * *Lập luận:* Khi có 333–3.000 thiết bị check-in/giây (lúc cao điểm Thundering Herd), việc chạy câu lệnh `COUNT(*)` liên tục trên bảng `device_tasks` hàng triệu dòng sẽ gây nghẽn khóa đọc/ghi Database. Đếm và cấp phát nguyên tử (atomic `DECR`/`INCR` hoặc Lua script) trên Redis xử lý trong vài micro-giây, bảo vệ DB hoàn toàn. *(Nếu Redis gặp sự cố, hệ thống mới fallback về truy vấn DB có index `(campaignId, status)`).*

---

## PHẦN 3: KỊCH BẢN NÓI KHI THUYẾT TRÌNH (DỰ KIẾN ~2.5 PHÚT CHO THÀNH VIÊN C)

> **Slide 7 (~1 phút 15 giây):**
> *"Tiếp nối luồng thiết bị check-in, em xin trình bày bộ máy điều phối chiến dịch. Khi Operator bấm Start, hệ thống không đẩy firmware ồ ạt cho toàn bộ 50.000 thiết bị vì rủi ro mất Internet diện rộng rất lớn. Thay vào đó, chúng em chia chiến dịch thành các đợt tăng dần: 1% → 10% → 50% → 100%. Đặc biệt ở đợt Canary 1%, thiết bị không được chọn ngẫu nhiên mà ưu tiên thiết bị nội bộ, phủ đủ các đời phần cứng và loại trừ tuyệt đối khách hàng VIP. Giữa các đợt bắt buộc có thời gian ngâm (Soak Time) 2–4 giờ để bắt các lỗi ẩn như memory leak trước khi tự động mở đợt tiếp theo."*
>
> **Slide 9 (~1 phút 15 giây):**
> *"Về mặt an toàn vận hành, vòng đời chiến dịch được quản lý chặt qua máy trạng thái 6 bước. Để phát hiện sớm firmware lỗi, Auto-Pause Worker quét mỗi 30 giây theo tỷ lệ lỗi trên số thiết bị đã hoàn tất của Wave, kèm ngưỡng cỡ mẫu tối thiểu 50 máy để tránh báo động giả. Để tránh 2 Operator cùng chạy đè firmware lên một thiết bị, nhóm áp dụng bảo vệ 2 lớp gồm Redis Distributed Lock ở tầng API và Partial Unique Index ở tầng Database. Cuối cùng, nhằm giữ mạng ISP không quá tải khi tải file 50MB, chúng em dùng Redis Semaphore giới hạn đúng `maxConcurrentDevices` thiết bị được tải đồng thời."*
