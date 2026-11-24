# MA TRẬN QUY TẮC TƯƠNG THÍCH FIRMWARE
## DASAN Firmware Rollout Platform — Luồng 1 & Slide 6 (Đã đồng bộ Cross-review)

> **Mục tiêu:** Bảo đảm firmware chỉ được triển khai tới thiết bị đúng dòng sản phẩm (`model`), thuộc đúng nhóm đích (`targetGroupId`), đang chạy phiên bản nền được hỗ trợ, không có tác vụ cập nhật nào đang chạy song song và chỉ sử dụng firmware ở trạng thái `APPROVED`.

---

## 1. Kiểm tra ở bước Upload (`POST /api/firmware`)

Các kiểm tra này được thực hiện tại `Firmware Service` trước khi lưu bản ghi ở trạng thái `UPLOADED` và trước khi QA xem xét phê duyệt:

| Tiêu chí | Điều kiện hợp lệ | Nếu không thỏa mãn |
| :--- | :--- | :--- |
| **SHA-256 checksum** | SHA-256 hệ thống tính trực tiếp từ file thực tế `=` `checksum` trong metadata. | `400 Bad Request`; từ chối lưu file. |
| **Model hợp lệ** | `model` tồn tại và nằm trong danh mục dòng thiết bị hệ thống hỗ trợ. | `400 Bad Request`; từ chối metadata. |
| **Khoảng phiên bản (Version range)** | `minRequiredVersionCode <= versionCode` (công thức quy ước Q8: `MAJOR * 10000 + MINOR * 100 + PATCH`, ví dụ `v2.4.1 → 20401`). | `400 Bad Request`; khoảng phiên bản không hợp lệ. |
| **Chống trùng bản phát hành (Duplicate release)** | Không tồn tại bản ghi nào trong `firmware_versions` có cùng cặp `(model, versionNo)`. | `409 Conflict`; yêu cầu đổi `versionNo` hoặc xử lý bản phát hành trùng. |

* **Bảo vệ tầng CSDL:** Bảng `firmware_versions` khai báo `UNIQUE (model, versionNo)` và `CHECK (minRequiredVersionCode <= versionCode)`. Backend bắt lỗi unique constraint để trả về `409 Conflict` chuẩn xác.

---

## 2. Ma trận chọn thiết bị cho Campaign nâng cấp thông thường

| Tiêu chí | Điều kiện hợp lệ | Nếu không thỏa mãn | Thời điểm kiểm tra |
| :--- | :--- | :--- | :--- |
| **Model matching** | `devices.model = targetFirmware.model` | Loại thiết bị khỏi danh sách đủ điều kiện. | Khi lập danh sách thiết bị & đối chiếu lại lúc check-in. |
| **Target group** | `devices.groupId = campaign.targetGroupId` | Không đưa thiết bị ngoài nhóm khách hàng/vùng đích vào chiến dịch. | Khi lập danh sách thiết bị. |
| **Minimum required version** | `currentFirmware.versionCode >= targetFirmware.minRequiredVersionCode` | Từ chối nâng cấp nhảy cóc; cần đi qua chiến dịch nâng cấp phiên bản trung gian trước. | Khi lập danh sách thiết bị & lúc giao task check-in. |
| **Forward upgrade only** | `currentFirmware.versionCode < targetFirmware.versionCode` | Bỏ qua thiết bị đã ở cùng phiên bản hoặc phiên bản mới hơn (tránh cập nhật lặp hoặc vô tình hạ cấp). | Khi lập danh sách thiết bị. |
| **No active concurrent task** | Thiết bị chưa có `device_tasks` ở trạng thái `PENDING`, `DOWNLOADING`, `INSTALLING`, `VERIFYING` | Từ chối tạo task chồng chéo (`409 Conflict` hoặc loại trừ theo chính sách chiến dịch). | Khi Start chiến dịch (kèm Redis Lock + Partial Unique Index). |
| **Firmware approval & Non-deprecated** | `targetFirmware.status = 'APPROVED'` *(đồng thời loại trừ `UPLOADED` và `DEPRECATED`)* | Chặn tạo/chạy chiến dịch (`409 FIRMWARE_NOT_APPROVED`); dừng cấp phát nếu bị `ADMIN` thu hồi giữa chừng. | Khi tạo campaign, trước mỗi wave và lúc thiết bị check-in. |

---

## 3. Ví dụ kiểm tra phiên bản (Quy ước số nguyên Q8)

Công thức quy đổi `versionCode`: **`MAJOR * 10000 + MINOR * 100 + PATCH`** *(hỗ trợ chính xác các bản vá lẻ như `v2.4.1 → 20401`, không bao giờ so sánh chuỗi theo thứ tự từ điển vì `"v10.0.0" < "v2.0.0"`)*.

Giả sử firmware mục tiêu là **`v4.0.0` (`versionCode = 40000`)** và phiên bản nền tối thiểu là **`v2.0.0` (`minRequiredVersionCode = 20000`)**:

| Firmware hiện tại (`versionCode`) | Model khớp | Đạt `minRequiredVersionCode` (`>= 20000`) | Nhỏ hơn bản đích (`< 40000`) | Kết quả xét duyệt |
| :--- | :---: | :---: | :---: | :--- |
| `v1.0.0` (`10000`) | Có | Không | Có | **Không hợp lệ** — thấp hơn phiên bản nền tối thiểu |
| `v2.0.0` (`20000`) | Có | Có | Có | **Hợp lệ** |
| `v3.0.1` (`30001`) | Có | Có | Có | **Hợp lệ** |
| `v4.0.0` (`40000`) | Có | Có | Không | **Không hợp lệ** — thiết bị đã ở phiên bản mục tiêu |
| `v4.1.0` (`40100`) | Có | Có | Không | **Không hợp lệ** — chặn hạ cấp trong rollout thông thường |
| `v3.0.0` (`30000`) | Không | Có | Có | **Không hợp lệ** — sai dòng thiết bị (`model`) |

---

## 4. Ngoại lệ nghiệp vụ: Emergency Rollback Campaign (Điểm cộng #13)

* Điều kiện `currentFirmware.versionCode < targetFirmware.versionCode` **chỉ áp dụng cho chiến dịch nâng cấp thông thường**.
* Khi phát hiện lỗi nghiêm trọng sau khi chiến dịch đã hoàn tất, **Emergency Rollback Campaign** cho phép đưa thiết bị từ phiên bản cao hơn quay về phiên bản firmware ổn định trước đó (tra cứu từ `device_firmware_histories`).
* **Giới hạn an toàn bắt buộc:** Nhánh Rollback chỉ bỏ qua duy nhất chiều so sánh `< targetFirmware.versionCode`. Toàn bộ các điều kiện còn lại (`model` khớp, đúng `targetGroupId`, không trùng task active, checksum toàn vẹn và `targetFirmware.status = 'APPROVED'` — tuyệt đối không dùng bản `DEPRECATED`) vẫn phải thực thi đầy đủ.

---

## 5. Truy vấn SQL chọn thiết bị đủ điều kiện

Truy vấn dưới đây áp dụng khi khởi chạy chiến dịch nâng cấp thông thường (`$1` là `campaignId`):

```sql
SELECT d.id
FROM campaigns c
JOIN firmware_versions target_fw
    ON target_fw.id = c.firmwareId
JOIN devices d
    ON d.groupId = c.targetGroupId
JOIN firmware_versions current_fw
    ON current_fw.id = d.currentFirmwareId
WHERE c.id = $1
  AND d.model = target_fw.model
  AND current_fw.model = d.model
  AND current_fw.versionCode >= target_fw.minRequiredVersionCode
  AND current_fw.versionCode < target_fw.versionCode
  AND target_fw.status = 'APPROVED'
  AND NOT EXISTS (
      SELECT 1
      FROM device_tasks dt
      WHERE dt."deviceId" = d.id
        AND dt.status IN ('PENDING', 'DOWNLOADING', 'INSTALLING', 'VERIFYING')
  );
```

---

## 6. Đối chiếu các trường & ràng buộc trong ERD

| Bảng | Trường / Ràng buộc | Mục đích bảo vệ |
| :--- | :--- | :--- |
| `devices` | `model`, `groupId`, `currentFirmwareId` | Xác định dòng thiết bị, nhóm khách hàng đích và phiên bản firmware đang chạy ổn định. |
| `firmware_versions` | `model`, `versionNo`, `versionCode`, `minRequiredVersionCode` | Định danh bản phát hành và so sánh khoảng phiên bản bằng số nguyên (Q8). |
| `firmware_versions` | `status` (`UPLOADED \| APPROVED \| DEPRECATED`) | Chỉ cho phép chọn `APPROVED`; loại trừ tuyệt đối `UPLOADED` và `DEPRECATED`. |
| `firmware_versions` | `UNIQUE (model, versionNo)` | Chặn upload trùng phiên bản cho cùng một dòng thiết bị (`409 Conflict`). |
| `firmware_versions` | `CHECK (minRequiredVersionCode <= versionCode)` | Chặn khai báo khoảng phiên bản nền phi lý ngay tại tầng Database. |
| `firmware_versions` | `CHECK (approvedBy IS NULL OR uploadedBy <> approvedBy)` | Thực thi nguyên tắc 4-mắt (Four-eyes approval) ở tầng Database. |
| `campaigns` | `targetGroupId`, `firmwareId` | Ràng buộc phạm vi nhóm thiết bị và bản firmware mục tiêu của chiến dịch. |
| `device_tasks` | Partial Unique Index `uq_active_device_task(deviceId)` | Chốt chặn cuối đảm bảo 1 thiết bị không bao giờ nhận đồng thời 2 tác vụ đang hoạt động. |
