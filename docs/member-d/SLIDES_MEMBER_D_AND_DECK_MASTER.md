# HỒ SƠ SLIDE THÀNH VIÊN D & BẢN ĐIỀU PHỐI TỔNG THỂ 16 SLIDE
## Đề tài: Nền tảng Triển khai Cập nhật Firmware (Firmware Rollout Platform) — DASAN Vietnam (KITS 2026 OJT)

| | |
| :--- | :--- |
| **Người điều phối** | Thành viên D — *System Reliability, Security, AI Lead & Project Coordinator* |
| **Phạm vi tài liệu** | Nội dung chi tiết + Lời dẫn thuyết trình cho **8 slide của Thành viên D** (**Slide 1, 2, 10, 11, 13, 14, 15, 16** + dòng bổ sung **Slide 9**) và **Khung điều phối 16 Slide toàn nhóm** |
| **Thời lượng chuẩn** | **10 phút trình bày** (`2,5 phút × 4 thành viên`) + **3–5 phút Hỏi đáp (Q&A)** |
| **Checklist đáp ứng** | `docs/checklists/system-design-gate.md` — **CHK028, CHK029, CHK037, CHK038** |

---

## PHẦN I. KHUNG ĐIỀU PHỐI 16 SLIDE & PHÂN BỔ THỜI GIAN (10 PHÚT = 600 GIÂY)

| Slide | Tiêu đề Slide | Chủ trì | Thời lượng | Sơ đồ / Tài liệu nguồn đối chiếu |
| :-: | :--- | :-: | :-: | :--- |
| **1** | Trang bìa: Firmware Rollout Platform | **D** | `15s` | Tên nhóm, 4 thành viên, DASAN Vietnam |
| **2** | Xác định vấn đề, Mục tiêu, Ngoài phạm vi & Giả định | **D** | `35s` | Bối cảnh đề bài trang 2–3 |
| **3** | Tác nhân, Ca sử dụng & Bảng thuật ngữ thống nhất | **A** | `40s` | `docs/member-a/SLIDE_03_ACTORS_AND_GLOSSARY.md` |
| **4** | Mô hình miền dữ liệu (ERD) & Giải trình 5 câu hỏi Bước 1 | **A** | `65s` | `diagrams/erd.dbml` · `docs/member-a/ERD_DESIGN_QA.md` |
| **5** | Tổng quan kiến trúc, Lập luận chọn Pull + Tách tải CDN | **B** | `45s` | `diagrams/architecture.mmd` · `docs/member-b/DEVICE_AGENT_DESIGN.md` |
| **6** | Luồng 1: Phát hành, Phê duyệt 4-mắt & Quy tắc tương thích | **A** | `45s` | `diagrams/sequence_release.mmd` · `docs/member-a/FIRMWARE_COMPATIBILITY_MATRIX.md` |
| **7** | Luồng 2: Triển khai chiến dịch, Canary Wave & Slot tải | **C** | `55s` | `diagrams/sequence_campaign_rollout.drawio` · `Member_C_Deliverables.md` |
| **8** | Hai máy trạng thái: Campaign *(Trái)* & Device Task *(Phải)* | **C + B** | `55s` (`25s+30s`) | `diagrams/campaign_state_machine.drawio` · `diagrams/device_state_machine.mmd` |
| **9** | Xử lý lỗi, Dual-Bank A/B, Auto-Pause & Emergency Rollback | **B + C** *(D góp 1 dòng)* | `65s` (`35s+30s`) | `DEVICE_AGENT_DESIGN.md` · `Member_C_Deliverables.md` · `EMERGENCY_ROLLBACK_DESIGN.md` |
| **10** | Quy mô, Năng lực, Điểm nghẽn & Kịch bản mở rộng ×10 | **D** | `35s` | `docs/member-d/CAPACITY_ESTIMATION.md` · `capacity_calc.py` |
| **11** | Bảo mật: Ma trận RBAC, Xác thực thiết bị HMAC & Audit Trail | **D** | `30s` | `docs/member-d/RBAC_SECURITY_AUDIT.md` |
| **12** | Phác thảo API RESTful & Chi tiết 3 Endpoint cốt lõi `(*)` | **B** | `40s` | `DEVICE_AGENT_DESIGN.md` · `Member_C_Deliverables.md` §6 |
| **13** | Ứng dụng AI/LLM: Phân loại log lỗi, Validator & Ca sửa lỗi thật | **D** | `25s` | `docs/member-d/AI_LOG_CLASSIFIER_DESIGN.md` · `docs/prompt-log.md` |
| **14** | Đánh đổi thiết kế (Trade-offs) & Lộ trình MVP | **D** | `20s` | `DASAN_OJT1_System_Design_Specification.md` §1 |
| **15** | Đóng góp cá nhân của 4 thành viên & Bài học kinh nghiệm | **D** | `15s` | Lịch sử nhánh Git & tài liệu từng thành viên |
| **16** | Tổng kết, Demo nhanh Prototype / Validator & Hỏi đáp (Q&A) | **Cả nhóm** | `15s` *(+ Q&A)* | `prototype/` (B) · `docs/member-d/mock_platform_demo.py` (D) |

> **Kiểm tra tổng thời lượng từng thành viên (cân bằng đúng 150 giây/người):**
> * **Thành viên A** *(Slide 3, 4, 6)*: `40 + 65 + 45` = **`150s` (2 phút 30 giây)**
> * **Thành viên B** *(Slide 5, 8-phải, 9-đầu, 12)*: `45 + 30 + 35 + 40` = **`150s` (2 phút 30 giây)**
> * **Thành viên C** *(Slide 7, 8-trái, 9-sau + kết nối)*: `55 + 25 + 30 + 40 (phần Concurrency/Dashboard Slide 7-9)` ≈ **`150s` (2 phút 30 giây)**
> * **Thành viên D** *(Slide 1, 2, 10, 11, 13, 14, 15, 16)*: `15 + 35 + 35 + 30 + 25 + 20` (+ chuyển ý 15–16) ≈ **`150s` (2 phút 30 giây)**

---

## PHẦN II. NỘI DUNG CHI TIẾT CÁC SLIDE DO THÀNH VIÊN D PHỤ TRÁCH

---

### SLIDE 1 — TRANG BÌA (COVER SLIDE)

* **Tiêu đề chính:** **FIRMWARE ROLLOUT PLATFORM — SYSTEM DESIGN**
* **Tiêu đề phụ:** Nền tảng triển khai cập nhật Firmware an toàn, theo đợt cho `100.000+` thiết bị mạng ISP
* **Doanh nghiệp ra đề:** **DASAN Vietnam** · Chương trình **2026 KITS Hanoi OJT (SW Developer Track)**
* **Đội hình Nhóm 5 (4 thành viên):**
  1. **Thành viên A** — *Domain & Data Architect* (ERD chuẩn hóa, Luồng phát hành & Quy tắc tương thích)
  2. **Thành viên B** — *Device Agent & Edge Protocol Specialist* (Cơ chế Pull, State Machine thiết bị, Dual-Bank A/B, REST API & Prototype)
  3. **Thành viên C** — *Campaign Engine & Concurrency Engineer* (Canary Wave, Auto-Pause, Concurrency 2 lớp, Semaphore & Observability)
  4. **Thành viên D** — *System Reliability, Security, AI Lead & Coordinator* (Capacity Planning, RBAC/HMAC/Audit, AI Log Classifier & Rollback)

🎤 **Lời dẫn (15s):** *"Xin chào đại diện doanh nghiệp DASAN Vietnam và hội đồng đánh giá. Nhóm 5 xin trình bày bản thiết kế hệ thống **Firmware Rollout Platform** — giải pháp quản lý và cập nhật firmware an toàn cho hàng trăm nghìn thiết bị mạng quang và bộ chuyển mạch tại các nhà mạng ISP."*

---

### SLIDE 2 — XÁC ĐỊNH VẤN ĐỀ, MỤC TIÊU, PHẠM VI & GIẢ ĐỊNH

#### 1. Nỗi đau vận hành thực tế (Problem Statement)
* **Thủ công & Mù tiến độ:** Kỹ sư nạp file lẻ lên từng thiết bị và theo dõi bằng Excel $\to$ không biết chính xác bao nhiêu máy đang chạy phiên bản nào, bao nhiêu máy cập nhật dở bị rớt mạng.
* **Rủi ro thảm họa diện rộng (Blast Radius):** Đẩy đồng loạt 1 bản firmware lỗi hoặc mất điện lúc ghi flash có thể làm **hàng chục nghìn hộ gia đình mất Internet cùng lúc**, buộc ISP cử kỹ thuật viên tới từng nhà nạp lại ROM.

#### 2. Mục tiêu thiết kế cốt lõi (Design Goals)
* **Zero-Brick & Zero-Outage:** Cập nhật thất bại tuyệt đối không làm gián đoạn dịch vụ (Dual-Bank A/B + Watchdog + Canary `1% → 10% → 50% → 100%` + Auto-Pause cơ học).
* **Kiểm soát tải hạ tầng:** Xử lý mượt `100.000` thiết bị check-in và `20 Gbps` băng thông tải firmware mà không sập API hay Origin Storage.
* **Quản trị chặt chẽ:** Phê duyệt 4-mắt (`uploadedBy ≠ approvedBy`), tách 2 miền xác thực và lưu vết kiểm toán bất biến (`audit_logs`).

#### 3. Phân định rõ Trong phạm vi vs. Ngoài mục tiêu (Scope & Non-Goals)
| Trong phạm vi (In-Scope) | Ngoài mục tiêu (Explicit Non-Goals) |
| :--- | :--- |
| • Quản lý vòng đời Firmware, duyệt 4-mắt & kiểm tra tương thích.<br>• Điều phối Campaign theo đợt Canary, Auto-Pause, giới hạn tải đồng thời & Khung giờ bảo trì đa múi giờ.<br>• Giao thức Edge Check-in (Pull), Dual-Bank Rollback & Emergency Rollback sau chiến dịch.<br>• Phân loại nhóm log lỗi bằng AI (chỉ gợi ý tham khảo). | • **Không** viết mã C/RTOS cấp thấp của Bootloader phần cứng (giả định phần cứng DASAN đã hỗ trợ Dual-Bank & Watchdog).<br>• **Không** thay thế hệ thống quản lý cấu hình thuê bao hằng ngày (PPPoE/VLAN/VoIP kiểu ACS TR-069 toàn phần).<br>• **Không** cho phép AI tự động thực thi bất kỳ lệnh dừng, hủy hay rollback nào. |

#### 4. Các giả định nền tảng (Key Assumptions)
* Fleet `100.000` thiết bị (`~20` models, `30` khách hàng ISP) đặt sau NAT/Firewall khách hàng, IP động, chu kỳ check-in `5 phút`, kích thước image `~50 MB`.

🎤 **Lời dẫn (35s):** *"Bài toán đặt ra rất rõ: cập nhật cho 100.000 ONT/Router giống như cập nhật OS cho 100.000 máy khách nhưng **thất bại tuyệt đối không được làm mất mạng hộ gia đình**. Thay vì quy trình Excel thủ công rủi ro cao, hệ thống của nhóm đặt 3 chốt chặn: Canary theo đợt có Auto-pause, phần cứng Dual-Bank chống brick và tách tải CDN. Nhóm cũng xác định rõ ngoài phạm vi: không can thiệp firmware bootloader gốc và tuyệt đối không trao quyền điều khiển tự động cho AI."*

---

### SLIDE 10 — QUY MÔ, NĂNG LỰC, ĐIỂM NGHẼN & KỊCH BẢN MỞ RỘNG ×10

*(Nguồn chi tiết & script kiểm chứng: [`docs/member-d/CAPACITY_ESTIMATION.md`](CAPACITY_ESTIMATION.md) & [`capacity_calc.py`](capacity_calc.py))*

#### Bảng số liệu cốt lõi (Tất cả tái lập tự động bằng `capacity_calc.py`)
| Chỉ số năng lực | Công thức & Giả định chính | Kết quả | Hệ quả kiến trúc bắt buộc |
| :--- | :--- | :--- | :--- |
| **Check-in trung bình & Đỉnh** | `100.000 / 300s` · Herd `30%` fleet online lại trong `10–20s` (tải API chỉ `~24 Mbps`) | **`333 RPS`** TB<br>**`1.500–3.000 RPS`** đỉnh | Lệch pha cố định `hash(serialNo) mod 300` + Full-Jitter Backoff (hạ đỉnh về `~433 RPS`) + Stateless Autoscale |
| **Dữ liệu đợt 10% & Cả chiến dịch** | Chiến dịch `50.000` máy × `50 MB`:<br>• Mốc `10%` cộng dồn (Q1) = `5.000` máy<br>• Riêng Wave 2 (`+9%`) = `4.500` máy | **`250 GB`** *(10% cộng dồn)*<br>**`225 GB`** *(riêng Wave 2)*<br>**`2,5 TB`** / campaign | Phân biệt rạch ròi mốc cộng dồn Q1 và kích thước từng đợt (`500 / 4.500 / 20.000 / 25.000` máy) |
| **Băng thông Egress đỉnh** | `maxConcurrentDevices (500)` × `5 MB/s` (`40 Mbps`/máy; nếu không khóa slot = `2 Tbps`) | **`2,5 GB/s = 20 Gbps`** | **Điểm nghẽn #1:** Bắt buộc **S3 + Multi-PoP CDN (~50 PoP)** + Pre-signed URL (Origin chỉ phát `~2,5 GB`, giảm `1.000×`) |
| **Thời gian hoàn tất `50.000` máy** | Slot chỉ giữ lúc `DOWNLOADING` (`10s`/máy $\Rightarrow$ `50 lượt/s` — Q6) $\Rightarrow$ tải + cài 4 wave chỉ **~49 phút**! | **`~4,8h`** *(máy ONLINE)*<br>**`~5,8–8,0h`** *(cắt straggler)*<br>**`100h`** *(chờ đủ 24h Q7)* | Thời gian bị chi phối bởi **Soak Time (4h)** và **chính sách hạn chót máy OFFLINE**, không phải băng thông |
| **Tăng trưởng DB / năm** | `10` đợt lớn (`500k` lượt cập nhật/năm), retry cộng trên cùng dòng; không ghi heartbeat vào audit | **`500k`** `device_tasks`/năm<br>**`≤ 2,5M`** `audit_logs`/năm (`~1,4 GB`) | Ghi `lastCheckInAt` vào Redis rồi **batch flush 30–60s**; Partition theo tháng + Cold Storage sau 12 tháng |

#### Khi quy mô tăng gấp 10 lần (`1.000.000` thiết bị — Cái gì gãy trước?)
1. **Gãy #1 — Egress 1 vùng CDN (`200 Gbps`, `25 TB`/campaign):** Chuyển sang **Multi-Region / Local ISP CDN** + chia **ngân sách slot tải theo từng vùng ISP** (ví dụ `500 slot × 10 vùng`) thay vì 1 semaphore toàn cục.
2. **Gãy #2 — Burst Check-in (`15.000–30.000 RPS`, `105 tỷ` req/năm):** Bật HTTP/2 Keep-Alive + TLS Session Resumption, đặt **Kafka/Queue** đệm đường ghi trạng thái.
3. **Gãy #3 — Hot key Redis & Bảng lớn (`5M` task + `25M` audit/năm):** Nâng cấp **Redis Cluster** shard theo `campaignId` và Range Partitioning theo tháng.

🎤 **Lời dẫn (35s):** *"Về quy mô, 333 RPS check-in trung bình chỉ tốn 2,7 Mbps, nhưng có 2 con số quyết định kiến trúc: Thứ nhất là **20 Gbps băng thông tải đỉnh** — buộc phải tách data-plane sang CDN bằng Pre-signed URL để giảm tải Origin 1.000 lần. Thứ hai, nhờ trả slot ngay sau bước tải (Q6), phần tải và cài 50.000 máy thực tế chỉ mất **49 phút**; tổng thời gian chiến dịch 5 đến 8 giờ nằm ở **Soak Time** và hạn chót thiết bị OFFLINE. Khi mở rộng gấp 10 lần lên 1 triệu máy, Egress 200 Gbps và Burst 30.000 RPS sẽ gãy trước DB, nên giải pháp là chia ngân sách slot theo PoP nhà mạng và đệm qua Queue + Redis Cluster."*

---

### SLIDE 11 — BẢO MẬT, PHÂN QUYỀN RBAC & NHẬT KÝ KIỂM TOÁN

*(Nguồn chi tiết: [`docs/member-d/RBAC_SECURITY_AUDIT.md`](RBAC_SECURITY_AUDIT.md))*

#### 1. Ma trận RBAC tối thiểu quyền & Tách nhiệm vụ (4 Role + Edge Device)
| Nhóm API (Đủ 17 thao tác Bước 3) | ADMIN | DEVELOPER | QA | OPERATOR | Edge Device | Chốt chặn nghiệp vụ & Mã lỗi |
| :--- | :-: | :-: | :-: | :-: | :-: | :--- |
| `POST /api/firmware` *(Upload)* | ✘ | **✔** | ✘ | ✘ | ✘ | Sai role $\to$ `403`; trùng `(model, versionNo)` $\to$ `409` |
| `PATCH /api/firmware/{id}/approve` | ✘ *(override có audit)* | ✘ | **✔\*** | ✘ | ✘ | **Four-eyes 3 lớp** (UI + Service `FOR UPDATE` + DB `CHECK uploadedBy <> approvedBy`) $\to$ vi phạm trả **`403 FOUR_EYES_VIOLATION`** |
| `PATCH /api/firmware/{id}/deprecate` | **✔** | ✘ | ✘ | ✘ | ✘ | Khóa ngay bản lỗi; chặn tạo/mở wave mới |
| `POST / PATCH /api/campaigns/*` | ✘ *(break-glass)* | ✘ | ✘ | **✔\*** | ✘ | Chỉ firmware `APPROVED`; sai trạng thái $\to$ `409` |
| `GET /firmware · /devices · /progress · /tasks` | ✔ | ✔* *(debug)* | ✔* | ✔* | ✘ | Lọc dữ liệu theo vai trò (Read-only cho QA/Dev) |
| `GET /api/audit-logs` | **✔** | ✘ | ✘ | ✘ | ✘ | Chỉ `ADMIN` tra cứu điều tra sự cố |
| `POST /api/device-agent/check-in` & `/result` | ✘ | ✘ | ✘ | ✘ | **✔\*** | Miền xác thực riêng; báo task máy khác $\to$ `403 TASK_NOT_OWNED` |

> **Điểm mạnh cốt lõi:** Không tồn tại bất kỳ một cá nhân nào tự đi hết chuỗi *Upload $\to$ Approve $\to$ Rollout $\to$ Deprecate*. Kể cả `ADMIN` cũng không được tự upload rồi tự duyệt.

#### 2. Vì sao tách 2 miền xác thực: JWT (Web) vs. HMAC-SHA256 6 thành phần (Thiết bị)?
* **Web Portal (`JWT 15'` + Argon2id + Redis `jti` deny-list):** Phù hợp phiên đăng nhập người dùng có vai trò RBAC.
* **Thiết bị cạnh (`HMAC-SHA256(serialNo + timestamp + nonce + METHOD + PATH + SHA256(body))`):**
  * **Chống Replay & Chống sửa Body:** Cửa sổ `±300s` + Redis Nonce dùng 1 lần (`SET NX EX 600` chỉ ghi **sau** khi verify chữ ký) + khóa chặt cả đường dẫn lẫn mã băm payload.
  * **Cô lập bán kính thiệt hại (Blast Radius = 1 máy):** Secret riêng từng thiết bị lưu tách biệt tại `device_credentials` / KMS. Lộ 1 thiết bị chỉ xoay khóa/cách ly đúng máy đó, không ảnh hưởng 99.999 máy còn lại (nếu dùng chung khóa JWT thì sập toàn fleet; mTLS là bước nâng cấp Production).

#### 3. Thiết kế `audit_logs` bất biến (Append-Only 5 lớp)
* `actorType ∈ {MEMBER, SYSTEM, DEVICE}` (`actorId` nullable khi `SYSTEM`/`DEVICE`, khớp `CHECK` trên ERD).
* **5 lớp bảo vệ:** Không có API sửa/xóa $\to$ DB `REVOKE UPDATE, DELETE` $\to$ Trigger chặn sửa $\to$ Hash-chain phát hiện can thiệp $\to$ Xuất WORM/SIEM định kỳ.
* **Ghi cả hành vi bị từ chối (`401/403`)** nhưng **tuyệt đối cấm ghi heartbeat check-in** (giữ mức `~2,5M` dòng/năm thay vì `10,5 tỷ` dòng/năm).

🎤 **Lời dẫn (30s):** *"Ở tầng bảo mật, hệ thống tách cứng 2 miền xác thực: Người dùng web dùng JWT kèm ma trận RBAC sao cho không một ai đi trọn vòng đời từ upload, duyệt đến chạy chiến dịch; nguyên tắc 4-mắt được khóa tới tận tầng Database CHECK constraint. Với 100.000 thiết bị, nhóm không dùng JWT mà dùng HMAC 6 thành phần kèm Nonce 1 lần trên Redis để khóa chặt nội dung bản tin và cô lập rủi ro lộ khóa ở đúng 1 thiết bị. Mọi thao tác kể cả lần bị từ chối 403 đều ghi append-only vào `audit_logs`."*

---

### SLIDE 13 — ỨNG DỤNG AI / LLM: PHÂN LOẠI NHẬT KÝ LỖI & NHẬT KÝ SỬA LỖI THẬT

*(Nguồn thiết kế, code & nhật ký thực nghiệm: [`AI_LOG_CLASSIFIER_DESIGN.md`](AI_LOG_CLASSIFIER_DESIGN.md) · [`validate_output.py`](validate_output.py) · [`docs/prompt-log.md`](../prompt-log.md))*

#### 1. Kiến trúc tích hợp an toàn (Phương án C: Error Log Clustering & Suggested Action)
* **Vị trí:** Async Read-Only Worker, chỉ chạy khi Campaign `PAUSED` hoặc Wave `COMPLETED` (`tasksTerminal ≥ 50`).
* **Đầu vào đã gom nhóm & ẩn danh:** SQL gom lỗi thành `≤ 20` nhóm `errorGroups[]` (~`1,5 KB`, tiết kiệm `99,8%` token so với log thô), đổi `serialNo` thật sang `SN-####`, cắt toàn bộ tên ISP/IP/secret.
* **Prompt đủ 5 thành phần + JSON Schema đóng (`additionalProperties: false`):** Ép phân loại vào **8 nhãn nguyên nhân gốc** và **6 hành động tham khảo** — trong miền giá trị **hoàn toàn không có `abort`, `pause`, `rollback`**.

#### 2. Ba tầng kiểm định đầu ra (`validate_output.py`) & Fallback độc lập
1. **Tầng 1 (JSON Schema):** Kiểu dữ liệu, biên `confidence [0..1]`, độ dài chuỗi, cấm trường tự chế.
2. **Tầng 2 (Đối chiếu ngữ nghĩa Input):** Mọi `errorCode` và `deviceRef` AI trích dẫn **bắt buộc phải tồn tại trong Input**; `deviceCount ≤ taskCount`; quét chặn rò rỉ `DSN-...` / email và cảnh báo Prompt Injection.
3. **Tầng 3 (Human-in-the-loop & Fallback):** `OPERATOR` tự duyệt; nếu LLM timeout/lỗi hoặc bị Validator bác bỏ $\to$ **chỉ ẩn khung gợi ý AI, bộ máy Auto-Pause cơ học của Thành viên C vẫn bảo vệ mạng độc lập 100%**.

#### 3. Kết quả thực nghiệm thật & Tình huống AI sai đã được nhóm phát hiện, sửa đổi (`docs/prompt-log.md`)
* **Giá trị thực tế (Sample 03):** Khi `18/860` máy bị Watchdog `ROLLED_BACK` (`2,09% < ngưỡng 5%` nên Auto-pause cơ học chưa dừng), AI phát hiện mẫu `Kernel panic` trên cả 2 vùng và gắn nhãn `HIGH / BOOT_VERIFY → recommend_review_firmware`, cứu chiến dịch trước khi mở Wave 50%.
* **3 lỗi thật phát hiện khi chạy Prompt v1 (Pass 3/5 = 60%) $\to$ Sửa ở Prompt v2 & Validator (Pass 5/5 = 100%):**
  1. *Lỗi echo Prompt Injection (Sample 05):* Prompt v1 bảo AI *"trích dẫn chuỗi bất thường"*, làm AI chép nguyên văn câu lệnh độc hại `"ignore previous instructions..."` vào `evidence`, kích hoạt cảnh báo `SEM_INJECTION_ECHO` $\to$ **Sửa ở Prompt v2:** Chỉ mô tả gián tiếp theo đường dẫn trường + gắn cờ `SUSPICIOUS_INSTRUCTION_TEXT`.
  2. *Lỗi vượt trần ký tự (Sample 01 & 05):* Prompt v1 thiếu giới hạn độ dài `evidence`/`limitations`, AI sinh chuỗi `282–293` ký tự bị Validator chặn (`SCHEMA_MAX_LENGTH`) $\to$ **Sửa ở Prompt v2:** Khóa trần `≤ 160` ký tự/dòng.
  3. *Lỗi lệch quy ước nghiệp vụ Q7 (Sample 04):* AI gợi ý `retry_later` cho lỗi `WAVE_DEADLINE_EXCEEDED` dù Q7 quy định hết hạn wave không tự retry $\to$ **Sửa ở Prompt v2:** Bổ sung luật Q7/Q9 vào khối bối cảnh nghiệp vụ, AI đổi sang `investigate` chuẩn xác.

🎤 **Lời dẫn (25s):** *"Với tính năng AI, nhóm chọn Phương án C: gom hàng nghìn log lỗi đã ẩn danh thành vài nhóm nguyên nhân gốc để rút ngắn thời gian chẩn đoán cho Operator. AI bị khóa chặt bằng JSON Schema không chứa bất kỳ lệnh hủy hay rollback nào, đi qua bộ lọc `validate_output.py` đối chiếu từng mã lỗi với input thật. Thực tế khi chạy thử Prompt v1 trên 5 kịch bản, Validator đã chặn đứng 2 kết quả do tràn độ dài và lặp lại câu lệnh Prompt Injection, đồng thời nhóm phát hiện AI gợi ý `retry_later` sai quy ước Q7 — sau khi tinh chỉnh lên Prompt v2, cả 5/5 kịch bản đều vượt qua kiểm định tuyệt đối."*

---

### SLIDE 14 — ĐÁNH ĐỔI THIẾT KẾ (ARCHITECTURAL TRADE-OFFS) & LỘ TRÌNH MVP

#### 1. Bảng 5 Quyết định Đánh đổi Thiết kế Cốt lõi (Trade-offs)
| Quyết định được chọn | Phương án bị loại bỏ | Lý do kỹ thuật & Đánh đổi chấp nhận |
| :--- | :--- | :--- |
| **1. Giao tiếp `PULL` định kỳ 5' + Lệch pha `serialNo` & Jitter** | • `PUSH` trực tiếp từ Server<br>• Kết nối `MQTT / WebSocket` thường trực | **Loại Push** vì 100k ONT nằm sau NAT/Firewall ISP, IP động. **Loại MQTT** vì nuôi 100k kết nối tốn RAM/FD không cần thiết. *Đánh đổi:* Chấp nhận độ trễ nhận lệnh tối đa `≤ 5 phút` — hoàn toàn phù hợp bài toán cập nhật firmware. |
| **2. Tách tải nhị phân qua `S3 + Multi-PoP CDN` (Pre-signed URL 15')** | • Tải file qua Backend API trung gian | **Loại Backend Stream** vì `20 Gbps` egress sẽ làm nghẹt API Gateway và đánh sập luôn luồng check-in. *Đánh đổi:* Phải quản lý vòng đời Pre-signed URL ngắn hạn và đồng bộ cache PoP. |
| **3. Tách bảng `campaign_waves` + Partial Unique Index trên PostgreSQL** | • Lưu mảng JSON waves trong `campaigns`<br>• Chỉ khóa đồng thời trên tầng code / Redis | **Loại JSON** vì không thể FK/JOIN tính tỷ lệ lỗi từng đợt. **Loại khóa đơn lớp** vì Redis có thể mất khóa khi failover — Partial Unique Index là chốt chặn ACID cuối cùng chống 1 máy nhận 2 task. |
| **4. Phần cứng `Dual-Bank A/B` + `HMAC-SHA256` 6 thành phần theo máy** | • `Single-Bank` ghi đè trực tiếp<br>• Dùng chung `JWT` cho thiết bị | **Loại Single-Bank** vì mất điện khi flash sẽ biến ONT thành "cục gạch". **Loại JWT thiết bị** vì lộ khóa ký sẽ mất toàn bộ fleet. *Đánh đổi:* Tốn gấp đôi bộ nhớ Flash cho phân vùng phụ và cần kho `device_credentials`. |
| **5. `Auto-Pause cơ học` độc lập + `AI chỉ đọc & gợi ý`** | • Cho LLM tự động Pause / Abort / Rollback chiến dịch | **Loại AI tự quyết** vì LLM mang tính xác suất và đọc dữ liệu không đáng tin từ thiết bị (dễ bị Prompt Injection gây DoS nghiệp vụ). *Đánh đổi:* Operator vẫn phải bấm xác nhận cuối cùng. |

#### 2. Lộ trình triển khai: MVP (Bàn giao ngay) vs. Post-MVP (Mở rộng Production)
| Hạng mục | Giai đoạn MVP (Trong bài thiết kế & Prototype) | Giai đoạn Post-MVP / Production Scale (`1M+` thiết bị) |
| :--- | :--- | :--- |
| **Giao thức & Tải file** | Pull HTTP/2 + Jitter, tải nguyên ảnh `50 MB` qua Pre-signed URL, giới hạn `maxConcurrentDevices` theo campaign. | **Delta Binary Update** (`bsdiff`, giảm `50 MB → 3–5 MB`), chia ngân sách slot tải theo từng vùng PoP ISP; Rollback chuyển thẳng phân vùng nếu image cũ trên Bank phụ khớp SHA-256. |
| **Bảo mật thiết bị** | `HMAC-SHA256` (6 thành phần) + Nonce chống replay + kho khóa tách biệt. | **Mutual TLS (mTLS)** gắn chứng chỉ X.509 trong chip phần cứng **TPM / Secure Element** + tự động xoay khóa định kỳ. |
| **Lưu trữ & Kiểm toán** | PostgreSQL chuẩn hóa 9 bảng + Trigger Append-only `audit_logs` + Redis Cache/Semaphore. | Tự động Range Partitioning `device_tasks`/`audit_logs` theo tháng, đẩy lưu trữ lạnh **S3 Object Lock (WORM)** + SIEM, Kafka đệm luồng check-in. |
| **AI & Quan sát** | Phân loại nhóm lỗi tại mốc `PAUSED` / `WAVE_COMPLETED` qua JSON Schema + Validator 2 tầng. | Đối chiếu chéo biến động chất lượng đường truyền quang (PON Rx Power) hậu cập nhật để tự động cảnh báo suy hao sớm. |

🎤 **Lời dẫn (20s):** *"Mọi quyết định trong kiến trúc đều dựa trên sự đánh đổi có chủ đích: chúng tôi chấp nhận độ trễ tối đa 5 phút của cơ chế Pull để đổi lấy khả năng xuyên NAT 100% và vận hành nhẹ nhàng; chấp nhận tốn gấp đôi bộ nhớ Flash Dual-Bank để đổi lấy cam kết không bao giờ làm brick thiết bị khách hàng; và tách bạch ranh giới MVP gọn chắc với lộ trình nâng cấp lên Delta Update, mTLS TPM và Multi-Region CDN ở quy mô hàng triệu thiết bị."*

---

### SLIDE 15 — ĐÓNG GÓP CÁ NHÂN & BÀI HỌC KINH NGHIỆM

#### 1. Dấu ấn đóng góp rõ ràng của từng thành viên trên Git Repository
| Thành viên | Nhánh / Thư mục chính | Sản phẩm thiết kế & Mã nguồn bàn giao cụ thể |
| :--- | :--- | :--- |
| **Thành viên A**<br>*(Domain & Data)* | `main` · `diagrams/` · `docs/member-a/` | • Mô hình ERD chuẩn hóa 9 bảng (`diagrams/erd.dbml` + `erd.mmd`/`erd.png`) kèm `CHECK` 4-mắt & Partial Unique Index.<br>• Giải trình sâu 5 câu hỏi dữ liệu Bước 1, Luồng 1 Phát hành/Phê duyệt (`diagrams/sequence_release.mmd`) & Ma trận tương thích `versionCode`. |
| **Thành viên B**<br>*(Device & Protocol)* | `feature/tv-b-device` · `docs/member-b/` · `prototype/` | • Kiến trúc tổng quan, lập luận Pull + Jitter, Luồng Check-in, Máy trạng thái Device Task, Dual-Bank A/B & tính lũy đẳng.<br>• Đặc tả REST API (Slide 12) + **Prototype FastAPI & Device Simulator** chạy thực tế (tua nhanh ×60). |
| **Thành viên C**<br>*(Campaign Engine)* | `diagrams/` · `DASAN_OJT1_Member_C_Deliverables.md` | • Luồng điều phối Canary Wave (`1%→10%→50%→100%`), chọn thiết bị trừ VIP, Máy trạng thái Campaign & Auto-Pause cơ học.<br>• Kiểm soát đồng thời 2 lớp (`Distributed Lock` + `Partial Unique Index`), Redis Semaphore, Observability (#11) & Maintenance Window (#14). |
| **Thành viên D**<br>*(Scale, Security & AI)* | `feature/d` · `docs/member-d/` · `docs/prompt-log.md` | • Bảng tính Quy mô & kịch bản ×10 kiểm chứng bằng `capacity_calc.py`; Ma trận RBAC, HMAC vs JWT, `audit_logs` 5 lớp & Emergency Rollback (#13).<br>• Thiết kế AI Log Classifier, `validate_output.py`, thực nghiệm LLM thật (`prompt-log.md`), Mock Demo & điều phối 16 Slide. |

#### 2. Bốn bài học kỹ thuật lớn nhất của cả nhóm
1. **Chốt hợp đồng dữ liệu trước khi vẽ rời:** Thống nhất sớm bộ quy ước **Q1–Q10** (enum trạng thái, mẫu số tỷ lệ lỗi, thời điểm trả slot tải) giúp 4 mảnh ghép khớp nhau không mâu thuẫn.
2. **Đừng cảm tính với các con số quy mô:** Viết script tính toán giúp nhóm phát hiện ngay thời gian chiến dịch bị quyết định bởi *Soak Time* và *thiết bị OFFLINE* chứ không phải băng thông tải.
3. **An toàn viễn thông cần phòng thủ nhiều lớp (Defense-in-Depth):** Kết hợp từ phần cứng (Dual-Bank) $\to$ CSDL (CHECK, Partial Unique Index) $\to$ Điều phối (Canary, Auto-Pause).
4. **Dùng AI có kiểm chứng, không tin mù quáng:** LLM rất giỏi gom nhóm ngữ nghĩa nhưng phải bị khóa trong Schema đóng, kiểm tra ngữ nghĩa bằng code và không bao giờ thay thế chốt an toàn tất định.

---

### SLIDE 16 — TỔNG KẾT, DEMO NHANH & HỎI ĐÁP (Q&A)

#### 1. Điểm nhấn Demo thực tế (Tùy chọn chiếu nhanh 30–45s hoặc mở sẵn khi Q&A)
* **Demo 1 — Luồng Thiết bị & Simulator (`prototype/` — Thành viên B):** 50 thiết bị ảo check-in ký HMAC-SHA256, nhận Pre-signed URL, mô phỏng đứt mạng retry và Watchdog tự `ROLLED_BACK` mà không vi phạm `uq_active_device_task`.
* **Demo 2 — Cổng RBAC, Four-Eyes, Audit Append-Only & AI Validator (`docs/member-d/`):**
  * Swagger UI (`python docs/member-d/mock_platform_demo.py`): QA tự duyệt firmware mình upload nhận ngay **`403 FOUR_EYES_VIOLATION`** và bị ghi vào `audit_logs` bất biến.
  * Kiểm định AI (`python docs/member-d/validate_output.py`): Chặn tức khắc JSON bịa mã lỗi `ERR_FLASH_WRITE_CORRUPTED` / `SN-9999`, chấp nhận 5/5 output thật của Prompt v2.

#### 2. Phân công trực chiến Hỏi đáp Hội đồng (3–5 phút Q&A)
* **Câu hỏi về ERD, Lịch sử firmware, Four-eyes DB, Quy tắc tương thích:** Thành viên **A** trả lời chính (D hỗ trợ phần DB Security).
* **Câu hỏi về Push vs Pull, Mất điện khi flash, Boot-loop, Idempotency, REST API:** Thành viên **B** trả lời chính.
* **Câu hỏi về Canary VIP, Auto-Pause, 2 Operator bấm Start cùng lúc, Slot tải, Khung giờ bảo trì:** Thành viên **C** trả lời chính.
* **Câu hỏi về 20 Gbps CDN, Mở rộng 1 triệu thiết bị, Lộ khóa HMAC, DBA sửa Audit, Vì sao cấm AI tự Abort, Rollback sau chiến dịch:** Thành viên **D** trả lời chính.

🎤 **Lời dẫn kết thúc (15s):** *"Trên đây là toàn bộ kiến trúc **Firmware Rollout Platform** của Nhóm 5 — đảm bảo an toàn từ phân vùng phần cứng của từng chiếc modem cho tới hạ tầng phân phối 20 Gbps của nhà mạng, kèm mã nguồn prototype và bộ kiểm định thực tế trên GitHub. Nhóm rất mong nhận được các câu hỏi phản biện từ đại diện DASAN Vietnam và hội đồng!"*
