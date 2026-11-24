# TÁC NHÂN, CA SỬ DỤNG & BẢNG THUẬT NGỮ CHUẨN HÓA
## DASAN Firmware Rollout Platform — Nội dung Slide 3 (Phụ trách: Thành viên A)

---

## 1. Các tác nhân hệ thống & Ca sử dụng chính (Actors & Use Cases)

Hệ thống phân tách rõ **2 miền truy cập** (Con người qua Admin Portal dùng `JWT + RBAC` · Thiết bị cạnh qua Edge API dùng `HMAC-SHA256 / mTLS`) theo nguyên tắc **Tối thiểu quyền (Least Privilege)** và **Tách biệt nhiệm vụ (Separation of Duties)**:

| Tác nhân (Actor) | Miền xác thực | Nhu cầu cốt lõi & Ca sử dụng chính | Giới hạn phân quyền (Vì sao?) |
| :--- | :---: | :--- | :--- |
| **Developer** | JWT (`DEVELOPER`) | Tải bản build firmware (`.bin`), khai báo metadata (`model`, `versionNo`, `minRequiredVersion`, `checksum` SHA-256) và ghi chú phát hành (`POST /api/firmware`). | **Không được duyệt** firmware và **không được chạy** chiến dịch để tránh tự phát hành code chưa kiểm thử. |
| **QA Engineer** | JWT (`QA`) | Rà soát kết quả kiểm thử lab, phê duyệt bản phát hành theo **nguyên tắc 4-mắt** (`PATCH /api/firmware/{id}/approve`, bắt buộc `approvedBy ≠ uploadedBy`); theo dõi chỉ số chất lượng sau cập nhật. | Không được tự duyệt firmware do chính mình tải lên (`403 FOUR_EYES_VIOLATION`); không bấm nút điều hành rollout. |
| **Operator** | JWT (`OPERATOR`) | Lên kế hoạch chiến dịch theo đợt Canary (`1% → 10% → 50% → 100%`), cấu hình `failureThresholdPercent`, `maxConcurrentDevices`, bấm `Start / Pause / Resume / Abort`, giám sát Dashboard & cảnh báo AI. | Chỉ được chọn firmware ở trạng thái `APPROVED`; không thể tự phê duyệt firmware hoặc sửa/xóa `audit_logs`. |
| **System Admin** | JWT (`ADMIN`) | Thu hồi khẩn cấp firmware lỗi (`PATCH /api/firmware/{id}/deprecate`), tra cứu toàn bộ nhật ký kiểm toán (`GET /api/audit-logs`), quản trị tài khoản & khóa thiết bị. | Không gom trọn vòng đời *upload → approve → rollout* vào một người; mọi thao tác nhạy cảm đều lưu vết kiểm toán. |
| **Edge Device Agent** *(100.000 ONT/ONU, Router, Switch)* | `HMAC-SHA256` / `mTLS` | Định kỳ **Check-in (Pull 5 phút ± 30s Jitter)** hỏi việc (`POST /api/device-agent/check-in`), tải file trực tiếp từ CDN qua Pre-signed URL, flash vào phân vùng phụ (Dual-Bank A/B) và báo cáo `stage` / kết quả (`POST /tasks/{id}/result`). | Chỉ gọi được đúng 2 endpoint `/api/device-agent/*`; lộ secret của 1 thiết bị không ảnh hưởng thiết bị khác hay API quản trị. |

---

## 2. Bảng thuật ngữ nghiệp vụ thống nhất toàn nhóm (Glossary)

| Thuật ngữ | Ý nghĩa trong thiết kế của nhóm |
| :--- | :--- |
| **ONT / ONU** | Thiết bị đầu cuối mạng quang đặt tại nhà thuê bao ISP (tương tự modem cáp quang); nằm sau NAT/Firewall khách hàng nên máy chủ không thể chủ động mở kết nối tới. |
| **Check-in (Pull + Jitter)** | Cơ chế thiết bị chủ động gọi về server mỗi `300s ± 30s` ngẫu nhiên để báo danh sống (`lastCheckInAt`) và nhận tác vụ cập nhật nếu có, triệt tiêu hiện tượng *Thundering Herd*. |
| **Four-Eyes Approval** | Nguyên tắc kiểm soát hai người độc lập: người tải firmware lên (`uploadedBy`) tuyệt đối không được là người phê duyệt (`approvedBy`). |
| **Canary / Wave Rollout** | Chiến lược chia nhỏ đợt triển khai theo tỷ lệ cộng dồn (`1% → 10% → 50% → 100%`), kết hợp thời gian ngâm (*Soak Time 2–4h*) và ngưỡng thành công (`≥ 95%`) trước khi mở rộng. |
| **Auto-Pause** | Cơ chế bảo vệ tự động chuyển chiến dịch sang `PAUSED` ngay khi tỷ lệ lỗi của các tác vụ đã kết thúc trong Wave vượt `failureThresholdPercent` (với cỡ mẫu tối thiểu `N ≥ 50`), hoạt động cơ học độc lập với AI. |
| **Dual-Bank (A/B Partition) & Watchdog** | Thiết kế phần cứng 2 phân vùng nhớ: giữ nguyên firmware cũ đang chạy ở Bank A, ghi bản mới vào Bank B. Nếu khởi động Bank B bị lỗi (*boot-loop* 3 lần), Hardware Watchdog tự quay về Bank A và báo `ROLLED_BACK`. |
| **Maintenance Window** | Khung giờ bảo trì ban đêm theo múi giờ địa phương của từng nhà mạng ISP (`device_groups.timezone` + `maintenanceWindow`, ví dụ `01:00–05:00`), ngoài khung giờ server trả `NO_TASK`. |
