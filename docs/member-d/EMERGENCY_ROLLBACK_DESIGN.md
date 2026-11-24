# DỪNG KHẨN CẤP & QUAY LẠI BẢN CŨ SAU KHI CHIẾN DỊCH KẾT THÚC
## Task 4 (Điểm cộng #13 & Bổ sung Slide 9) · Nền tảng triển khai cập nhật Firmware (DASAN Vietnam)

| | |
| :--- | :--- |
| **Người thực hiện** | Thành viên D — *System Reliability, Security, AI Lead & Project Coordinator* |
| **Task** | Task 4 — Điểm cộng #13: *Dừng khẩn cấp và quay lại bản cũ trên toàn bộ tập thiết bị khi phát hiện firmware lỗi sau khi chiến dịch đã kết thúc* |
| **Nguồn đề bài** | `KITS2026_OJT2_Assignments.pdf` — Bước 4 Điểm cộng #13 (trang 6/15), Slide 9 (trang 7/15) |
| **Đối chiếu đồng bộ** | `ERD/dasan_firmware_rollout.dbml` (`device_firmware_histories`, `device_tasks`) · `docs/member-a/FIRMWARE_COMPATIBILITY_MATRIX.md` §4 · `DASAN_OJT1_Member_C_Deliverables.md` · `docs/member-d/RBAC_SECURITY_AUDIT.md` |
| **Checklist đáp ứng** | `docs/checklists/system-design-gate.md` — **CHK005**, **CHK023** |

> **Một câu chốt cho Slide 9 & Hỏi đáp:** *"Hardware Watchdog cứu từng thiết bị bị boot-loop ngay lúc cài; còn khi lỗi âm ỉ chỉ bộc lộ vài ngày sau khi chiến dịch đã `COMPLETED`, nền tảng thu hồi bản lỗi (`DEPRECATED`) và phát hành **Rollback Campaign** tra ngược `device_firmware_histories` để đưa từng thiết bị về đúng bản `APPROVED` ổn định liền trước — vẫn đi qua Canary 1% và giới hạn `maxConcurrentDevices` để tuyệt đối không gây bão mạng hay lỗi hạ cấp cấu hình."*

---

## 1. BỐI CẢNH: VÌ SAO WATCHDOG & AUTO-PAUSE CHƯA ĐỦ?

Hệ thống có **3 tầng phòng thủ theo thời gian**, mỗi tầng xử lý một loại lỗi khác nhau:

| Tầng bảo vệ | Thời điểm phát hiện | Cơ chế tự động / điều phối | Lỗi nào lọt qua tầng này? |
| :--- | :--- | :--- | :--- |
| **Tầng 1 — Bootloader Watchdog** *(Thành viên B)* | `0 – 5 phút` ngay sau khi flash & reboot (`VERIFYING`) | Đếm 3 lần boot-loop trên Bank B $\to$ tự chuyển cờ boot về Bank A, báo `ROLLED_BACK` | Firmware vẫn boot lên bình thường và vượt qua self-test ban đầu |
| **Tầng 2 — Canary Soak & Auto-Pause** *(Thành viên C)* | `15 phút – 4 giờ` trong khi chiến dịch đang `RUNNING` | Ngâm thử 2–4h ở Wave 1–2; dừng ngay khi `FailureRate(Wave) > failureThresholdPercent` | Lỗi tiềm ẩn dài hạn (*latent defect*) chỉ xuất hiện sau **48–72 giờ** hoặc lỗ hổng bảo mật mới công bố |
| **Tầng 3 — Post-Completion Emergency Rollback** *(Thành viên D — #13)* | **Vài ngày / vài tuần sau** khi chiến dịch đã `COMPLETED` (`100%`) | `ADMIN` thu hồi firmware (`DEPRECATED`) + `OPERATOR` chạy **Rollback Campaign** từ `device_firmware_histories` | Lớp chốt chặn cuối cùng để khôi phục toàn bộ tập thiết bị mà không cần kỹ sư cấu hình tay |

**Ví dụ thực tế tại ISP:** Phiên bản `v2.4.1` cho dòng `DASAN-H660GM` vượt qua Canary và hoàn tất `100%` cho `50.000` hộ gia đình (`campaigns.status = COMPLETED`). Đến ngày thứ 3, bộ đếm phiên PPPoE bị tràn bộ nhớ (*memory leak sau ~72h uptime*) làm hàng loạt ONT rớt mạng ngắt quãng, hoặc đội bảo mật phát hiện lỗ hổng CVE nghiêm trọng trong thư viện OpenSSL đi kèm `v2.4.1`.

---

## 2. LUỒNG XỬ LÝ CHUẨN (2 BƯỚC TÁCH BIỆT VAI TRÒ)

```mermaid
sequenceDiagram
    autonumber
    actor ADM as System Admin
    actor OP as Operator
    participant API as Admin & Campaign API
    participant DB as PostgreSQL
    participant RD as Redis (Lock & Semaphore)
    participant DEV as Edge Devices (v2.4.1)

    Note over ADM,DB: Bước 1: Khóa van phát tán bản lỗi v2.4.1 (Ngăn dùng lại ở mọi chiến dịch mới)
    ADM->>API: PATCH /api/firmware/{v2_4_1_id}/deprecate (reason: "PPPoE leak after 72h")
    API->>DB: UPDATE firmware_versions SET status = 'DEPRECATED' + INSERT audit_logs (FIRMWARE_DEPRECATED)
    API-->>ADM: 200 OK (v2.4.1 bị khóa vĩnh viễn)

    opt Nếu vẫn còn chiến dịch khác đang RUNNING/SCHEDULED dùng v2.4.1
        OP->>API: PATCH /api/campaigns/{runningCmpId}/abort
        API->>DB: campaign -> ABORTED; tasks PENDING -> FAILED (CAMPAIGN_ABORTED) [giải phóng uq_active_device_task]
    end

    Note over OP,DB: Bước 2: Tạo & Khởi chạy Chiến dịch Quay lui (Emergency Rollback Campaign)
    OP->>API: POST /api/campaigns (mode="ROLLBACK", sourceCampaignId, firmwareId=safeAnchor_v2_3_0, targetGroupId, waves=[1,10,50,100])
    API->>DB: Kiểm tra safeAnchor_v2_3_0.status = 'APPROVED' + Lưu campaigns (DRAFT) + audit ROLLBACK_CAMPAIGN_CREATED
    API-->>OP: 201 Created

    OP->>API: PATCH /api/campaigns/{rollbackCmpId}/start
    API->>RD: Acquire Lock(targetGroupId)
    API->>DB: Chọn máy đang chạy đúng v2.4.1 + Tra device_firmware_histories lấy toFirmwareId ổn định liền trước
    API->>DB: Sinh device_tasks (fromFirmwareId = v2.4.1, toFirmwareId = bản cũ từng máy, status = PENDING)
    API->>RD: Khởi tạo sem:campaign:{rollbackCmpId} = maxConcurrentDevices & Release Lock
    API-->>OP: 200 OK (Mở Canary Wave 1 = 1%)

    loop Thiết bị Check-in mỗi 300s (hoặc trong Maintenance Window)
        DEV->>API: POST /api/device-agent/check-in (currentVersion = "2.4.1", activePartition = "B")
        API-->>DEV: 200 OK {action: "UPDATE", targetVersion: "2.3.0", downloadUrl (Pre-signed CDN), checksum}
        Note over DEV: Tải v2.3.0 ghi vào phân vùng phụ (Bank A), verify SHA-256, reboot & self-test
        DEV->>API: POST /api/device-agent/tasks/{taskId}/result (stage = "SUCCESS", reportedVersion = "2.3.0")
        API->>DB: Transaction: task -> SUCCESS, currentFirmwareId -> v2.3.0, INSERT device_firmware_histories
    end
```

---

## 3. GIẢI QUYẾT 4 BÀI TOÁN KHÓ (EDGE CASES & RÀNG BUỘC ERD)

### 3.1. Nhóm thiết bị trước đó chạy nhiều phiên bản cũ khác nhau thì lùi về bản nào? (Giải quyết `CHK023`)

Trong thực tế, trước khi lên `v2.4.1`, tập `50.000` thiết bị trong cùng `targetGroupId` có thể không đồng nhất: `40.000` máy từ `v2.3.0`, `8.000` máy từ `v2.2.5`, và `2.000` máy mới lắp đặt từ nhà máy (chưa có lịch sử trước `v2.4.1`).

Hệ thống giải quyết triệt để nhờ cấu trúc bảng `device_tasks` đã tách riêng **`fromFirmwareId` và `toFirmwareId` trên từng dòng thiết bị**, kết hợp mỏ neo **`campaigns.firmwareId` (`Safe Anchor Firmware`)**:

1. **Ưu tiên 1 — Khôi phục đúng bản liền trước của từng máy (`Per-Device History Lookup`):**
   * Tra bảng `device_firmware_histories` của thiết bị đó, lấy bản ghi gần nhất có `firmwareId <> :badFirmwareId` **VÀ** bản firmware đó hiện vẫn đang ở trạng thái **`APPROVED`** (`model` khớp).
   * Máy trước đó chạy `v2.3.0` nhận `toFirmwareId = v2.3.0`; máy trước đó chạy `v2.2.5` nhận `toFirmwareId = v2.2.5`.
2. **Ưu tiên 2 — Fallback về Mỏ neo an toàn (`campaigns.firmwareId`):**
   * Nếu thiết bị mới xuất xưởng (chỉ có 1 dòng lịch sử là `v2.4.1`) **hoặc** bản cũ từng chạy (`v2.2.0`) cũng đã bị thu hồi `DEPRECATED` trước đó $\to$ gán `device_tasks.toFirmwareId = campaigns.firmwareId` (bản chuẩn ổn định `v2.3.0 APPROVED` do Operator chọn khi tạo chiến dịch).

### 3.2. Thiết bị đã được nâng cấp tiếp lên phiên bản mới hơn (`v2.4.2` / `v2.5.0`) thì sao?

* **Quy tắc bắt buộc:** Truy vấn chọn thiết bị cho Rollback Campaign lọc cứng **`devices.currentFirmwareId = :badFirmwareId`** (chỉ tác động lên máy **đang thực sự chạy bản lỗi `v2.4.1`**).
* Nếu một nhóm nhỏ thiết bị (ví dụ Lab hoặc Canary của bản vá nóng `v2.4.2`) đã nâng lên `v2.4.2` (`currentFirmwareId = v2_4_2_id`), chúng **tự động được loại trừ**, tuyệt đối không bị kéo lùi mất bản vá mới!

### 3.3. Làm sao hỗ trợ Rollback mà không phá vỡ 9 bảng chuẩn trong ERD? (Giải quyết `CHK005`)

* **Trong phạm vi MVP (Giữ nguyên 100% schema `ERD/dasan_firmware_rollout.dbml`):**
  * Không cần thêm bảng mới. `campaigns.firmwareId` lưu phiên bản neo an toàn (`APPROVED`), còn `device_tasks.toFirmwareId` lưu phiên bản đích thực tế của từng máy.
  * Cờ điều khiển `mode: "ROLLBACK"`, `badFirmwareId` và `bypassMaintenanceWindow` được truyền trong request payload của `POST /api/campaigns` và ghi đầy đủ vào `audit_logs.detail` (`action = 'ROLLBACK_CAMPAIGN_CREATED'`).
* **Lộ trình mở rộng hậu MVP (Phase 2 Schema Evolution):**
  * Bổ sung `campaignType ENUM('UPGRADE', 'ROLLBACK') DEFAULT 'UPGRADE'`, `rollbackFromCampaignId UUID NULL`, và `bypassMaintenanceWindow BOOLEAN DEFAULT FALSE` vào bảng `campaigns` để hỗ trợ lọc/thống kê trực tiếp trên Admin Portal mà không cần đọc `audit_logs.detail`.

### 3.4. Vì sao Rollback khẩn cấp VẪN phải chạy theo đợt Canary (1% → 10% → 50% → 100%) và giữ `maxConcurrentDevices`?

Đây là câu hỏi bẫy kinh điển của hội đồng tuyển dụng (*"Đang lỗi khẩn cấp sao không hạ cấp toàn bộ 50.000 máy ngay lập tức?"*):
1. **Chống sập hạ tầng mạng & CDN:** Mở đồng loạt `50.000` lượt tải × `40 Mbps` = **`2 Tbps`** sẽ đánh sập băng thông đường trục ISP ngay trong lúc mạng đang nhạy cảm vì sự cố. Giữ `sem:campaign:{id}` (`500` slot = `20 Gbps`) thì việc tải toàn bộ `50.000` máy thực tế cũng chỉ mất **~16,7 phút**!
2. **Chống thảm họa "Bất tương thích cấu hình ngược" (*Config Downgrade Brick*):** Khi thiết bị lên `v2.4.1`, file cấu hình NVRAM có thể đã được migrate sang định dạng mới; lùi thẳng về `v2.3.0` mà không kiểm chứng trên `1%` Canary (`500` máy, Soak Time rút gọn `15–30 phút`) có thể làm toàn bộ `50.000` ONT mất cấu hình PPPoE/VLAN đồng loạt.
3. **Vẫn tận dụng Dual-Bank A/B ở phía thiết bị:** Dù trên Bank A của nhiều thiết bị vẫn còn lưu binary `v2.3.0` cũ, thiết kế chuẩn vẫn đi qua luồng tải/verify chuẩn vào phân vùng không hoạt động và chuyển cờ boot (tối ưu Phase 2: nếu bootloader xác nhận phân vùng phụ sẵn có image khớp đúng `SHA-256` của `toFirmware`, thiết bị có thể **bỏ qua bước tải 50 MB** và chuyển thẳng sang `INSTALLING/VERIFYING`, giúp tốc độ rollback nhanh gấp 10 lần và tốn `0 GB` băng thông CDN!).

### 3.5. Xử lý Khung giờ bảo trì (`maintenanceWindow`) khi Rollback khẩn cấp

| Mức độ sự cố | Chính sách Khung giờ bảo trì | Hành vi hệ thống |
| :--- | :--- | :--- |
| **Mức Sev-2** *(Lỗi rò bộ nhớ chậm, chưa mất mạng diện rộng)* | `bypassMaintenanceWindow = false` *(Mặc định)* | Tôn trọng giờ bảo trì ban đêm (`01:00–05:00` theo `timezone` của ISP) để không làm reboot modem giữa giờ làm việc ban ngày của khách hàng. |
| **Mức Sev-1 / P0** *(Mất kết nối diện rộng hoặc lỗ hổng bảo mật đang bị khai thác)* | `bypassMaintenanceWindow = true` *(Yêu cầu nhập `emergencyReason`)* | Cấp task ngay ở lần check-in kế tiếp (`≤ 5 phút`), ghi bắt buộc `audit_logs` với cờ `emergencyWindowBypass = true` để hậu kiểm. |

---

## 4. TRUY VẤN SQL CHỌN THIẾT BỊ & XÁC ĐỊNH BẢN CŨ TỪNG MÁY

```sql
-- $1: campaignId (Rollback Campaign), $2: badFirmwareId (phiên bản lỗi cần thu hồi, vd v2.4.1)
WITH last_good_history AS (
    SELECT DISTINCT ON (h."deviceId")
           h."deviceId",
           h."firmwareId" AS prev_firmware_id
    FROM device_firmware_histories h
    JOIN firmware_versions fw ON fw.id = h."firmwareId"
    WHERE h."firmwareId" <> $2
      AND fw.status = 'APPROVED'
    ORDER BY h."deviceId", h."installedAt" DESC
)
SELECT d.id                                              AS device_id,
       d."currentFirmwareId"                             AS from_firmware_id,
       COALESCE(lgh.prev_firmware_id, c."firmwareId")    AS to_firmware_id
FROM campaigns c
JOIN firmware_versions anchor_fw ON anchor_fw.id = c."firmwareId"
JOIN devices d                   ON d."groupId" = c."targetGroupId"
LEFT JOIN last_good_history lgh  ON lgh."deviceId" = d.id
WHERE c.id = $1
  AND anchor_fw.status = 'APPROVED'                      -- Mỏ neo bắt buộc là bản APPROVED
  AND d.model = anchor_fw.model                          -- Khớp đúng dòng thiết bị
  AND d."currentFirmwareId" = $2                         -- CHỈ lùi máy đang chạy đúng bản lỗi (bỏ qua máy đã lên v2.4.2+)
  AND NOT EXISTS (                                       -- Không đụng thiết bị đang có active task
      SELECT 1
      FROM device_tasks dt
      WHERE dt."deviceId" = d.id
        AND dt.status IN ('PENDING', 'DOWNLOADING', 'INSTALLING', 'VERIFYING')
  );
```

---

## 5. DÒNG BỔ SUNG VÀO BẢNG TÌNH HUỐNG LỖI TRÊN SLIDE 9 (BÀN GIAO CHO B & C)

Dán trực tiếp dòng thứ 6 dưới đây vào cuối **Bảng Tình Huống Lỗi (Slide 9)**:

| Tình huống lỗi | Điều gì xảy ra? | Phát hiện thế nào? | Cơ chế khôi phục tự động / điều phối |
| :--- | :--- | :--- | :--- |
| **6. Lỗi tiềm ẩn phát hiện sau khi chiến dịch đã `COMPLETED`** *(Bonus #13 — D)* | Firmware mới vượt qua bước boot ban đầu nhưng bộc lộ lỗi ngầm sau vài ngày chạy thực tế (rò bộ nhớ PPPoE, lỗi hiệu năng hoặc lỗ hổng CVE). | Hệ thống giám sát NOC của ISP / cảnh báo lỗi hậu kiểm từ khách hàng và đội QA sau triển khai. | 1) `ADMIN` gọi `/deprecate` khóa vĩnh viễn bản lỗi.<br>2) `OPERATOR` tạo **Rollback Campaign**: SQL tra ngược `device_firmware_histories` gán từng máy (`currentFirmwareId = bản lỗi`) về đúng bản `APPROVED` ổn định liền trước (bỏ qua máy đã lên bản vá mới hơn), vẫn chạy qua Canary `1%` + giới hạn `maxConcurrentDevices` + Dual-Bank an toàn. |
