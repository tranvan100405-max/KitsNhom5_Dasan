# PHÂN QUYỀN RBAC, XÁC THỰC THIẾT BỊ & AUDIT TRAIL
## Task 2 — Nội dung Slide 11 · Nền tảng triển khai cập nhật Firmware (DASAN Vietnam)

| | |
| :--- | :--- |
| **Người thực hiện** | Thành viên D — *System Reliability, Security, AI Lead & Project Coordinator* |
| **Task** | Task 2: Ma trận RBAC (4 role + Device) · 2 cơ chế xác thực · Thiết kế `audit_logs` · Danh mục hành động audit |
| **Nguồn đề bài** | `KITS2026_OJT2_Assignments.pdf` — Bước 3 (danh sách API), Cốt lõi #1 (four-eyes + ma trận quyền), Cốt lõi #7 (audit trail) |
| **Nguồn quy ước** | `DASAN_OJT1_Team_Role_Assignment.md` §1 (Q1–Q10, enum) + §2 Thành viên D; `DASAN_OJT1_System_Design_Specification.md` §1, §2, §3, §5 |
| **Đối chiếu schema** | `ERD/dasan_firmware_rollout.dbml` (bảng `members`, `audit_logs`, `firmware_versions`) |
| **Đối chiếu code B** | nhánh `feature/tv-b-device`: `docs/member-b/DEVICE_AGENT_DESIGN.md`, `prototype/device_agent/auth.py`, `router.py`, `service.py`, `config.py`, `db.py` |
| **Quy ước** | Tên bảng/cột/enum giữ đúng dbml + tài liệu nhóm. Chỗ lệch **chỉ liệt kê** ở §0.2, không tự sửa. Mọi API ngoài danh sách đề đều ghi rõ **ĐỀ XUẤT**. Không có secret thật — giá trị minh họa. |

> **Một câu chốt của slide 11:** *"Hai miền xác thực tách biệt (JWT cho người, HMAC theo từng request cho thiết bị); quyền theo nguyên tắc tối thiểu + four-eyes; mọi hành động nhạy cảm đều append-only vào `audit_logs` — kể cả hành vi bị từ chối."*

---

## 0. TỔNG QUAN, NGUỒN ĐỐI CHIẾU & CÁC ĐIỂM LỆCH

### 0.1. Danh sách endpoint chuẩn (đủ 100% danh sách API của đề)

Đề bài gộp 4 hành động vòng đời campaign vào một dòng; bảng dưới **tách thành 4 dòng** vì điều kiện trạng thái (409) và hành động audit khác nhau.

| # | Method & Path | Mô tả theo đề | Ghi chú |
| :-: | :--- | :--- | :--- |
| 1 | `POST /api/auth/login` | Đăng nhập, cấp token | Endpoint công khai duy nhất (chưa cần JWT) |
| 2 | `POST /api/firmware` | Tải metadata + file reference lên | Đề ghi rõ **DEVELOPER** |
| 3 | `PATCH /api/firmware/{id}/approve` | Phê duyệt firmware | Đề ghi rõ **QA, không phải người tải lên** |
| 4 | `PATCH /api/firmware/{id}/deprecate` | Thu hồi firmware lỗi | Đề ghi rõ **ADMIN** |
| 5 | `GET /api/firmware` | Danh sách firmware (phân trang/lọc) | |
| 6 | `GET /api/devices` | Danh sách thiết bị (phân trang/lọc) | |
| 7 | `GET /api/devices/{id}/history` | Lịch sử firmware của 1 thiết bị | |
| 8 | `POST /api/campaigns` | Tạo chiến dịch | Đề ghi rõ **OPERATOR**; endpoint `(*)` |
| 9 | `PATCH /api/campaigns/{id}/start` | Bắt đầu chiến dịch | |
| 10 | `PATCH /api/campaigns/{id}/pause` | Tạm dừng | |
| 11 | `PATCH /api/campaigns/{id}/resume` | Tiếp tục | |
| 12 | `PATCH /api/campaigns/{id}/abort` | Hủy khẩn cấp | |
| 13 | `GET /api/campaigns/{id}/progress` | Số lượng theo trạng thái, tỷ lệ thành công, đợt hiện tại | |
| 14 | `GET /api/campaigns/{id}/tasks` | Kết quả từng thiết bị (phân trang/lọc) | |
| 15 | `GET /api/audit-logs` | Ai đã làm gì, khi nào | Đề ghi rõ **ADMIN** |
| 16 | `POST /api/device-agent/check-in` | Thiết bị báo danh, nhận task | Endpoint `(*)` — **chỉ Device** |
| 17 | `POST /api/device-agent/tasks/{taskId}/result` | Thiết bị báo tiến độ/kết quả | Endpoint `(*)` — **chỉ Device** |

**API KHÔNG có trong đề (cần nêu rõ nếu nhóm muốn dùng):**

- Không có endpoint quản lý người dùng/role (`POST /api/members`, `PATCH /api/members/{id}/role`) → tài khoản do seed/DBA tạo; nếu cần UI quản trị thì **ĐỀ XUẤT** bổ sung.
- Không có `POST /api/auth/refresh`, `POST /api/auth/logout` → cơ chế refresh/revoke là **ĐỀ XUẤT** (Bước 3 không yêu cầu, nhưng slide 11 nên nói rõ).
- Không có endpoint thu hồi/rotate secret thiết bị → **ĐỀ XUẤT** `POST /api/devices/{id}/credentials/rotate` (chỉ ADMIN) để xử lý sự cố lộ secret (mục B.4).

### 0.2. Các điểm LỆCH giữa dbml / tài liệu nhóm / code của B (liệt kê — KHÔNG tự sửa)

| # | Chỗ lệch | dbml / tài liệu nhóm | Thực tế (code B hoặc ghi chú) | Ảnh hưởng | Đề xuất xử lý (chờ chốt) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| L1 | Bảng lưu secret thiết bị | **Không có** trong `ERD/dasan_firmware_rollout.dbml` | Code B dùng `device_credentials(deviceId, secret, createdAt)`; B đã ghi "còn mở #1, cần chốt với A" | Không có chỗ lưu secret ⇒ không thể xác thực HMAC | **ĐỀ XUẤT** A bổ sung `device_credentials` vào ERD (không gộp secret vào `devices` để API quản trị không đọc được) |
| L2 | `members.role` | dbml: `varchar`; tài liệu nhóm: enum `ADMIN \| DEVELOPER \| QA \| OPERATOR` | Code B: `CHECK (role IN ('ADMIN','DEVELOPER','QA','OPERATOR'))` | Không có ràng buộc ở DB nếu chỉ theo dbml ⇒ nguy cơ role lạ | Ghi enum vào dbml/DDL (không đổi tên cột) |
| L3 | `audit_logs.actorType` | dbml: `varchar`; tài liệu: `MEMBER \| SYSTEM \| DEVICE` | Chưa có CHECK; code B **chưa có bảng `audit_logs`** | Dữ liệu rác nếu không constraint | **ĐỀ XUẤT** `CHECK (actorType IN ('MEMBER','SYSTEM','DEVICE'))` |
| L4 | `audit_logs.actorId` | dbml: `uuid` + `Ref: members.id < audit_logs.actorId` (FK chỉ tới `members`) | Sự kiện `SYSTEM`/`DEVICE` không có `members.id` | Không thể dùng actorId cho thiết bị | Giữ `actorId NULL` + đặt `deviceId`/`serialNo` trong `detail`; nếu muốn FK cứng tới `devices` thì **ĐỀ XUẤT** thêm cột `deviceActorId` |
| L5 | `audit_logs.targetType` / `targetId` | dbml: `targetType varchar`, `targetId varchar` | Không enum, không FK | Query/aggregation dễ sai | **ĐỀ XUẤT** enum giá trị: `FIRMWARE \| CAMPAIGN \| CAMPAIGN_WAVE \| DEVICE_TASK \| DEVICE \| MEMBER \| ENDPOINT` |
| L6 | Four-eyes ở tầng DB | dbml **không có** CHECK `uploadedBy <> approvedBy` | Chỉ có thể chặn ở service | Nếu code sai thì mất kiểm soát 2 người | **ĐỀ XUẤT** `CHECK ("uploadedBy" <> "approvedBy")` trên `firmware_versions` (chỉ áp dụng khi `approvedBy` khác NULL) + trigger |
| L7 | Enum trạng thái trong dbml | `firmware_versions.status`, `campaigns.status`, `campaign_waves.status`, `device_tasks.status`, `devices.connectivity`, `devices.deviceType` đều `varchar` | Tài liệu nhóm + code B dùng CHECK/enum đúng | Lệch schema giữa tài liệu và DB | Ghi CHECK tương ứng trong DDL khi triển khai; **không đổi tên/giá trị** |
| L8 | Nội dung chữ ký HMAC | Quy ước nhóm: `HMAC-SHA256(serialNo + timestamp + nonce)` | B ký **6 thành phần**: `serialNo`, `timestamp`, `nonce`, `METHOD`, `PATH`, `SHA256(body)` (B đã nêu "cần chốt với D") | Chưa ghi vào spec ⇒ người khác đọc spec sẽ làm thiếu | **D chốt: GIỮ cách của B** (chống sửa body + chống dùng chéo endpoint) và **cần bổ sung vào Specification** |
| L9 | Nonce cache | Tài liệu chỉ nói "nonce dùng 1 lần" | B prototype: `NonceCache` **in-memory từng process**, TTL 600 s | Nhiều instance API ⇒ nonce dùng lại được ở instance khác | Production: Redis `SET NX EX <nonce> 600` dùng chung; ghi vào phần "hạn chế prototype" |
| L10 | Audit trong prototype của B | Yêu cầu Cốt lõi #7 | Prototype chỉ có 9 bảng (không có `audit_logs`), **không ghi audit**, chỉ có router device, chưa có JWT/login/admin API | Slide 11 là **thiết kế của D**, chưa có code tương ứng | Ghi rõ: "thiết kế + cần triển khai"; nếu kịp thì D bổ sung `audit_logs` vào mock API |
| L11 | Cột IP / requestId trong audit | dbml **không có** | Cần để điều tra sự cố | Thiếu ngữ cảnh khi có sự cố | MVP: lưu trong `detail`; **ĐỀ XUẤT** thêm 2 cột `ipAddress`, `requestId` (không đổi cột cũ) |
| L12 | mTLS vs HMAC | Spec: "mTLS **hoặc** HMAC-SHA256" | B chọn HMAC cho MVP (đúng quy ước nhóm), mTLS để production | Không phải lỗi — là quyết định | Ghi vào slide: HMAC = MVP, mTLS = nâng cấp |
| L13 | Secret trong prototype | — | SQLite lưu `secret` dạng rõ (`secrets.token_hex(16)`) | Chỉ chấp nhận cho demo | Production: KMS/HSM + envelope encryption; secret chỉ đọc bởi Device Ingestion Service |
| L14 | `nextCheckInSeconds` | Không có cột trong ERD | B trả trong response check-in | Không ảnh hưởng bảo mật | Giữ (là field response, không phải cột DB) |

### 0.3. Ký hiệu & ngữ nghĩa mã lỗi dùng xuyên suốt tài liệu

| Ký hiệu | Nghĩa |
| :--- | :--- |
| ✔ | Được phép, không điều kiện |
| ✔* | Được phép **có điều kiện** — điều kiện ghi ngay trong ô/cột ghi chú |
| ✘ | Bị từ chối |

**Mã lỗi chuẩn (thống nhất với B):**

| Mã | Khi nào dùng | Ví dụ |
| :--- | :--- | :--- |
| **401** | **Chưa xác thực**: thiếu/sai/hết hạn credential **của đúng cơ chế** | Thiếu JWT; chữ ký HMAC sai; timestamp lệch > 300 s; nonce đã dùng; gọi endpoint device bằng JWT web |
| **403** | **Đã xác thực nhưng không đủ quyền** hoặc vi phạm quy tắc nghiệp vụ về danh tính | Role không được phép; QA duyệt firmware mình upload (`FOUR_EYES_VIOLATION`); thiết bị báo task của máy khác (`TASK_NOT_OWNED`) |
| **404** | Không tồn tại tài nguyên **và** người dùng có quyền xem loại tài nguyên đó | `GET /api/firmware/{id}` không có |
| **409** | Đúng quyền nhưng **sai trạng thái** hoặc xung đột phiên bản | approve firmware đã duyệt; start campaign đang `RUNNING`; báo `stage` đi lùi; `STALE_ATTEMPT` |
| **400** | Dữ liệu đầu vào sai định dạng/không hợp lệ | `stage` lạ; body sai JSON; model không khớp |
| **429** (ĐỀ XUẤT) | Vượt rate limit (login, check-in theo serial) | Brute-force login; 1 serial gọi quá nhanh |

**Nguyên tắc không rò rỉ thông tin:** login sai email/mật khẩu trả **cùng một** 401; thiết bị có serial không tồn tại vẫn trả **401** (không trả 404) để không ai dò được serial nào có thật — đúng như B đang làm (`auth.py` so sánh với secret giả `"unknown-device"` trước khi trả lỗi).

---

## A. MA TRẬN RBAC (ENDPOINT × ROLE)

### A.1. Nguyên tắc thiết kế

1. **Least privilege (tối thiểu quyền):** mỗi role chỉ có đúng quyền phục vụ nhiệm vụ của mình; không role nào có toàn bộ vòng đời firmware (upload → approve → deprecate → rollout).
2. **Separation of duties (tách nhiệm vụ):** người **tải** firmware ≠ người **duyệt** (four-eyes, Cốt lõi #1); người **vận hành campaign** = OPERATOR, không phải người duyệt/người tải.
3. **Hai miền xác thực tách biệt:** web (JWT) và thiết bị (HMAC) không dùng chung; quyền của miền này **không** chuyển sang miền kia.
4. **Mặc định từ chối (deny by default):** route nào không khai báo `require_roles(...)` thì chặn; chỉ endpoint device mới miễn JWT nhưng bắt buộc HMAC.
5. **Kiểm tra 2 tầng:** **thẩm quyền (role)** ở middleware + **điều kiện nghiệp vụ** (ownership, four-eyes, state) ở service; sai tầng nào trả mã tầng đó (403 vs 409).
6. **Mọi lần từ chối đều ghi audit** (mục D): 403/401 là sự kiện bảo mật, không phải lỗi kỹ thuật im lặng.

### A.2. Ma trận chính

Cột ghi chú nêu **điều kiện** và **mã lỗi khi bị từ chối**; các mã `FOUR_EYES_VIOLATION`, `ROLE_NOT_ALLOWED`… là **ĐỀ XUẤT** (chưa có trong tài liệu nhóm, dùng thống nhất với B nếu trùng).

| # | Endpoint | ADMIN | DEVELOPER | QA | OPERATOR | Device | Điều kiện / mã lỗi khi từ chối |
| :-: | :--- | :-: | :-: | :-: | :-: | :-: | :--- |
| 1 | `POST /api/auth/login` | ✔ | ✔ | ✔ | ✔ | ✘ | Sai thông tin → **401** (một thông báo chung); quá nhiều lần → **429** (ĐỀ XUẤT); Device gọi → 401 (không có mật khẩu) |
| 2 | `POST /api/firmware` | ✘ | **✔** | ✘ | ✘ | ✘ | Chỉ DEVELOPER → **403 ROLE_NOT_ALLOWED**; sai checksum/model → **400** |
| 3 | `PATCH /api/firmware/{id}/approve` | ✔** | ✘ | **✔\*** | ✘ | ✘ | **\* uploadedBy ≠ approvedBy**; vi phạm → **403 FOUR_EYES_VIOLATION**; status ≠ `UPLOADED` → **409 INVALID_STATE**; không tồn tại → **404**; ** ADMIN: tuỳ chọn của nhóm (xem A.4) — nếu bật vẫn bị four-eyes** |
| 4 | `PATCH /api/firmware/{id}/deprecate` | **✔** | ✘ | ✘ | ✘ | ✘ | Chỉ ADMIN → **403**; đã `DEPRECATED` → **409** |
| 5 | `GET /api/firmware` | ✔ | ✔ | ✔ | ✔* | ✘ | OPERATOR chỉ thấy `APPROVED`/`DEPRECATED` (lọc dữ liệu, không phải chặn); thiếu/sai JWT → **401** |
| 6 | `GET /api/devices` | ✔ | ✔* | ✔* | ✔ | ✘ | DEV/QA **chỉ đọc** (read-only) → **403** nếu gọi endpoint khác; 401 nếu chưa đăng nhập |
| 7 | `GET /api/devices/{id}/history` | ✔ | ✘ | ✔* | ✔ | ✘ | DEV không có nhu cầu vận hành → **403 ROLE_NOT_ALLOWED** |
| 8 | `POST /api/campaigns` | ✘*** | ✘ | ✘ | **✔** | ✘ | Chỉ OPERATOR → **403**; firmware chưa `APPROVED`/bị `DEPRECATED` → **409 FIRMWARE_NOT_APPROVED**; không có thiết bị đủ điều kiện → **409 NO_ELIGIBLE_DEVICES**; *** ADMIN break-glass (xem A.4) |
| 9 | `PATCH /api/campaigns/{id}/start` | ✘*** | ✘ | ✘ | **✔\*** | ✘ | Campaign phải `DRAFT`/`SCHEDULED` → nếu không **409 INVALID_STATE**; thiếu quyền → **403** |
| 10 | `PATCH /api/campaigns/{id}/pause` | ✘*** | ✘ | ✘ | **✔\*** | ✘ | Campaign phải `RUNNING` → **409** |
| 11 | `PATCH /api/campaigns/{id}/resume` | ✘*** | ✘ | ✘ | **✔\*** | ✘ | Campaign phải `PAUSED` → **409** |
| 12 | `PATCH /api/campaigns/{id}/abort` | ✘*** | ✘ | ✘ | **✔\*** | ✘ | Campaign chưa `COMPLETED`/`ABORTED` → **409**; thao tác phá huỷ nên yêu cầu step-up auth (ĐỀ XUẤT) |
| 13 | `GET /api/campaigns/{id}/progress` | ✔ | ✘ | ✔* | ✔ | ✘ | DEV → **403**; QA chỉ đọc để đánh giá chất lượng |
| 14 | `GET /api/campaigns/{id}/tasks` | ✔ | ✘ | ✔* | ✔ | ✘ | Kết quả theo thiết bị: chỉ role vận hành/đảm bảo chất lượng; **che bớt serial** nếu cần (ĐỀ XUẤT) |
| 15 | `GET /api/audit-logs` | **✔** | ✘ | ✘ | ✘ | ✘ | Chỉ ADMIN → **403 ROLE_NOT_ALLOWED**; lọc theo thời gian/actor/target; **việc đọc audit cũng nên ghi audit** (ĐỀ XUẤT) |
| 16 | `POST /api/device-agent/check-in` | ✘ | ✘ | ✘ | ✘ | **✔** | Web gọi → **401** (không có HMAC; JWT không được chấp nhận ở miền device); HMAC sai/hết hạn → **401**; body `serialNo` ≠ serial đã ký → **403** |
| 17 | `POST /api/device-agent/tasks/{taskId}/result` | ✘ | ✘ | ✘ | ✘ | **✔\*** | Task không thuộc thiết bị đã ký → **403 TASK_NOT_OWNED**; task không tồn tại → **404**; `stage` sai/đi lùi → **409 INVALID_TRANSITION / STALE_ATTEMPT**; thiếu HMAC → **401** |

**Ghi chú cách đọc cột ADMIN:** "quản lý toàn bộ" (Cốt lõi #1) được hiểu là **quản trị hệ thống**: quản lý firmware (deprecate), audit, cấu hình, xử lý sự cố — **không** bao gồm vận hành campaign. Đây là cách hiểu **tách nhiệm vụ**; nếu nhóm chọn ADMIN = superuser thì các ô `✘***` đổi thành `✔*` **kèm bắt buộc ghi audit `ADMIN_OVERRIDE`**. Xem A.4.

### A.3. Vì sao cấp đúng các quyền này (least privilege)

| Role | Được cấp | Vì sao cần | Cố tình **KHÔNG** cấp | Vì sao |
| :--- | :--- | :--- | :--- | :--- |
| **DEVELOPER** | `POST /api/firmware`, `GET /api/firmware`, `GET /api/devices` (read-only) | Cần upload đúng model + checksum; cần đọc lại metadata để đối chiếu; cần xem phân bố model để biết firmware dùng được cho dòng nào | approve, deprecate, campaign, audit, device endpoints | Nếu DEV tự duyệt được thì four-eyes vô nghĩa; DEV không vận hành rollout |
| **QA** | `approve`, `GET /api/firmware`, `GET /api/devices` + `history` + `progress`/`tasks` (read-only) | Duyệt dựa trên file + release note; cần xem lịch sử thiết bị và tiến độ để xác nhận chất lượng sau rollout | upload, deprecate, điều khiển campaign, audit | QA không tạo firmware (tránh xung đột lợi ích); không bấm nút vận hành để giữ vai trò kiểm soát độc lập |
| **OPERATOR** | tạo/start/pause/resume/abort campaign; đọc firmware (chỉ APPROVED), devices, history, progress, tasks | Điều hành rollout theo đợt + xử lý sự cố vận hành | approve/deprecate/upload, audit | Operator mà duyệt được firmware thì có thể đẩy bản chưa kiểm duyệt; không được xoá dấu vết |
| **ADMIN** | deprecate firmware, audit-logs, đọc tất cả | Quản trị vòng đời firmware (thu hồi bản lỗi), điều tra sự cố, giám sát | upload (theo đề bài upload = DEVELOPER), four-eyes vẫn áp dụng nếu bật quyền approve | Giữ 4-eyes; admin không đứng tên cả 2 vai |
| **Device** | **đúng 2 endpoint** `/api/device-agent/*` | Đúng nhu cầu tối thiểu: nhận việc và báo kết quả | mọi endpoint web | Thiết bị không có tài khoản/phiên; nếu cấp quyền web thì 1 thiết bị bị lộ secret có thể đụng dữ liệu quản trị |

**Điểm mạnh để nói với giám khảo:** không tồn tại một role duy nhất nào đi hết được chuỗi *upload → approve → deprecate → tạo campaign → start*; chuỗi đó bắt buộc phải qua **ít nhất 3 người khác nhau** (DEVELOPER, QA, OPERATOR), và việc thu hồi phải do người thứ 4 (ADMIN) → đúng tinh thần four-eyes + separation of duties.

### A.4. Four-eyes: ADMIN có được tự duyệt firmware do mình upload không?

**Trả lời:** **KHÔNG** — và đề xuất chặn ở **3 lớp**.

**Vì sao không:**
1. Four-eyes có giá trị khi và chỉ khi **2 người độc lập**. Cho ADMIN (hoặc bất kỳ ai) ngoại lệ "tự upload rồi tự duyệt" biến kiểm soát 2 người thành kiểm soát 1 người — mất hoàn toàn ý nghĩa.
2. Admin đã có đường xử lý sự cố không cần tự duyệt: **deprecate** bản lỗi (đề bài giao đúng quyền này cho ADMIN) + tạo rollback campaign (Bonus #13) + audit.
3. Nếu ADMIN vừa upload vừa duyệt, audit trail sẽ ghi hai hành động cùng một `actorId` — giám khảo sẽ chỉ ra ngay đây là lỗ hổng kiểm soát.

**Đề xuất chốt:**

| Quyết định | Đề xuất |
| :--- | :--- |
| Ai được approve | **QA** (bắt buộc). ADMIN chỉ được approve nếu nhóm chủ động chọn "ADMIN override", và **luôn** bị ràng buộc `uploadedBy ≠ approvedBy` |
| Điều kiện | `actor.role ∈ {QA}` (hoặc ADMIN nếu override) **và** `actor.id ≠ firmware.uploadedBy` **và** `firmware.status = UPLOADED` |
| Vi phạm | **403 `FOUR_EYES_VIOLATION`**, không đổi trạng thái, ghi audit `FIRMWARE_APPROVAL_DENIED` |
| Admin override | Chỉ khi nhóm cho phép; mọi lần override ghi thêm `detail.override = true` + lý do; nên yêu cầu 2 người (admin + 1 QA) nếu thực sự khẩn cấp |
| "Từ chối" firmware | Đề bài chỉ có `approve`/`deprecate` → hành vi **từ chối** được biểu diễn là **lần approve bị chặn (403)** và ghi audit; nếu nhóm muốn QA **chủ động reject** thì **ĐỀ XUẤT** thêm body `{decision: "REJECT", reason}` cho endpoint approve (không thêm endpoint mới) |

**3 lớp thực thi:**

1. **UI:** ẩn nút Approve nếu `firmware.uploadedBy == currentUser.id` (chỉ là trải nghiệm, không phải bảo mật).
2. **Service (bắt buộc):** trong transaction: `SELECT ... FOR UPDATE` firmware → kiểm tra role + `uploadedBy != actorId` + `status = UPLOADED` → mới `UPDATE approval`. Hai người duyệt đồng thời: người sau nhận **409 `CONCURRENT_MODIFICATION`** (optimistic lock theo `status`).
3. **DB (ĐỀ XUẤT, chốt chặn cuối):** `CHECK ("uploadedBy" <> "approvedBy")` trên `firmware_versions` + trigger chặn update nếu vi phạm. Lý do cần lớp DB: nếu sau này có job/DBA cập nhật trực tiếp thì vẫn không thể tạo trạng thái "tự duyệt".

### A.5. Hai endpoint thiết bị — miền xác thực tách biệt

- Prefix riêng `/api/device-agent/*`; API Gateway áp policy riêng: **bắt buộc HMAC**, không nhận Bearer JWT; rate-limit theo `X-Device-Serial` + IP; body size giới hạn; không có route admin nào nằm dưới prefix này.
- **Người dùng web (kể cả ADMIN) gọi endpoint device → 401**, không phải 403: họ chưa xác thực bằng cơ chế mà endpoint yêu cầu (thiếu `X-Signature`/`X-Timestamp`/`X-Nonce`). Trả 401 đúng ngữ nghĩa HTTP; đồng thời không tiết lộ "endpoint này tồn tại cho ai".
- **Thiết bị gọi endpoint web → 401** vì không có JWT; nếu có token lạ thì cũng không có role trong JWT → 403. Thiết bị **không bao giờ** được cấp role web.
- Lý do tách: nếu dùng chung JWT cho 100.000 thiết bị thì lộ 1 signing key = toàn bộ fleet bị giả mạo; còn HMAC secret là per-device (mục B.4).

---

## B. HAI CƠ CHẾ XÁC THỰC: JWT (NGƯỜI DÙNG WEB) VS HMAC-SHA256 (THIẾT BỊ)

### B.1. Bảng so sánh

| Tiêu chí | **JWT (người dùng web)** | **HMAC-SHA256 theo request (thiết bị)** |
| :--- | :--- | :--- |
| Đối tượng | ADMIN, DEVELOPER, QA, OPERATOR | Device Agent (ONT/ONU/switch/router) |
| Danh tính | `sub = members.id`, claim `role` | `serialNo` tra trong `devices` → `device_credentials` |
| Cơ chế | Bearer token do server ký (HS256/RS256) | Chữ ký HMAC trên **canonical string** của từng request |
| Khoá bí mật | JWT signing key ở server (env/KMS); mật khẩu băm Argon2id | Secret **riêng từng thiết bị**, nạp lúc xuất xưởng; server giữ trong `device_credentials` (production: KMS/HSM) |
| Nơi lưu phía client | Cookie `HttpOnly; Secure; SameSite=Strict` (ĐỀ XUẤT) hoặc memory; **không** localStorage nếu tránh XSS | Flash/TPM của thiết bị, không xuất ra khỏi thiết bị |
| Thời hạn | Access **15 phút** + refresh **8 giờ** (giả định) | Mỗi request: timestamp phải nằm trong **±300 s** |
| Hết hạn | `exp` claim; refresh rotation | Timestamp ngoài cửa sổ → **401 TIMESTAMP_OUT_OF_WINDOW** |
| Thu hồi | `jti` deny-list Redis (TTL = `exp`), logout, refresh reuse detection | Rotate/disable secret của từng thiết bị (ĐỀ XUẤT endpoint) |
| Chống replay | Token là bearer → dựa vào HTTPS + TTL ngắn + revoke + step-up cho thao tác phá huỷ | **Nonce dùng 1 lần** (Redis `SET NX EX 600`) + timestamp ±300 s + chữ ký gắn **method/path/body hash** |
| Toàn vẹn body | Không (chỉ xác thực danh tính); dựa vào TLS | **Có**: `SHA256(body)` nằm trong chữ ký |
| Hết hạn/giả mạo do lệch giờ | Server tự quản | Thiết bị cần NTP; response trả `serverTime` để thiết bị tự chỉnh |
| Bán kính thiệt hại khi lộ | 1 phiên người dùng (tối đa 15 phút) | **Đúng 1 thiết bị** (không lan sang thiết bị khác, không vào được API web) |
| Xoay khoá | Rotate signing key (ảnh hưởng mọi phiên) | Rotate từng thiết bị, không ảnh hưởng fleet |
| Lỗi trả về | 401 `MISSING_TOKEN`/`TOKEN_EXPIRED`/`TOKEN_REVOKED`; 403 `ROLE_NOT_ALLOWED` | 401 `MISSING_AUTH_HEADERS`/`INVALID_SIGNATURE`/`TIMESTAMP_OUT_OF_WINDOW`/`NONCE_REUSED`/`INVALID_TIMESTAMP`/`INVALID_NONCE`; 403 `SERIAL_MISMATCH`/`TASK_NOT_OWNED` |

### B.2. JWT — thiết kế chi tiết

- **Luồng:** `POST /api/auth/login` (email + mật khẩu) → kiểm tra hash Argon2id (giả định; không dùng MD5/SHA1) → nếu đúng cấp `accessToken` (15 phút) + `refreshToken` (8 giờ, lưu hash trong DB, rotate mỗi lần dùng — ĐỀ XUẤT).
- **Claims tối thiểu:** `{ sub: members.id, role: "OPERATOR", jti: uuid, iat, exp, iss: "dasan-firmware" }`. **Không** đưa email/PII thừa vào token.
- **Kiểm tra mỗi request:** chữ ký → `exp` → `jti` không nằm deny-list → `role` có trong danh sách cho phép của route → **điều kiện nghiệp vụ** (ownership/four-eyes/state) ở service.
- **Không bao giờ tin dữ liệu client:** role lấy **từ token đã ký**, không lấy từ body/header; mọi field nhạy cảm (`uploadedBy`, `createdBy`, `actorId`) do **server** điền từ token, không nhận từ client (chống mass assignment).
- **Thu hồi:** login/logout/đổi quyền → thêm `jti` vào Redis deny-list với TTL = thời gian còn lại của token; refresh reuse → revoke toàn bộ họ token của user + audit.
- **Bảo vệ token:** cookie `HttpOnly` (chống XSS đọc token) + `Secure` + `SameSite=Strict` (+ CSRF double-submit nếu dùng cookie); CSP cho admin portal; không lưu token trong URL/log.
- **Brute-force:** rate-limit theo IP + email, khoá tạm sau N lần sai, audit mọi lần thất bại (mục D) — tránh dò mật khẩu.

### B.3. HMAC-SHA256 — thiết kế chi tiết (khớp code B)

**Canonical string (B đang ký — chốt giữ):**

```text
canonical = serialNo + "\n" + timestamp + "\n" + nonce + "\n" + METHOD + "\n" + path + "\n" + SHA256(body).hexdigest()
signature = HMAC-SHA256(secret, canonical).hexdigest()
```

**Header bắt buộc:** `X-Device-Serial`, `X-Timestamp` (Unix giây), `X-Nonce` (8–64 ký tự), `X-Signature` (hex). Thiếu 1 header → **401 `MISSING_AUTH_HEADERS`**.

**Thứ tự kiểm tra server (đúng như `auth.py` của B để tránh lỗi bảo mật):**

1. Có đủ 4 header? → không: 401.
2. `nonce` đúng định dạng/độ dài? → 401 `INVALID_NONCE`.
3. `timestamp` parse được và `|now − ts| ≤ 300 s`? → 401 `INVALID_TIMESTAMP` / `TIMESTAMP_OUT_OF_WINDOW`.
4. Tra `devices` + `device_credentials` theo `serialNo`; **tính chữ ký với secret giả nếu không tìm thấy** rồi `hmac.compare_digest` → 401 `INVALID_SIGNATURE` (không trả 404, không lộ serial có thật; thời gian xử lý tương đương để chống dò).
5. **Chỉ sau khi chữ ký hợp lệ** mới ghi nonce vào cache (`SET NX EX 600`) → nếu đã tồn tại: 401 `NONCE_REUSED`. (Ghi trước khi verify sẽ cho phép kẻ tấn công "đốt nonce" của người khác — cache poisoning.)
6. Gắn `DeviceIdentity(deviceId, serialNo, model)` cho request; service kiểm tra tiếp: `body.serialNo == identity.serialNo` → khác: **403**; task thuộc đúng `deviceId` → sai: **403 `TASK_NOT_OWNED`**.

**Chống replay — 2 lớp độc lập:**

- **Timestamp ±300 s** (B: `HMAC_MAX_CLOCK_SKEW_SECONDS = 300`): request bắt được sau 5 phút vô dụng.
- **Nonce 1 lần** (B: `NONCE_TTL_SECONDS = 600` = 2× cửa sổ): trong 5 phút, mỗi `(serial, nonce)` chỉ dùng được 1 lần → replay tức thời cũng bị chặn.
- Chữ ký gắn **method + path + SHA256(body)** → không thể lấy chữ ký của `/check-in` dùng cho `/result`, không thể sửa body (vd đổi `stage` thành `SUCCESS`).
- **Production:** thay `NonceCache` in-memory bằng Redis `SET NX EX` để mọi instance thấy chung (hiện prototype chỉ 1 process — L9).

**Ví dụ minh hoạ (secret giả, không phải secret thật):**

```text
serialNo = "DSN-H660-0001"
timestamp = "1795000000"
nonce = "8f14e45fceea167a5a36dedd4bea2543"
METHOD = "POST"
path = "/api/device-agent/check-in"
body = {"serialNo":"DSN-H660-0001","model":"DASAN-H660GM","currentVersion":"2.3.0","activePartition":"A"}
=> canonical (6 dòng), signature = HMAC-SHA256(secret_demo, canonical)
```

### B.4. Nếu lộ secret của MỘT thiết bị thì sao?

| Khía cạnh | Phân tích |
| :--- | :--- |
| Kẻ tấn công làm được gì | Giả danh **đúng 1 thiết bị đó**: gọi check-in (nhận pre-signed URL của chính task của máy đó), báo `stage`/`SUCCESS` giả cho task của máy đó (có thể che giấu một lần cập nhật lỗi) |
| **Không** làm được gì | Không đụng thiết bị khác (secret khác); không vào API web (không có JWT/role); không đọc audit; không tạo/duyệt firmware/campaign; không đổi secret của máy khác |
| Vì sao giới hạn | Secret per-device + chữ ký per-request + kiểm tra `body.serialNo` + `TASK_NOT_OWNED` + không có quyền web |
| Phát hiện | (1) cùng serial check-in từ 2 IP/2 vùng trong thời gian ngắn; (2) `SUCCESS` không có tiền sử `DOWNLOADED`/`DOWNLOADING` trong audit; (3) thời gian "tải + cài" ngắn bất thường; (4) tăng đột biến `DEVICE_AUTH_FAILED` cho serial khác từ cùng IP (dò) |
| Xử lý | Rotate secret ngay (ĐỀ XUẤT endpoint `POST /api/devices/{id}/credentials/rotate`, ADMIN), đánh dấu thiết bị nghi nhiễm/quarantine, ghi audit `DEVICE_CREDENTIAL_ROTATED`, thông báo vận hành; nếu là phần cứng bị mở → thay thiết bị |
| Tồn dư | Trong khoảng thời gian trước khi phát hiện, kẻ tấn công có thể báo kết quả sai cho task của máy đó → giảm thiểu bằng đối soát `currentVersion` thật ở check-in kế tiếp (thiết kế sẵn của B) + audit chain |

**Kết luận:** lộ secret 1 thiết bị là sự cố **cục bộ**, không phải sự cố toàn hệ thống — đây là lý do cốt lõi chọn HMAC per-device thay vì JWT dùng chung.

### B.5. Vì sao KHÔNG dùng JWT cho thiết bị

1. **Không có vòng đời người dùng:** thiết bị không có mật khẩu, không có phiên đăng nhập, không thể làm luồng refresh/rotation như con người.
2. **Token bearer bị dùng lại:** kẻ tấn công lấy được token thì dùng được tới khi hết hạn, không gắn với nội dung request → có thể gửi `SUCCESS` giả cho bất kỳ task nào của thiết bị đó mà không bị phát hiện bởi chữ ký.
3. **Thu hồi đắt:** 100.000 thiết bị × token hết hạn 15 phút = deny-list khổng lồ; rotate signing key thì ảnh hưởng toàn fleet.
4. **Bán kính thiệt hại:** lộ **một** signing key JWT = giả mạo được **mọi** thiết bị; lộ secret HMAC = đúng 1 thiết bị.
5. **Thiết bị boot bằng firmware cũ/đồng hồ chưa sync:** JWT cần thời gian đúng để kiểm `exp`; HMAC cũng cần timestamp nhưng server trả `serverTime` để thiết bị tự chỉnh (B đã làm), và sai số cho phép rõ ràng ±300 s.
6. **JWT không bảo vệ toàn vẹn request:** không có `SHA256(body)` trong token → phải tin hoàn toàn vào TLS; HMAC ký cả body.

**Còn mTLS?** Spec cho phép mTLS **hoặc** HMAC. mTLS mạnh hơn nhưng cần hạ tầng cấp phát/thu hồi chứng chỉ cho 100k thiết bị, chi phí TLS termination, và khó triển khai trong 8 giờ OJT → **MVP dùng HMAC, ghi rõ mTLS là hướng production**.

### B.6. Đối chiếu với cách B đã làm

| Hạng mục | Code/thiết kế B | Đánh giá của D | Việc cần chốt |
| :--- | :--- | :--- | :--- |
| Canonical string | 6 thành phần (serial, ts, nonce, method, path, sha256(body)), phân cách `\n`, method upper | **Khớp và mạnh hơn quy ước nhóm** (quy ước chỉ 3 thành phần) | Chốt giữ (L8) + bổ sung vào Specification §1/§3 |
| Header | `X-Device-Serial`, `X-Timestamp`, `X-Nonce`, `X-Signature` | Khớp | — |
| Cửa sổ thời gian | `HMAC_MAX_CLOCK_SKEW_SECONDS = 300` (5 phút) | Khớp Spec và B design | — |
| Nonce | `NonceCache` in-memory theo process, TTL 600 s, chỉ ghi **sau** khi verify | Đúng logic, **chưa dùng chung nhiều instance** | Production: Redis `SET NX EX` (L9) |
| So sánh chữ ký | `hmac.compare_digest` | Đúng (constant-time) | — |
| Serial không tồn tại | Tính với secret giả `"unknown-device"` rồi 401 | Đúng (chống enumeration) | — |
| Body serial ≠ signed serial | `service.py` trả **403** | Khớp ma trận dòng 16 | — |
| Task không thuộc thiết bị | 403 `TASK_NOT_OWNED` | Khớp ma trận dòng 17 | — |
| Trạng thái sai / attempt cũ | 409 `INVALID_TRANSITION` / `STALE_ATTEMPT` | Khớp | — |
| Lưu secret | `device_credentials(deviceId, secret)` plaintext SQLite | Cần KMS/HSM khi production; **bảng chưa có trong ERD** | Chốt với A (L1) |
| Audit | **Chưa có** | Thiếu so với Cốt lõi #7 | Cần bổ sung `audit_logs` (mục C/D) |
| JWT cho web | **Chưa có** (prototype chỉ device router) | RBAC/JWT là thiết kế của D, cần code | Ghi rõ trong slide: "thiết kế + mock API" |

**Trả lời câu hỏi mở #3 của B (trong `DEVICE_AGENT_DESIGN.md` §7.2):** D **xác nhận giữ** việc ký thêm `METHOD`, `PATH`, `SHA256(body)`. Lý do: (a) chống dùng chéo chữ ký giữa `/check-in` và `/result`; (b) chống sửa body trên đường truyền; (c) chi phí chỉ là hash 1 body nhỏ (< 1 KB). Cần ghi vào Specification để cả nhóm thống nhất.

---

## C. THIẾT KẾ `audit_logs`

### C.1. Cấu trúc cột (khớp 100% dbml hiện tại)

| Cột (dbml) | Kiểu dbml | Nullable | Ý nghĩa | Ghi chú triển khai (ĐỀ XUẤT, không đổi tên) |
| :--- | :--- | :-: | :--- | :--- |
| `id` | `uuid [pk]` | ✘ | Khoá chính | `gen_random_uuid()` |
| `actorId` | `uuid` (FK → `members.id`) | ✔ | Người thực hiện nếu là MEMBER | `NULL` khi `actorType` = `SYSTEM`/`DEVICE` |
| `actorType` | `varchar` | ✘ | `MEMBER \| SYSTEM \| DEVICE` | Thêm `CHECK (...)` |
| `action` | `varchar` | ✘ | Mã hành động (mục D) | `CHECK` theo danh mục hoặc enum mềm |
| `targetType` | `varchar` | ✘ | Loại đối tượng bị tác động | ĐỀ XUẤT enum: `FIRMWARE \| CAMPAIGN \| CAMPAIGN_WAVE \| DEVICE_TASK \| DEVICE \| MEMBER \| ENDPOINT` |
| `targetId` | `varchar` | ✔ | ID đối tượng (uuid dạng chuỗi hoặc khoá ghép) | Không FK (vì đa hình); index theo `(targetType, targetId)` |
| `detail` | `json` | ✔ | Ngữ cảnh chi tiết (before/after, lý do, IP…) | Production nên dùng `jsonb` |
| `createdAt` | `datetime` | ✘ | Thời điểm | `DEFAULT now()`; **nguồn thời gian của server**, không nhận từ client |

**Lưu ý L4:** `actorId` FK chỉ tới `members` nên **không thể** trỏ tới `devices`. Với sự kiện DEVICE: `actorId = NULL`, `actorType = 'DEVICE'`, còn danh tính thiết bị đặt ở `detail.deviceId`, `detail.serialNo`; `targetType = 'DEVICE_TASK'`, `targetId = device_tasks.id`.

### C.2. Append-only được ĐẢM BẢO bằng cách nào (5 lớp)

| Lớp | Cơ chế | Chặn được gì | Ghi chú |
| :-: | :--- | :--- | :--- |
| 1 | **Không có API sửa/xoá**: chỉ có `GET /api/audit-logs` (ADMIN) | Ứng dụng không thể sửa qua HTTP | Đề bài không có endpoint update/delete audit → giữ đúng danh sách |
| 2 | **Phân quyền DB**: role ứng dụng chỉ có `INSERT`, `SELECT` trên `audit_logs`; role đọc audit riêng | UPDATE/DELETE/TRUNCATE bị DB từ chối | `REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM app_rw;` |
| 3 | **Trigger bất biến** (ĐỀ XUẤT) | UPDATE/DELETE kể cả khi có role mạnh | `BEFORE UPDATE OR DELETE ... RAISE EXCEPTION 'audit_logs is append-only'` |
| 4 | **Hash chain** (tuỳ chọn nâng cao) | Sửa/xoá **lén** một dòng (kể cả DBA) | `recordHash = SHA256(prevHash + canonical_json(dòng))`; lưu `prevHash`/`recordHash` trong `detail.chain` (MVP, không thêm cột) hoặc 2 cột mới (ĐỀ XUẤT) |
| 5 | **WORM + sao lưu ngoài**: export hằng ngày sang object storage có Object Lock / SIEM, mỗi ngày neo 1 hash gốc | Xoá cả bảng/partition ở DB gốc | Chỉ DBA có dual-control mới drop partition; bản WORM vẫn còn |

**DDL tham khảo (Postgres, giữ nguyên tên cột dbml):**

```sql
-- Lớp 2+3: chỉ INSERT/SELECT + chặn sửa
GRANT INSERT, SELECT ON audit_logs TO app_rw;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM app_rw;

CREATE OR REPLACE FUNCTION audit_logs_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs is append-only (attempt=% op=%)', TG_OP, TG_TABLE_NAME;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_immutable
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();
```

**Hash chain (tuỳ chọn — nêu để trả lời câu hỏi "DBA sửa thì sao"):**

```text
payload_n  = canonical_json({actorId, actorType, action, targetType, targetId, detail, createdAt})
prevHash_n = recordHash_{n-1}   (dòng đầu tiên: 64 ký tự '0')
recordHash_n = SHA256(prevHash_n + "|" + payload_n)
→ mỗi ngày chốt "anchorHash" gửi object storage Object Lock (không xoá được)
→ job kiểm tra chuỗi hằng đêm; đứt chuỗi = báo động
```

**Vì sao phải nói rõ giới hạn:** không có hệ thống nào chống được **root DBA** sửa cả DB lẫn bản sao nếu không có WORM bên ngoài. Slide nên nói thẳng: *append-only thực thi ở DB cho ứng dụng; chống gian lận cấp hạ tầng cần hash chain + WORM + tách quyền DBA* — đó là câu trả lời trưởng thành.

### C.3. `actorId` nullable + `actorType` — bảng quy tắc

| `actorType` | `actorId` | Ai | Ví dụ | Ghi chú |
| :--- | :--- | :--- | :--- | :--- |
| `MEMBER` | **NOT NULL** (FK `members.id`) | ADMIN/DEVELOPER/QA/OPERATOR | QA duyệt firmware | Nếu không xác định được user (vd login sai email) → `actorId = NULL`, `actorType = 'MEMBER'`, `detail.emailAttempted` (đã mask) |
| `SYSTEM` | `NULL` | Worker/Scheduler/Auto-pause | Auto-pause do `failureRate` vượt ngưỡng | `detail.workerId`, `detail.jobId`, `detail.reason` |
| `DEVICE` | `NULL` (FK không trỏ được `devices`) | Thiết bị đã xác thực HMAC | Thiết bị báo `ROLLED_BACK` | `detail.deviceId`, `detail.serialNo`; **không bao giờ** ghi secret/chữ ký |

### C.4. `detail` lưu gì?

**Cấu trúc đề xuất (JSON object, có `schemaVersion` để tiến hoá):**

```json
{
  "schemaVersion": 1,
  "requestId": "req-7f3a...",
  "ipAddress": "203.113.x.x",
  "userAgent": "Mozilla/5.0 ...",
  "reason": "FOUR_EYES_VIOLATION",
  "before": { "status": "UPLOADED" },
  "after":  { "status": "APPROVED" },
  "meta": { "uploadedBy": "uuid-...", "approvedBy": "uuid-...", "checksum": "e3b0c442..." }
}
```

- `before`/`after`: **chỉ các trường thay đổi** (diff) — không dump cả bản ghi.
- `meta`: dữ liệu nghiệp vụ cần truy vết (số serial, attempt, errorCode, failureRate…).
- **TUYỆT ĐỐI KHÔNG ghi:** mật khẩu/hash mật khẩu, JWT, refresh token, `device_credentials.secret`, chữ ký HMAC đầy đủ, nội dung file firmware, PII không cần thiết (email đầy đủ — nên mask `a***@domain`), header `Authorization`.
- Thời gian: chỉ dùng `createdAt` server; nếu cần thời gian client thì ghi vào `detail.clientTimestamp` (không dùng để truy vấn).

### C.5. Index & partition (liên hệ ước tính 2,5 triệu dòng/năm)

Từ `docs/member-d/CAPACITY_ESTIMATION.md` (mục E): **5 dòng audit/task × 500.000 task/năm ≈ 2.500.000 dòng/năm** (~208k dòng/tháng; ~1,4 GB/năm). Vì vậy:

**Index tối thiểu:**

```sql
CREATE INDEX idx_audit_created_at     ON audit_logs ("createdAt" DESC);
CREATE INDEX idx_audit_actor          ON audit_logs ("actorId", "createdAt" DESC);
CREATE INDEX idx_audit_target         ON audit_logs ("targetType", "targetId", "createdAt" DESC);
CREATE INDEX idx_audit_action         ON audit_logs (action, "createdAt" DESC);
CREATE INDEX idx_audit_security_events ON audit_logs ("createdAt" DESC)
  WHERE action IN ('ACCESS_DENIED','DEVICE_AUTH_FAILED','MEMBER_LOGIN_FAILED');
```

**Partition theo thời gian (RANGE theo tháng):**

```sql
CREATE TABLE audit_logs (LIKE audit_logs_template) PARTITION BY RANGE ("createdAt");
CREATE TABLE audit_logs_2026_11 PARTITION OF audit_logs
  FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
-- ... mỗi tháng 1 partition; pg_partman tự tạo
```

- Lý do partition theo `createdAt` (không theo `campaignId`): truy vấn audit luôn lọc theo thời gian; drop partition cũ nhanh; index nhỏ hơn.
- **Retention (giả định):** hot 3 tháng trên DB, warm 12 tháng, cold 5 năm ở object storage (WORM); nếu chốt khác thì chỉ đổi con số, không đổi thiết kế.
- Link với capacity: audit chỉ ~208k dòng/tháng nên **không phải điểm nghẽn**; nếu audit cả heartbeat thì thành **10,5 tỷ dòng/năm** (mục E của tài liệu capacity) → phải chặn ngay ở thiết kế (mục D.2).

### C.6. Đường ghi audit: đồng bộ hay bất đồng bộ?

| Loại sự kiện | Cách ghi | Lý do |
| :--- | :--- | :--- |
| Phê duyệt/thu hồi firmware, tạo/điều khiển campaign, auto-pause, role/credential changes | **Đồng bộ, cùng transaction** với thay đổi nghiệp vụ | Mất audit = mất bằng chứng; khối lượng nhỏ (vài nghìn/năm) |
| Login thất bại, 403, device auth failed | **Đồng bộ ở exception handler** (commit riêng, không rollback theo request) | Request thất bại vẫn phải ghi; nếu rollback theo TX nghiệp vụ thì mất dấu vết |
| Chuyển trạng thái `device_tasks` (DOWNLOADING/INSTALLING/VERIFYING/terminal) | **Bất đồng bộ qua bảng outbox** + worker ghi batch vào `audit_logs` | Khối lượng lớn hơn (tối đa 50 task/s lúc tải), không được làm chậm API device; outbox bảo đảm không mất |
| Heartbeat / báo trùng `stage` | **Không ghi** | Không phải thay đổi trạng thái (mục D.2) |

**Idempotency:** outbox có `eventId` unique (vd `sha256(taskId|attempt|stage)`), worker insert `ON CONFLICT DO NOTHING`; `audit_logs` MVP chưa có cột `eventId` → lưu `detail.eventId` (hoặc thêm cột — ĐỀ XUẤT) để tránh trùng khi retry.

---

## D. DANH MỤC HÀNH ĐỘNG PHẢI GHI AUDIT

### D.1. Các action bắt buộc (đủ yêu cầu Cốt lõi #7)

Quy ước tên **ĐỀ XUẤT**: `ENTITY_VERB` (in hoa, `snake_case` cho phần verb) — chưa có trong tài liệu nhóm nên phải chốt chung.

| # | `action` | `actorType` | `targetType` | Khi nào | `detail` mẫu (rút gọn) | Ghi |
| :-: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `FIRMWARE_UPLOADED` | MEMBER (DEVELOPER) | FIRMWARE | Upload metadata + file reference | `{versionNo, versionCode, model, checksum, sizeBytes, fileUrl}` | Sync |
| 2 | `FIRMWARE_APPROVED` | MEMBER (QA) | FIRMWARE | Duyệt thành công | `{before:{status:UPLOADED}, after:{status:APPROVED}, uploadedBy, approvedBy, checksum}` | Sync |
| 3 | `FIRMWARE_APPROVAL_DENIED` | MEMBER | FIRMWARE | **Từ chối duyệt**: vi phạm four-eyes hoặc sai trạng thái | `{reason: FOUR_EYES_VIOLATION, uploadedBy, actorId}` | Sync (handler 403/409) |
| 4 | `FIRMWARE_DEPRECATED` | MEMBER (ADMIN) | FIRMWARE | Thu hồi firmware lỗi | `{before:{status:APPROVED}, after:{status:DEPRECATED}, reason}` | Sync |
| 5 | `CAMPAIGN_CREATED` | MEMBER (OPERATOR) | CAMPAIGN | Tạo campaign | `{firmwareId, targetGroupId, failureThresholdPercent, maxConcurrentDevices, plannedWaves}` | Sync |
| 6 | `CAMPAIGN_STARTED` | MEMBER (OPERATOR) | CAMPAIGN | `DRAFT/SCHEDULED → RUNNING` | `{before:{status:DRAFT}, after:{status:RUNNING}, waveId, eligibleDeviceCount}` | Sync |
| 7 | `CAMPAIGN_PAUSED` | MEMBER (OPERATOR) | CAMPAIGN | Tạm dừng thủ công | `{before, after, reason}` | Sync |
| 8 | `CAMPAIGN_RESUMED` | MEMBER (OPERATOR) | CAMPAIGN | Tiếp tục | `{before:{status:PAUSED}, after:{status:RUNNING}}` | Sync |
| 9 | `CAMPAIGN_ABORTED` | MEMBER (OPERATOR) | CAMPAIGN | Huỷ khẩn cấp | `{before, after, reason, tasksPending}` | Sync |
| 10 | **`CAMPAIGN_AUTO_PAUSED`** | **SYSTEM** | CAMPAIGN | Worker phát hiện `FailureRate > failureThresholdPercent` | `{waveId, failureRate, threshold, sampleSize, failedCount, timeoutCount, rolledBackCount, errorCodeTop}` | Sync (worker) |
| 11 | `CAMPAIGN_WAVE_STATE_CHANGED` | SYSTEM | CAMPAIGN_WAVE | `PENDING → RUNNING → COMPLETED` | `{before, after, rolloutPercentage, successRate}` | Sync |
| 12 | `DEVICE_TASK_CREATED` | SYSTEM | DEVICE_TASK | Engine tạo task cho thiết bị trong wave | `{campaignId, waveId, deviceId, fromFirmwareId, toFirmwareId}` | Async (batch) |
| 13 | `DEVICE_TASK_STATE_CHANGED` | SYSTEM | DEVICE_TASK | Server đổi trạng thái: cấp slot `PENDING→DOWNLOADING`, `→TIMEOUT`, retry `FAILED/TIMEOUT→PENDING` | `{before, after, attemptCount, errorCode}` | Async |
| 14 | `DEVICE_TASK_STAGE_REPORTED` | **DEVICE** | DEVICE_TASK | Thiết bị báo `stage` **làm đổi trạng thái** (DOWNLOADED/SUCCESS/FAILED/ROLLED_BACK…) | `{stage, before, after, attempt, reportedVersion, errorCode, deviceId, serialNo}` | Async |
| 15 | `DEVICE_AUTH_FAILED` | DEVICE | DEVICE | HMAC sai/hết hạn/nonce trùng/serial không tồn tại | `{serialNoClaimed, reason: INVALID_SIGNATURE, ipAddress}` — **không ghi chữ ký** | Sync (401 handler) |
| 16 | `DEVICE_CREDENTIAL_ROTATED` | MEMBER (ADMIN) | DEVICE | Rotate secret sau sự cố (ĐỀ XUẤT endpoint) | `{deviceId, serialNo, reason}` — **không ghi secret** | Sync |
| 17 | `MEMBER_LOGIN_SUCCEEDED` | MEMBER | MEMBER | Đăng nhập thành công | `{ipAddress, userAgent, jti}` | Sync |
| 18 | **`MEMBER_LOGIN_FAILED`** | MEMBER | MEMBER | Sai mật khẩu/email, tài khoản khoá | `{emailMasked, reason, ipAddress, attemptNo}` | Sync |
| 19 | `MEMBER_TOKEN_REVOKED` | MEMBER | MEMBER | Logout / refresh reuse / admin revoke | `{jti, reason}` | Sync |
| 20 | **`ACCESS_DENIED`** | MEMBER | ENDPOINT | Mọi **403** (sai role, four-eyes, task không thuộc thiết bị) | `{method, path, requiredRoles, actualRole, reason}` | Sync (403 handler) |
| 21 | `AUDIT_LOGS_READ` (ĐỀ XUẤT) | MEMBER (ADMIN) | ENDPOINT | Ai đọc audit, lọc khoảng nào | `{from, to, filters, resultCount}` | Sync |
| 22 | `ROLLBACK_CAMPAIGN_CREATED` (Bonus #13) | MEMBER (OPERATOR) | CAMPAIGN | Tạo campaign rollback từ `device_firmware_histories` | `{sourceCampaignId, targetFirmwareId, deviceCount}` | Sync |

**Vì sao ghi cả hành vi bị từ chối:** 403/401 là dấu hiệu tấn công/lạm quyền sớm nhất. Nếu chỉ ghi hành động thành công thì kẻ tấn công dò quyền sẽ không để lại dấu vết. Cốt lõi #7 yêu cầu "mọi phê duyệt, thao tác chiến dịch và thay đổi trạng thái" — hành vi bị từ chối là **thay đổi trạng thái bảo mật**, phải ghi.

### D.2. Cái gì KHÔNG ghi vào `audit_logs` (và vì sao)

| Không ghi | Vì sao |
| :--- | :--- |
| **Heartbeat / check-in thành công / `NO_TASK`** | 100.000 thiết bị × 288 lần/ngày = **10,5 tỷ dòng/năm** → phá DB và vô nghĩa (không phải thay đổi trạng thái); `devices.lastCheckInAt` đã lưu trạng thái mới nhất |
| Báo trùng `stage` (idempotent duplicate, vd `INSTALLING` lần 2) | Không đổi trạng thái; ghi lại chỉ tạo nhiễu. Chỉ ghi **lần chuyển trạng thái thực** (D.1 #14) |
| Mỗi lần cấp pre-signed URL | Đã suy ra từ chuyển `DOWNLOADING`; URL hết hạn 15 phút, ghi lại không tăng giá trị điều tra |
| `GET` thông thường (firmware/devices/campaigns) — trừ `AUDIT_LOGS_READ` | Đọc không thay đổi trạng thái; khối lượng lớn; nếu cần điều tra thì bật **sampling** hoặc log access ở tầng gateway (không phải `audit_logs`) |
| Xác thực JWT thành công mỗi request | Hàng triệu dòng/năm; login đã ghi (#17) |
| Log ứng dụng/metrics/debug | Thuộc hệ thống observability, không phải audit nghiệp vụ (tránh trộn hai loại) |
| Secret, token, chữ ký HMAC, mật khẩu, toàn bộ body firmware | **Không bao giờ** — biến audit thành nơi rò rỉ bí mật |

**Chống "audit flood":** nếu kẻ tấn công spam login/check-in sai → có thể tạo hàng triệu dòng 401. Giải pháp: rate-limit theo IP/serial; `DEVICE_AUTH_FAILED` chỉ ghi **tối đa N dòng/serial/phút**, các lần vượt ghi gộp `{suppressedCount: k}`; alert khi vượt ngưỡng. Ghi rõ đây là đánh đổi (mất chi tiết từng lần) — **giả định** N = 5/phút/serial.

### D.3. Kiểm tra khối lượng (khớp tài liệu capacity)

| Thành phần | Ước tính | Ghi chú |
| :--- | :--- | :--- |
| Device task transitions | ~5 dòng/task × 500.000 task/năm = **2.500.000 dòng/năm** | Khớp mục E của `CAPACITY_ESTIMATION.md` |
| Hành động member (firmware/campaign/auth) | ~10 campaign × ~20 sự kiện + login + 403 ≈ **vài nghìn/năm** | Không đáng kể |
| **Tổng** | **~2,5 triệu dòng/năm ≈ 208k dòng/tháng** | Partition tháng là đủ; **không** phải điểm nghẽn |
| Nếu audit heartbeat | **10,5 tỷ/năm** | Bị chặn bởi thiết kế D.2 |

---

## E. KỊCH BẢN TẤN CÔNG / LẠM QUYỀN & CÁCH CHẶN

| # | Kịch bản | Kẻ tấn công làm gì | Lớp chặn | Phát hiện / audit | Tồn dư & giảm thiểu |
| :-: | :--- | :--- | :--- | :--- | :--- |
| 1 | **Tự duyệt firmware (self-approval)** | DEVELOPER upload bản lỗi rồi tự gọi `approve` (hoặc ADMIN upload rồi tự duyệt) | Service: `uploadedBy != actorId` → **403 FOUR_EYES_VIOLATION**; DB CHECK (ĐỀ XUẤT); UI ẩn nút | `FIRMWARE_APPROVAL_DENIED` + `ACCESS_DENIED`; alert nếu lặp lại | 2 người **thông đồng** vẫn duyệt được bản lỗi → giảm thiểu bằng audit + hậu kiểm + deprecate nhanh; không thể chặn tuyệt đối trong mô hình 4-eyes |
| 2 | **Replay request check-in/result** | Bắt 1 request hợp lệ (trong 5 phút) rồi gửi lại, hoặc đổi `stage` thành `SUCCESS` | Timestamp ±300 s; **nonce 1 lần** (Redis `SET NX EX`); chữ ký gắn `METHOD/PATH/SHA256(body)` → sửa body là sai chữ ký | **401 `NONCE_REUSED` / `TIMESTAMP_OUT_OF_WINDOW` / `INVALID_SIGNATURE`** + `DEVICE_AUTH_FAILED` | Kẻ tấn công gửi **trước** thiết bị thật (chiếm nonce) → thiết bị nhận 401, request giả vẫn đúng chữ ký nhưng body không đổi được; thiệt hại = 1 lần gọi trùng vô hại (idempotent) |
| 3 | **Giả mạo serial thiết bị** | Biết serial của thiết bị khác (in trên vỏ), gửi check-in với serial đó | Không có secret → **401 INVALID_SIGNATURE**; `body.serialNo` ≠ serial đã ký → **403**; task không thuộc thiết bị → **403 TASK_NOT_OWNED**; unknown serial trả 401 (không lộ) | `DEVICE_AUTH_FAILED` + `ACCESS_DENIED`; alert khi 1 IP thử nhiều serial | Nếu **lộ secret** → xem B.4 (rotate + quarantine); nếu serial đoán được hàng loạt → rate-limit + WAF + alert |
| 4 | **Operator xoá dấu vết** | Operator gọi API xoá/sửa `audit_logs` hoặc tự sửa DB để che hành vi sai | Không có endpoint update/delete; DB role chỉ INSERT/SELECT; trigger bất biến; hash chain; WORM export | Mọi lần thử UPDATE/DELETE bị DB chặn (log DB) + hash chain đứt = alert; audit `AUDIT_LOGS_READ` khi đọc | Root DBA vẫn có thể tắt trigger → cần dual-control DBA + WORM + SIEM; **nói rõ giới hạn này trên slide** |
| 5 | **Token web bị đánh cắp (JWT theft)** | Lấy cookie/token của OPERATOR/QA rồi gọi API | TTL ngắn 15 phút; `HttpOnly/Secure/SameSite`; revoke theo `jti`; RBAC giới hạn thiệt hại; **step-up auth** cho abort/deprecate (ĐỀ XUẤT) | `ACCESS_DENIED`, login từ IP/UA lạ, nhiều request bất thường → alert; `MEMBER_TOKEN_REVOKED` | XSS trên admin portal hoặc malware máy người dùng vẫn lấy được token trong 15 phút → CSP + không lưu localStorage + khuyến nghị MFA (ĐỀ XUẤT) |
| 6 | **Báo `SUCCESS` giả để che firmware lỗi** | Thiết bị (hoặc kẻ có secret) báo `SUCCESS` dù chưa cài | State machine: chỉ nhận `SUCCESS` từ `VERIFYING` → **409 INVALID_TRANSITION**; đối soát `currentVersion`/`reportedVersion` ở check-in kế tiếp; `device_firmware_histories` chỉ ghi khi `SUCCESS` hợp lệ | `DEVICE_TASK_STAGE_REPORTED` có `before/after`; phát hiện `SUCCESS` không có tiền sử `DOWNLOADED`/`DOWNLOADING`; alert khi tỷ lệ SUCCESS tăng bất thường | Thiết bị bị compromise hoàn toàn (root) thì không thể tin tuyệt đối → giảm thiểu bằng đối soát phiên bản + hậu kiểm + mTLS/attestation ở production |
| 7 | **Mass assignment leo quyền** | Gửi body có `role`, `uploadedBy`, `actorId`, `createdBy` để tự gán quyền/danh tính | Server **không nhận** các field này từ client; lấy từ token; DTO whitelist | Request có field lạ → 400 hoặc bỏ qua + audit bất thường | Nếu code dùng ORM `update(**body)` sẽ dính → review code + test case |

---

## F. GIẢ ĐỊNH & CÂU HỎI GIÁM KHẢO

### F.1. Giả định (mọi thứ không có trong đề đều ở đây)

| # | Giả định | Giá trị dùng | Ảnh hưởng nếu khác |
| :-: | :--- | :--- | :--- |
| G1 | Thời hạn JWT | Access **15 phút**, refresh **8 giờ**, rotate mỗi lần dùng (ĐỀ XUẤT) | Đề chỉ nói "cấp token"; nếu chọn 1 giờ thì bán kính thiệt hại khi lộ token tăng tương ứng |
| G2 | Thuật toán băm mật khẩu | **Argon2id** (hoặc bcrypt cost ≥ 12) | Đề không quy định; không dùng MD5/SHA1 |
| G3 | Thu hồi token | Redis deny-list theo `jti` + logout (ĐỀ XUẤT endpoint) | Prototype hiện chưa có code web auth |
| G4 | Cửa sổ HMAC | **±300 s**, nonce TTL **600 s** — lấy theo code B (`config.py`) | Nếu chọn ±60 s sẽ khó cho thiết bị đồng hồ kém |
| G5 | Nonce store production | **Redis `SET NX EX`** dùng chung nhiều instance | Prototype in-memory (L9) |
| G6 | Mật khẩu thiết bị được cấp phát | 128-bit random (B: `secrets.token_hex(16)`), nạp lúc xuất xưởng | Không có quy trình cấp phát thật trong đề |
| G7 | Lưu secret production | **KMS/HSM** + envelope encryption; app chỉ đọc qua service | Prototype SQLite plaintext (chỉ demo) |
| G8 | Bảng `device_credentials` | **ĐỀ XUẤT** bổ sung vào ERD (L1) | Không có bảng này thì HMAC không triển khai được |
| G9 | Rate limit | Login: 5 lần/phút/IP; check-in: theo serial; audit auth-fail gộp 5 dòng/phút/serial | Đề không quy định; cần chốt với C (gateway) |
| G10 | Thời gian giữ audit | Hot 3 tháng, warm 12 tháng, cold 5 năm | Chưa chốt; chỉ ảnh hưởng chi phí |
| G11 | Ký HMAC 6 thành phần | Giữ theo B (L8) | Nếu chỉ 3 thành phần như quy ước cũ → mất bảo vệ body/path |
| G12 | Không có endpoint quản lý user/role | Tài khoản do seed/DBA tạo | Nếu cần UI quản trị → ĐỀ XUẤT thêm API + audit role change |
| G13 | "ADMIN quản lý toàn bộ" | Hiểu là quản trị hệ thống, **không** vận hành campaign (A.2, A.4) | Nếu nhóm chọn superuser → đổi ô `✘***` thành `✔*` + audit override |
| G14 | QA duyệt firmware | QA là role duyệt **chính**; ADMIN chỉ override nếu nhóm chốt | Nếu chỉ có 1 QA trực → cần cơ chế override có audit |
| G15 | IP/UA trong audit | Lưu trong `detail` (MVP) hoặc thêm cột (ĐỀ XUẤT) | Ảnh hưởng khả năng điều tra |

### F.2. Câu hỏi giám khảo có thể hỏi (5 + gợi ý trả lời)

1. **"Tại sao thiết bị không dùng JWT như người dùng?"**
   → Thiết bị không có phiên đăng nhập; JWT là bearer token dùng lại được, không gắn với từng request, không bảo vệ body; lộ 1 signing key là mất toàn fleet. HMAC per-request + secret per-device giới hạn thiệt hại đúng 1 thiết bị, lại chống replay bằng nonce + timestamp (B.5).

2. **"Nonce lưu ở đâu khi có nhiều instance API? Redis sập thì sao?"**
   → Production dùng Redis `SET NX EX` để mọi instance thấy chung. Nếu Redis sập: chọn **fail-closed** (trả 503/401, thiết bị retry sau 5 phút — chấp nhận chậm 1 chu kỳ) an toàn hơn **fail-open** (mất chống replay). Đây là đánh đổi availability vs security, nêu rõ khi trả lời.

3. **"Nếu QA nghỉ, không ai duyệt được firmware thì sao?"**
   → Cần tối thiểu 2 tài khoản QA; trường hợp khẩn cấp mới bật **ADMIN override có audit + lý do + (nếu được) 2 người xác nhận**. Không thiết kế ngoại lệ thường trực vì sẽ vô hiệu hoá four-eyes (A.4).

4. **"DBA sửa `audit_logs` thì làm sao biết?"**
   → App-role chỉ INSERT/SELECT + trigger chặn UPDATE/DELETE; hash chain phát hiện sửa/xoá lén; export WORM (Object Lock/SIEM) hằng ngày. Giới hạn: root DBA vẫn có thể tắt trigger → cần dual-control DBA + bản WORM nằm ngoài quyền DBA (C.2).

5. **"Làm sao biết thiết bị báo SUCCESS là thật?"**
   → Chỉ nhận `SUCCESS` từ `VERIFYING` (state machine), đối soát `currentVersion` ở check-in kế tiếp, ghi `device_firmware_histories` chỉ khi hợp lệ, audit before/after, alert nếu SUCCESS không có tiền sử download (E.6). Thiết bị bị root thì không thể tin tuyệt đối — đó là lý do có mTLS/attestation ở production.

6. **"Tại sao `GET /api/audit-logs` chỉ ADMIN? OPERATOR cần xem ai pause campaign của mình mà?"**
   → Audit chứa IP, hành vi bảo mật toàn hệ thống → least privilege; OPERATOR đã có `GET /api/campaigns/{id}/progress` và dashboard để biết trạng thái. Nếu cần, **ĐỀ XUẤT** endpoint riêng trả audit **giới hạn theo campaign của mình** (không lộ audit toàn hệ thống).

---

## G. RÚT GỌN CHO SLIDE 11

**Bảng ma trận gọn (dán lên slide):**

| Nhóm quyền | ADMIN | DEVELOPER | QA | OPERATOR | Device |
| :--- | :-: | :-: | :-: | :-: | :-: |
| Firmware: upload / approve / deprecate | ✘ / ✔** / ✔ | **✔** / ✘ / ✘ | ✘ / **✔*** / ✘ | ✘ / ✘ / ✘ | ✘ |
| Campaign: tạo / start-pause-resume-abort | ✘*** / ✘*** | ✘ | ✘ | **✔ / ✔*** | ✘ |
| Đọc: firmware · devices · history · progress · tasks | ✔ | ✔* | ✔* | ✔* | ✘ |
| `GET /api/audit-logs` | **✔** | ✘ | ✘ | ✘ | ✘ |
| `/api/device-agent/check-in` + `/result` | ✘ | ✘ | ✘ | ✘ | **✔*** |

*(\*) có điều kiện: `uploadedBy ≠ approvedBy` (four-eyes) · trạng thái hợp lệ nếu không 409 · đọc read-only · (\*\*) ADMIN approve là tuỳ chọn của nhóm · (\*\*\*) ADMIN break-glass: nếu bật thì bắt buộc audit `ADMIN_OVERRIDE`.*

**5 bullet tối đa:**

1. **Hai miền xác thực tách biệt:** web dùng **JWT 15' + RBAC**; thiết bị dùng **HMAC-SHA256(serial, timestamp, nonce, method, path, SHA256(body))** — 401 nếu lệch giờ > 300 s hoặc nonce dùng lại; người dùng web không gọi được endpoint device và ngược lại.
2. **RBAC tối thiểu quyền + tách nhiệm vụ:** DEVELOPER upload — QA duyệt — OPERATOR vận hành — ADMIN thu hồi/audit; **không role nào đi hết được chuỗi** rollout; four-eyes chặn ở 3 lớp (UI, service, DB CHECK) → vi phạm trả **403 `FOUR_EYES_VIOLATION`**; **ADMIN không được tự duyệt firmware của mình**.
3. **`audit_logs` append-only:** cột khớp dbml (`actorId` nullable + `actorType MEMBER|SYSTEM|DEVICE`, `action`, `targetType`, `targetId`, `detail` json); chỉ INSERT/SELECT + trigger bất biến + hash chain/WORM; `detail` lưu **before/after**, không bao giờ lưu secret/token.
4. **Ghi cả hành vi bị từ chối:** duyệt/thu hồi firmware, tạo/start/pause/resume/abort, **AUTO-PAUSE (actor = SYSTEM)**, mọi chuyển trạng thái `device_tasks`, `MEMBER_LOGIN_FAILED`, `ACCESS_DENIED` (403), `DEVICE_AUTH_FAILED`; **KHÔNG ghi heartbeat** (nếu ghi sẽ thành 10,5 tỷ dòng/năm thay vì 2,5 triệu).
5. **Giới hạn nói thẳng:** append-only bảo vệ trước ứng dụng, chống gian lận ở tầng hạ tầng cần hash chain + WORM + tách quyền DBA; lộ secret **1 thiết bị** chỉ ảnh hưởng đúng thiết bị đó (rotate + quarantine) — đó là lý do không dùng JWT dùng chung cho cả fleet.

---

## H. NHỮNG CHỖ TÔI KHÔNG CHẮC / ĐÃ PHẢI GIẢ ĐỊNH

1. **Thời hạn JWT (15 phút), refresh 8 giờ, Argon2id, deny-list `jti`, step-up auth, MFA** — **không có trong đề**, là đề xuất của tôi (G1–G3). Nếu nhóm chọn khác chỉ cần đổi con số.
2. **"ADMIN quản lý toàn bộ" được hiểu là quản trị hệ thống, không vận hành campaign** — đây là **cách hiểu của tôi** (G13); nhóm có thể chọn ADMIN superuser, khi đó ma trận phải đổi các ô `✘***` và bắt buộc audit override.
3. **ADMIN có được duyệt firmware hay không** — tôi đề xuất **chỉ QA** (ADMIN override có kiểm soát); đề bài ghi "QA (ADMIN nếu chọn)" nên **cần nhóm chốt**.
4. **Bảng `device_credentials` không có trong dbml** (L1) — toàn bộ mục B dựa trên bảng này (đúng như code B đang chạy). **Nếu A không bổ sung ERD, phần xác thực thiết bị sẽ lệch tài liệu** — cần chốt với A.
5. **Chuỗi hành động audit (`action` names, `targetType` enum) là ĐỀ XUẤT** — chưa có trong tài liệu nhóm; nếu A/C dùng tên khác phải thống nhất trước khi lên slide.
6. **Hash chain** (cột `prevHash`/`recordHash`) — tôi đề xuất MVP **nhét vào `detail.chain`** để không đổi schema; nếu nhóm muốn cột riêng thì cần A sửa dbml. Chưa chốt.
7. **Retention audit 3/12/60 tháng** và **rate-limit cụ thể** — giả định (G9, G10), cần chốt với C (vận hành) và người phụ trách hạ tầng.
8. **`GET /api/audit-logs` có ghi audit việc đọc hay không** — tôi đánh dấu **ĐỀ XUẤT** (tránh vòng lặp/khối lượng); nhóm nên quyết định vì nó ảnh hưởng quyền riêng tư.
9. **"Từ chối firmware"**: đề không có endpoint reject; tôi biểu diễn bằng lần approve bị chặn (403) + audit, và đề xuất thêm `decision: REJECT` vào body approve. **Chưa có trong đề** — nếu giám khảo hỏi, phải nói rõ đây là đề xuất.
10. **Prototype của B chưa có `audit_logs`, chưa có JWT/login/admin API** (L10) — nên slide 11 là **thiết kế**, không phải demo code. Nếu cần demo, tôi phải bổ sung vào mock API (ngoài phạm vi Task 2).
11. **Hiệu năng kiểm tra HMAC + nonce ở 3.000 RPS** — về lý thuyết HMAC-SHA256 rất nhẹ, nhưng Redis `SET NX EX` per request cần đo thực tế; tôi **không có benchmark** để khẳng định. (Liên hệ capacity: 3.000 RPS cao điểm là khả thi với Redis cluster, nhưng cần đo.)
12. **Không có endpoint quản lý người dùng/role** trong đề — nếu giám khảo hỏi "ai tạo tài khoản?", trả lời: seed/DBA ở MVP; muốn có UI thì phải bổ sung API + audit `MEMBER_ROLE_CHANGED` (ĐỀ XUẤT).
