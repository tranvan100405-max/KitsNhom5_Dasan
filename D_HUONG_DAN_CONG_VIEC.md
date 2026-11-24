# Hướng dẫn công việc cho Thành viên D

> File theo dõi cá nhân. Cập nhật lần cuối: 24/11/2026. Hạn thuyết trình: **30/11/2026** (còn ~6 ngày).
> Cách làm: DeepSeek soạn nháp theo brief, mình **tự kiểm tra từng con số**, rồi ghi vào `docs/prompt-log.md`.

---

## 1. Bài toán nhóm đang giải (đọc 1 phút)

**Đề bài:** Thiết kế *Nền tảng triển khai cập nhật firmware* (Firmware Rollout Platform) cho DASAN Vietnam, bài OJT KITS 2026, track Thiết kế hệ thống.

**Tình huống:** Các nhà mạng (ISP) có hàng chục nghìn thiết bị (switch, router, ONT/ONU modem quang). Hiện nay kỹ sư cập nhật firmware thủ công, theo dõi bằng Excel. Nếu một firmware lỗi bị đẩy đồng loạt, hàng nghìn nhà mất mạng.

**Nhóm phải thiết kế một hệ thống:**
- Cập nhật cho **100.000 thiết bị**, theo từng đợt (canary): 1% → 10% → 50% → 100%. Đợt sau chỉ chạy khi đợt trước đủ tốt.
- **Tự tạm dừng** khi tỷ lệ lỗi vượt ngưỡng; có **rollback** (quay lại bản cũ).
- Thiết bị **chủ động hỏi việc** (pull/check-in) vì server không gọi được vào mạng khách hàng.
- **Phân quyền** (Developer upload, QA duyệt, Operator vận hành, Admin quản lý), **audit trail** (ai làm gì, lúc nào).
- Một tính năng **AI**: phân loại log lỗi (phương án C), con người duyệt kết quả.

**Đây là bài thiết kế, không bắt buộc code.** Giám khảo chấm theo **lập luận** ("vì sao"), không chỉ sơ đồ.

**Sản phẩm phải nộp:** slide tối đa 16 trang (.pptx và .pdf), file nguồn sơ đồ (draw.io/dbml), nhật ký prompt AI (`docs/prompt-log.md`). Prototype là điểm cộng.

**Thuật ngữ nhanh:**
| Từ | Nghĩa |
|---|---|
| Check-in | Thiết bị tự hỏi server "có việc gì cho tôi không?" mỗi 5 phút |
| Campaign | Một chiến dịch cập nhật firmware |
| Wave | Một đợt trong chiến dịch (1%, 10%, 50%, 100%) |
| Canary | Thử ít trước, ổn mới mở rộng |
| Rollback | Quay lại firmware cũ |
| Pull vs Push | Pull: thiết bị tự hỏi. Push: server gọi thiết bị |
| RBAC | Phân quyền theo vai trò |
| Audit trail | Sổ ghi "ai làm gì lúc nào", chỉ thêm, không sửa |
| HMAC / JWT | Cách xác thực: HMAC cho thiết bị, JWT cho người dùng web |
| Idempotency | Gửi cùng yêu cầu 2 lần vẫn cho kết quả như 1 lần |
| CDN | Mạng phân phối file, giảm tải cho máy chủ |

---

## 2. Nhóm có 4 người, ai làm gì

| Vai | Phụ trách | Người làm (suy luận từ git) |
|---|---|---|
| A | ERD, luồng phát hành, quy tắc tương thích | `spadez2802` (đã nộp ERD) |
| B | Phía thiết bị: check-in, state machine, idempotency | `CryAndRRich` (đã có prototype) |
| C | Campaign engine, đợt, tự tạm dừng, đồng thời | Chưa xác định |
| **D (mình)** | **Quy mô, bảo mật, AI, rollback, ghép slide, điều phối** | **Chưa xác định** |

---

## 3. Việc của D (checklist)

### Task 1. Ước tính quy mô (slide 10), làm TRƯỚC
- [ ] Check-in trung bình: 100.000 ÷ 300 s ≈ **333 RPS**
- [ ] Check-in cao điểm (thundering herd): **1.500–3.000 RPS**, giải pháp: jitter, rate limit
- [ ] Dữ liệu một đợt 10%: 5.000 máy × 50 MB ≈ **250 GB** *(lưu ý Q1: wave cộng dồn, wave 2 thực chỉ thêm 9% ≈ 4.500 máy ≈ 225 GB; ghi rõ đang tính cái nào)*
- [ ] Băng thông: 500 máy × 5 MB/s = 2,5 GB/s ≈ **20 Gbps** → cần CDN
- [ ] Thời gian hoàn tất chiến dịch 50.000 máy: tính **theo từng wave**, tính cả check-in 5 phút, thời gian cài (timeout 10'), soak time 2h. *Không gộp một con số, vì "2–3 giờ" trong spec hiện chưa có lập luận*
- [ ] `device_tasks` tăng ≈ **500.000 dòng/năm** (giả định ~10 chiến dịch × 50.000 máy); ước tính thêm `audit_logs`
- [ ] Điểm nghẽn: băng thông, ghi DB; giải pháp cho từng cái
- [ ] Kịch bản **gấp 10 lần** (1.000.000 máy): cái gì gãy đầu tiên, sửa thế nào
- [ ] Mọi giả định đều được ghi rõ

### Task 2. Bảo mật, RBAC, audit (slide 11)
- [ ] Ma trận: hàng là endpoint, cột là ADMIN / DEVELOPER / QA / OPERATOR / Device
- [ ] Duyệt firmware: QA và Admin, **điều kiện `uploadedBy ≠ approvedBy`** (four-eyes)
- [ ] Upload: DEVELOPER; thu hồi (deprecate): ADMIN; tạo và điều khiển campaign: OPERATOR; đọc audit-logs: ADMIN
- [ ] Giải thích: người dùng web dùng JWT, thiết bị dùng HMAC-SHA256(serialNo + timestamp + nonce) để chống replay
- [ ] Thiết kế bảng `audit_logs`: append-only, `actorId` nullable, `actorType` = MEMBER | SYSTEM | DEVICE
- [ ] Liệt kê hành động phải ghi log (duyệt, thao tác campaign, đổi trạng thái, tự tạm dừng)

### Task 3. Tính năng AI và `docs/prompt-log.md` (slide 13), BẮT BUỘC NỘP
- [ ] Prompt đủ 5 phần: mục đích, bối cảnh, trường đầu vào, tiêu chí, định dạng đầu ra (JSON Schema)
- [ ] Bộ lọc backend kiểm tra JSON, sai định dạng thì từ chối
- [ ] **Chạy thật** trên một model AI, chụp input/output nguyên văn (dữ liệu giả, đã ẩn danh); ghi đúng tên model
- [ ] Có ít nhất **1 trường hợp AI sai/thiếu** (xảy ra thật, không dựng) + cách nhóm sửa
- [ ] Con người duyệt, AI không tự dừng hay rollback
- [ ] Fallback: AI lỗi thì chỉ ẩn khung gợi ý; auto-pause của C vẫn chạy độc lập
- [ ] Ghi `docs/prompt-log.md` (1–2 trang): prompt v1 → output → vấn đề → prompt v2 → output → kết luận

### Task 4. Rollback sau chiến dịch (điểm cộng #13)
- [ ] Luồng "Rollback Campaign": firmware đích là bản trước, lấy từ `device_firmware_histories`
- [ ] Xử lý thiết bị đã bị chiến dịch khác nâng tiếp; vẫn tuân thủ quy tắc tương thích
- [ ] Thêm 1 dòng vào bảng tình huống lỗi ở slide 9 (phối hợp với C)

### Task 5. Điều phối và slide
- [ ] Họp chốt quy ước tên bảng, trạng thái, API (60 phút đầu)
- [ ] Ghép 16 slide, rà soát sơ đồ của A, B, C có mâu thuẫn không
- [ ] Soạn slide của D: **1** (bìa), **2** (vấn đề, phạm vi), **10** (quy mô), **11** (bảo mật), **13** (AI), **14** (đánh đổi, ≥3 quyết định + phương án bị loại), **15** (đóng góp cá nhân), **16** (tổng kết, demo, Q&A)
- [ ] Xuất `.pptx` và `.pdf`

### Task 6. Mock API (điểm cộng, làm CUỐI)
- [ ] Đừng làm lại: nhánh `feature/tv-b-device` của B đã có FastAPI + SQLite chạy được check-in → báo kết quả
- [ ] Chỉ cần bảo đảm chạy được Swagger UI và có dữ liệu mẫu để demo (hỏi B trước khi chỉnh)

---

## 4. Thứ tự nên làm
1. Task 1 (nhanh, cần cho slide 10)
2. Task 2
3. Task 3 (file bắt buộc nộp, không để sát hạn)
4. Task 4
5. Task 5 (slide)
6. Task 6 (Mock API)

---

## 5. Quy ước nhóm phải giữ khi làm (Q1–Q10 trong `DASAN_OJT1_Team_Role_Assignment.md`)
- **Q1** Tỷ lệ wave cộng dồn: 1% → 10% → 50% → 100%, kích thước từng đợt = 1% / 9% / 40% / 50%
- **Q2** Ngưỡng sang wave tiếp theo mặc định 95%, soak time ≥ 2h (wave 1, 2)
- **Q4** Tỷ lệ lỗi chỉ đếm trạng thái cuối (SUCCESS, ROLLED_BACK, FAILED/TIMEOUT hết 3 lần retry)
- **Q6** Slot tải cấp khi DOWNLOADING, trả khi INSTALLING hoặc lỗi tải
- **Q9** Timeout: tải 15', cài 10', verify 5'; retry tối đa 3, backoff 1 → 5 → 15 phút
- Enum trạng thái:
  - Campaign: `DRAFT, SCHEDULED, RUNNING, PAUSED, COMPLETED, ABORTED`
  - Device task: `PENDING, DOWNLOADING, INSTALLING, VERIFYING, SUCCESS, FAILED, TIMEOUT, ROLLED_BACK`

---

## 6. Dùng DeepSeek thế nào cho đúng đề
- Đề **cho phép** dùng AI hỗ trợ thiết kế, nhưng phải **giải thích và bảo vệ được từng quyết định**.
- Đề yêu cầu **nhật ký prompt**: đã hỏi gì, nhận gì, sửa/từ chối gì và vì sao.
- Quy trình mỗi task: DeepSeek soạn nháp → **mình tự tính lại các con số chính** → nhờ rà soát → sửa → ghi vào prompt-log.
- Đầu mỗi lần hỏi DeepSeek, dán đoạn dặn này và gửi kèm file quy ước nhóm:

```
Bối cảnh: đồ án OJT thiết kế "Firmware Rollout Platform" cho DASAN (100.000 thiết bị, canary 1%→10%→50%→100%).
Mọi con số, tên bảng, tên trạng thái PHẢI khớp tài liệu nhóm: DASAN_OJT1_Team_Role_Assignment.md
(mục 1: enum trạng thái và quy ước Q1–Q10). Không tự đổi tên trạng thái hay tự thêm giả định
mà không ghi rõ là "giả định". Mọi phép tính phải ghi công thức và đơn vị. Viết tiếng Việt.
```

---

## 7. Câu hỏi giám khảo có thể hỏi D (chuẩn bị trả lời)
1. Tăng lên 1.000.000 thiết bị thì thành phần nào gãy đầu tiên?
2. Vì sao không cho AI tự động hủy chiến dịch khi thấy lỗi nghiêm trọng?
3. Con số 20 Gbps ra từ đâu? Vì sao phải dùng CDN?
4. Vì sao thiết bị dùng HMAC mà không dùng JWT như người dùng web?
5. Nếu dịch vụ AI sập thì hệ thống có còn bảo vệ được thiết bị không?

---

## 8. Tình trạng repo hiện tại (để biết còn thiếu gì)
- Đã có: tài liệu đặc tả, phân vai, ERD (`ERD/`), thiết kế và prototype của B (nhánh `feature/tv-b-device`, chưa merge).
- **Chưa có:** `docs/prompt-log.md`, 6 file sơ đồ draw.io (thư mục `diagrams/` đã bị xóa khỏi git), slide, Mock API riêng của D.
- Cần xác nhận với nhóm: ai là C và D, để điền slide 1 và slide 15.
- Chưa nhất quán trong tài liệu: soak time (2h hay 2–4h), điều kiện cỡ mẫu tối thiểu của auto-pause, ước tính "2–3 giờ cho 50.000 máy".
