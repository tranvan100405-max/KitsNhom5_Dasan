# ƯỚC TÍNH QUY MÔ & NĂNG LỰC (CAPACITY ESTIMATION)
## Task 1 — Nội dung Slide 10 · Nền tảng triển khai cập nhật Firmware (DASAN Vietnam)

| | |
| :--- | :--- |
| **Người thực hiện** | Thành viên D — *System Reliability, Security, AI Lead & Project Coordinator* |
| **Task** | Task 1: Capacity Estimation (phục vụ **Slide 10** — "Quy mô, năng lực, điểm nghẽn & mở rộng gấp 10 lần") |
| **Nguồn số liệu gốc** | `KITS2026_OJT2_Assignments.pdf` — mục **"Thông số năng lực"** (trang 6/15) |
| **Nguồn quy ước** | `DASAN_OJT1_Team_Role_Assignment.md` §1 — quy ước **Q1–Q10**; `DASAN_OJT1_System_Design_Specification.md` §4 |
| **File kiểm chứng** | [`capacity_calc.py`](capacity_calc.py) — in lại **toàn bộ** con số trong tài liệu (output ở **Phụ lục 1**) |
| **Quy ước đơn vị** | 1 MB = 10⁶ byte, 1 GB = 1.000 MB, 1 TB = 1.000 GB (thập phân); Mbps/Gbps là bit/giây. Số thập phân dùng dấu phẩy kiểu Việt Nam. |
| **Phiên bản** | **v1.1** — hiệu chỉnh nhãn kịch bản (hạn chót wave **1 h là ĐỀ XUẤT của D, khác mặc định 24 h của Q7**) và thay số hạng "+150 s" bằng mô hình có công thức (`C0 = D × T_checkin`); **chờ B & C review** trước khi chốt (xem D.2 và H22). |

> **Nguyên tắc:** mọi con số dưới đây đều có **công thức + giả định + lập luận bậc độ lớn**. Giả định nào không có trong đề bài đều nằm ở **mục H**. Tên bảng / tên trạng thái dùng đúng quy ước nhóm (`device_tasks`, `audit_logs`, `DOWNLOADING`, `ROLLED_BACK`, …), **không đổi tên**.

---

## 0. BẢNG TỔNG HỢP (TL;DR)

| # | Chỉ số | Kết quả | Công thức / lập luận ngắn |
| :-: | :--- | :--- | :--- |
| 1 | Check-in trung bình | **333,33 RPS** | 100.000 thiết bị / 300 s |
| 2 | Check-in cao điểm (thundering herd) | **1.500 – 3.000 RPS** (4,5–9× trung bình) | 30% fleet = 30.000 máy online lại trong 10–20 s |
| 3 | Tải API check-in lúc cao điểm | **~24 Mbps** (không đáng kể) | 3.000 RPS × 1 KB/lượt |
| 4 | Cỡ từng đợt (Q1, cộng dồn 1/10/50/100%) | **500 / 4.500 / 20.000 / 25.000** máy | hiệu hai mốc cộng dồn liền kề |
| 5 | Dữ liệu **mốc 10% cộng dồn** | **250 GB** (5.000 máy) | 5.000 × 50 MB |
| 6 | Dữ liệu **đợt riêng wave 2 (9%)** | **225 GB** (4.500 máy) | 4.500 × 50 MB |
| 7 | Tổng dữ liệu campaign 50.000 máy | **2.500 GB = 2,5 TB** (3,0 TB kèm retry ×1,2) | 50.000 × 50 MB |
| 8 | Lưu lượng firmware/năm (edge) | **30 TB/năm** | 10 campaign × 3,0 TB |
| 9 | Băng thông đỉnh | **2.500 MB/s = 2,5 GB/s = 20 Gbps** | `maxConcurrentDevices` 500 × 5 MB/s |
| 10 | Thời gian tải toàn campaign (nếu chỉ tính tải) | **16,67 phút** | 2.500 GB / 2,5 GB/s |
| 11 | Thời gian **thực thi tải + cài** 4 wave | **29,7 – 48,7 phút** (tới 100,7 phút nếu mọi timeout Q9 xảy ra) | mô hình mục D, slot chỉ giữ lúc `DOWNLOADING` (Q6) |
| 12 | **Tổng thời gian campaign** | **4,49 h (tốt nhất) · 4,81 h (chỉ chọn máy ONLINE) · 8,00 h (nếu chốt hạn chót wave 1 h) · 100 h (giữ đúng mặc định Q7 24 h)** | soak 4 h + hạn chót straggler |
| 13 | `device_tasks` tăng thêm | **500.000 dòng/năm** (550.000 kèm rollback) | 10 campaign × 50.000 |
| 14 | `audit_logs` tăng thêm | **2.500.000 dòng/năm** (~1,4 GB/năm) | 5 dòng audit / 1 `device_task` |
| 15 | Check-in/năm toàn hệ thống | **10,51 tỷ request/năm** (28,8 triệu/ngày) | 100.000 × 31.536.000 / 300 |
| 16 | Kịch bản ×10 (1.000.000 thiết bị) | **3.333 RPS trung bình · 15.000–30.000 RPS đỉnh · 200 Gbps nếu scale slot ×10** | xem mục G |

*(Mọi dòng trong bảng này được in lại nguyên văn bởi `capacity_calc.py` — xem Phụ lục 1.)*

> **Đọc kèm cảnh báo nhãn (điểm 1 sau review):** Q7 quy định `waveDeadline` **mặc định 24 h** → đúng nguyên văn Q7 thì tổng là **100 h**. Con số **8,00 h chỉ đạt được khi đổi hạn chót xuống 1 h** — đây là **đề xuất của D**, *khác mặc định của nhóm*, và **phải được cả nhóm + campaign owner chốt** trước khi đưa lên slide. Slide không được ghi "thực tế 8 h" mà không nói rõ giả định này.

---

## A. CHECK-IN: RPS TRUNG BÌNH, CAO ĐIỂM & ĐỀ XUẤT GIẢM TẢI

### A.1 Công thức

```text
RPS_trung_bình   = FLEET / T_checkin
RPS_cao_điểm     ≈ (p_herd × FLEET) / T_herd
RPS_sau_jitter   ≈ RPS_trung_bình + (p_herd × FLEET) / T_checkin
Số_instance      = ceil(RPS_cao_điểm / RPS_instance)
```

### A.2 Giả định

- `FLEET = 100.000`, `T_checkin = 300 s` (đề bài: "mỗi thiết bị báo danh 5 phút một lần").
- **Thundering herd:** một sự cố mất điện / mạng ISP phục hồi làm **30% fleet (30.000 máy)** online lại cùng lúc, dàn trong **10–20 s** → cận dưới 1.500 RPS, cận trên 3.000 RPS.
- Kích thước 1 lượt check-in (request + response) ≈ **1 KB**; mỗi instance ingestion chịu được **~1.000 RPS** (giả định, cần benchmark thực tế); HMAC-SHA256 ~0,2 ms/lượt, TLS full handshake ~2 ms/lượt.

### A.3 Kết quả

| Đại lượng | Kết quả |
| :--- | :--- |
| RPS trung bình | **333,33 RPS** |
| RPS cao điểm (herd, không chống đỡ) | **1.500 RPS** (dàn 20 s) – **3.000 RPS** (dàn 10 s) |
| Hệ số cao điểm | **4,5× – 9,0×** RPS trung bình |
| Cao điểm phụ khi mở wave 4 (25.000 máy check-in trong 1 chu kỳ) | **+83,33 RPS** → nhỏ, không phải điểm nghẽn |
| Băng thông API check-in | trung bình **2,7 Mbps**, cao điểm **24,0 Mbps** |
| Nếu dàn herd bằng jitter trên 1 chu kỳ 300 s | +100 RPS → cao điểm còn **~433 RPS** (giảm **6,9×**) |
| Số instance ingestion | cần **3**, cấp **5** instance (dư N+2) |
| CPU nếu không tối ưu | HMAC **0,60 core**; TLS full handshake **6,00 core** |

### A.4 Đề xuất giảm tải

1. **Lệch pha cố định theo `serialNo` (mạnh hơn jitter ±30 s):** đặt `offset = hash(serialNo) mod 300` giây, ghép vào giờ check-in. Jitter ±30 s của thiết kế hiện tại chỉ dàn được tối đa ±60 s → **không đủ** cho herd 30.000 máy; lệch pha theo serial dàn đều cả 300 s nên triệt tiêu hiện tượng đồng pha vĩnh viễn.
2. **Full-jitter + exponential backoff khi lỗi mạng:** `delay = random(0, min(300 s, 1 s × 2^n))`. Herd 30.000 máy dàn trên 5 phút → chỉ còn +100 RPS thay vì 3.000 RPS.
3. **Rate limit 2 lớp:** token bucket theo `deviceId` (chống 1 máy spam) và theo **nhóm ISP** (chống cả vùng đồng loạt). Ingress trả `429`/`503` kèm header `Retry-After`; thiết bị bắt buộc backoff **kèm jitter**.
4. **Tuyệt đối không ghi DB trên đường check-in:** trả task từ Redis (`deviceId → taskId`), chỉ cập nhật `lastCheckInAt` vào Redis rồi **batch flush 30–60 s** xuống DB (xem mục F).
5. **Ingestion service stateless + autoscale:** không session, đặt sau Load Balancer; bật keep-alive/HTTP2 + TLS session resumption để tránh 6 core chỉ cho bắt tay TLS.
6. **Ưu tiên thiết bị đang trong wave:** khi đang có campaign chạy, response check-in của thiết bị có task `PENDING` phải được xử lý trước (partition queue theo `campaignId`) để không làm chậm tiến độ wave.

### A.5 Kết luận (1 câu)

**333 RPS trung bình là nhẹ, nhưng 1.500–3.000 RPS lúc thundering herd mới là rủi ro thật — phải xử lý bằng lệch pha theo `serialNo` + full-jitter backoff + ingestion stateless autoscale chứ không thể "thêm máy chủ" đơn thuần.**

---

## B. DỮ LIỆU CỦA TỪNG WAVE (CỘNG DỒN 10% VS ĐỢT RIÊNG WAVE 2)

### B.1 Công thức

```text
Cỡ mốc cộng dồn : N_k = TARGET × rolloutPercentage_k / 100          (Q1: 1% → 10% → 50% → 100%)
Cỡ đợt riêng    : n_k = N_k − N_{k−1}                              (wave 1 = 1%; wave 2 = 9%; …)
Dung lượng đợt  : V_k = n_k × 50 MB                                 (GB = MB / 1.000)
Tổng campaign   : V = TARGET × 50 MB
```

### B.2 Giả định

- `TARGET = 50.000` thiết bị (campaign lớn nhất theo đề bài: 10.000–50.000 máy).
- Mỗi thiết bị tải **đủ 50 MB** một lần (chưa tính retry, chưa tính nén/delta update).
- 1 GB = 1.000 MB (thập phân) — nếu dùng GiB thì nhỏ hơn ~7%.

### B.3 Kết quả

**Theo mốc cộng dồn (Q1):**

| Mốc cộng dồn | Số máy | Dung lượng | Thời gian tải @ 2,5 GB/s |
| :--- | ---: | ---: | ---: |
| Wave 1 — 1% | 500 | **25 GB** | 10,00 s |
| Wave 2 — 10% | **5.000** | **250 GB** | 100,00 s |
| Wave 3 — 50% | 25.000 | 1.250 GB | 500,00 s |
| Wave 4 — 100% | 50.000 | **2.500 GB = 2,5 TB** | 1.000,00 s |

**Theo đợt riêng (kích thước thực sự phải đẩy trong từng wave):**

| Đợt riêng | Số máy | Dung lượng | Thời gian tải @ 2,5 GB/s |
| :--- | ---: | ---: | ---: |
| Wave 1 (1%) | 500 | 25 GB | 10,00 s |
| Wave 2 (9%) | **4.500** | **225 GB** | 90,00 s |
| Wave 3 (40%) | 20.000 | 1.000 GB | 400,00 s |
| Wave 4 (50%) | 25.000 | 1.250 GB | 500,00 s |

**Phân biệt rõ hai con số hay bị nhầm:**

- **Mốc 10% cộng dồn = 5.000 máy = 250 GB** (đây là con số "lượng dữ liệu một đợt 10%" mà đề bài yêu cầu).
- **Đợt riêng wave 2 = 9% = 4.500 máy = 225 GB** (đây mới là lượng dữ liệu **thực sự phát sinh thêm** khi mở wave 2).
- Chênh lệch = **500 máy của wave 1 = 25 GB** — phần đã tải ở wave 1, không tải lại.

**Tổng hợp:** cả campaign = **2.500 GB = 2,5 TB**; cộng retry trung bình ×1,2 → **3,0 TB/campaign**; 10 campaign/năm → **30 TB/năm lưu lượng edge (CDN)**.

### B.4 Kết luận (1 câu)

**Slide 10 phải ghi rõ "10% cộng dồn = 250 GB (5.000 máy)" và "đợt riêng wave 2 = 225 GB (4.500 máy)"; dùng lẫn hai con số này sẽ bị hội đồng bắt lỗi ngay vì Q1 quy định `rolloutPercentage` là cộng dồn.**

---

## C. BĂNG THÔNG ĐỈNH & VÌ SAO BẮT BUỘC CDN

### C.1 Công thức

```text
B_đỉnh (byte) = maxConcurrentDevices × tốc_độ_tải_mỗi_máy
B_đỉnh (bit)  = B_đỉnh (byte) × 8
B_không_giới_hạn = TARGET × tốc_độ_tải_mỗi_máy × 8
Egress_origin_khi_có_CDN = FW_MB × số_PoP
```

### C.2 Giả định

- `maxConcurrentDevices = 500` slot tải; mỗi máy tải **5 MB/s** (≈ 40 Mbps, giả định đường truyền hộ gia đình thực nhận — không phải tốc độ tối đa của gói cước).
- Slot **chỉ được giữ trong lúc `DOWNLOADING`** và **trả khi thiết bị báo `INSTALLING`** (Q6) — đây là giả định then chốt để tính đúng mục D.
- CDN có **~50 PoP** (giả định); mỗi phiên bản firmware chỉ là **1 object 50 MB** nên cache hit gần 100%.

### C.3 Kết quả

| Đại lượng | Kết quả |
| :--- | :--- |
| Băng thông đỉnh | **500 × 5 MB/s = 2.500 MB/s = 2,5 GB/s = 2,44 GiB/s = 20 Gbps** |
| Nếu **không** giới hạn slot | 50.000 × 40 Mbps = **2.000 Gbps = 2 Tbps** (**100×** băng thông đỉnh) |
| Thời gian đẩy toàn bộ 2.500 GB ở 2,5 GB/s | **16,67 phút** |
| Egress origin **khi có CDN 50 PoP** | 50 × 50 MB = **2,5 GB**/phiên bản (thay vì 2.500 GB ra edge) → giảm **~1.000×** |
| Băng thông check-in cao điểm so với 20 Gbps | 24 Mbps = **0,12%** |

### C.4 Vì sao bắt buộc CDN (lập luận, không phải khẩu hiệu)

1. **20 Gbps duy trì liên tục trong 8–17 phút** là con số vượt egress của một vùng Object Storage đơn lẻ / một đường transit thông thường; nếu backend tự phát file thì API Gateway và ingress check-in cùng chết theo.
2. **Object firmware 50 MB là "cache vàng":** 50.000 thiết bị ở 30 khách hàng ISP khác nhau tải **cùng một object** → PoP chỉ cần 1 lần miss, các lần sau phục vụ tại chỗ. Origin chỉ phát **~2,5 GB** thay vì **2.500 GB**.
3. **Phân tán địa lý theo 30 ISP:** CDN đặt PoP gần mạng ISP giúp lưu lượng không phải đi vòng qua transit quốc tế, giảm cả độ trễ lẫn chi phí băng thông.
4. **Tách data path khỏi control path:** backend chỉ ký **pre-signed URL ngắn hạn (15–30 phút)**; toàn bộ byte firmware đi thẳng từ CDN → thiết bị. Nhờ vậy API check-in 333–3.000 RPS không bao giờ cạnh tranh băng thông với luồng tải firmware.

### C.5 Kết luận (1 câu)

**20 Gbps là con số quyết định của toàn bài: nó biến "tải firmware" thành bài toán hạ tầng phân phối nội dung, nên kiến trúc bắt buộc là Object Storage + CDN đa PoP + pre-signed URL, backend không bao giờ phát file.**

---

## D. THỜI GIAN HOÀN TẤT CAMPAIGN 50.000 THIẾT BỊ — TÍNH THEO TỪNG WAVE

### D.1 Công thức

```text
Năng lực tải          : D = maxConcurrentDevices × tốc_độ / kích_thước_file = 500 × 5 / 50 = 50 lượt tải/giây
Năng lực 1 chu kỳ     : C0 = D × T_checkin = 50 × 300 = 15.000 máy
Độ trễ khám phá       : T_khám_phá ≤ 1 chu kỳ check-in (300 s) + jitter
Tải xong cả đợt        : T_tải = max(T_khám_phá, n_k / D) + 10 s + (T_checkin nếu n_k > C0)
Thời gian phase        : T_phase = T_tải + T_cài/verify
Thời gian wave         : T_wave = max(T_phase, hạn_chót_wave) + soak_k     (chỉ chờ hạn chót khi còn thiết bị OFFLINE)
Tổng campaign          : T = Σ T_wave
```

- Số hạng **`T_checkin nếu n_k > C0`** (thay cho con số "+150 s" ở bản v1.0): khi số máy của wave vượt năng lực tải trong 1 chu kỳ check-in, phần dôi ra **bị từ chối slot** và phải chờ tới **vòng check-in kế tiếp** → cộng **1 chu kỳ = 300 s** cho máy cuối (cận trên). Đây là giả định có công thức, không phải số áng.
- Nếu server trả được `nextCheckInIn` (vd "thử lại sau 60 s") cho máy bị từ chối slot thì số hạng này còn ~60 s; cả hai trường hợp đều **không đổi kết luận** vì tổng thời gian bị soak + hạn chót chi phối.

### D.2 Giả định

- Cỡ đợt theo Q1: **500 / 4.500 / 20.000 / 25.000** máy.
- `maxConcurrentDevices = 500`; mỗi máy 5 MB/s → **50 lượt tải/giây**; file 50 MB → mỗi lượt giữ slot **10 s**.
- **Slot chỉ giữ lúc `DOWNLOADING` (Q6)** → cài/verify (≈ 3 phút thực tế; timeout Q9 = 10 phút cài + 5 phút verify) chạy **song song** giữa các máy và **không** chiếm slot.
- **Soak time 2 h sau wave 1 và wave 2** (Q2), wave 3–4 không soak (theo đúng câu chữ Q2). Lưu ý: tài liệu của C nhắc dải **"2–4 h"** → **2 h là cận dưới**; nếu nhóm chốt 4 h thì tổng +4 h (8,00 h → 12,00 h; 100 h → 104 h). **Cần chốt một con số với C.**
- **5% thiết bị OFFLINE** trong nhóm đích (giả định): task của chúng vẫn được tạo (Q7) nhưng phải chờ tới hạn chót wave mới đóng được.
- Hạn chót: **mặc định 24 h** (Q7 gọi là `waveDeadline`, lưu ở trường `campaign_waves.deadlineAt`). Tài liệu này **đề xuất 1 h** để cắt straggler khỏi critical path — **đây là thay đổi so với mặc định Q7, cần cả nhóm chốt** (không được gọi là "tuân thủ Q7"). Cấu hình wave nằm ở `campaign_waves`: `rolloutPercentage` (cộng dồn — Q1), `minSuccessRateToProceed` = 95% (Q2), `deadlineAt` (Q7).
- Retry tối đa 3 lần, backoff 1 → 5 → 15 phút (Q9); `ROLLED_BACK` không retry.

> **Cần chốt với B và C trước khi lên slide (điểm 4 sau review):**
> (1) **B** — xác nhận slot chỉ giữ lúc `DOWNLOADING` và trả khi thiết bị báo `INSTALLING` (Q6), vì mô hình thời gian ở mục D phụ thuộc trực tiếp vào điều này; xác nhận timeout Q9 15'/10'/5' và backoff 1 → 5 → 15 phút.
> (2) **C** — xác nhận cách semaphore `sem:campaign:{id}` cấp/thu hồi slot và **chốt soak 2 h hay 4 h**; tài liệu này lấy cận dưới 2 h.
> Kết quả review phải được ghi lại (ngày + người xác nhận) trước khi chốt con số trên slide 10.

### D.3 Kết quả — bảng theo từng wave (kịch bản thực tế dùng hạn chót 1 h — ĐỀ XUẤT, khác mặc định Q7)

| Wave | Cỡ đợt | Khám phá (check-in) | Tải xong đợt | Cài/verify | Phase | Chờ hạn chót 1 h | Soak | Wall-clock wave | Cộng dồn |
| :-: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 (1%) | 500 | 330 s | 340 s | 180 s | 8,7 phút | 51,3 phút | 2 h | 1,00 h | **3,00 h** |
| 2 (9%) | 4.500 | 330 s | 340 s | 180 s | 8,7 phút | 51,3 phút | 2 h | 1,00 h | **6,00 h** |
| 3 (40%) | 20.000 | 330 s | 710 s | 180 s | 14,8 phút | 45,2 phút | 0 | 1,00 h | **7,00 h** |
| 4 (50%) | 25.000 | 330 s | 810 s | 180 s | 16,5 phút | 43,5 phút | 0 | 1,00 h | **8,00 h** |

Giải thích các cột:

- **Khám phá:** thiết bị chỉ biết có việc ở lần check-in kế tiếp → tối đa 1 chu kỳ 300 s (+ jitter) mới tới được máy cuối.
- **Tải xong đợt:** `max(330 s, n/50) + 10 s + (300 s nếu n > C0)`, với `C0 = D × T_checkin = 15.000` máy. Wave 1–2 (n = 500 / 4.500 ≤ C0): không máy nào bị từ chối slot → 340 s. Wave 3–4 (n = 20.000 / 25.000 > C0): tải 400/500 s **cộng 300 s** chờ vòng check-in kế tiếp cho phần máy bị từ chối slot → 710/810 s.
- **Cài/verify:** 180 s thực tế (không giữ slot).
- **Chờ hạn chót:** vì còn 5% thiết bị OFFLINE chưa terminal, wave chỉ `COMPLETED` khi hết hạn chót (Q7) → phần này **nuốt trọn** thời gian phase.
- **Wall-clock wave:** 1,00 h (do chờ hạn chót) + soak.

### D.4 Khoảng "tốt nhất – thực tế – xấu nhất"

| Kịch bản | Thời gian thực thi (tải + cài, 4 wave) | **Tổng campaign** |
| :--- | ---: | ---: |
| **Tốt nhất** — lý thuyết (lower bound): 0% OFFLINE, điều phối hoàn hảo, cài nhanh (60 s) | 29,7 phút | **4,49 h** (4 h soak chiếm 89%) |
| **Thực tế** — chỉ chọn thiết bị ONLINE (không có straggler) | 48,7 phút | **4,81 h** |
| **Thực tế (ĐỀ XUẤT của D)** — 5% OFFLINE, **đổi hạn chót wave xuống 1 h** (khác mặc định Q7) | 48,7 phút | **8,00 h** |
| **Thực tế + tối ưu** — promotion ở 95%, straggler chạy song song | 48,7 phút | **5,81 h** |
| **Đúng mặc định Q7** — `waveDeadline` 24 h (kịch bản literal của Q7) | 100,7 phút | **100,00 h (≈ 4,2 ngày)** |

> **Nhãn quan trọng (điểm 1 sau review):** "**Đúng mặc định Q7**" mới là kịch bản vận hành thật nếu nhóm không đổi cấu hình. Các con số **4,81 h / 5,81 h / 8,00 h đều là kịch bản CÓ ĐIỀU CHỈNH chính sách** (chỉ chọn máy ONLINE / promotion sớm / đổi hạn chót xuống 1 h) — không được gọi là "tuân thủ Q7". Trên slide chỉ nêu "8 h" kèm chú thích "nếu chốt hạn chót wave 1 h (đề xuất, khác mặc định 24 h)".

**Thành phần nào chi phối tổng thời gian?**

- Trong kịch bản thực tế **đề xuất 1 h** (8,00 h): **soak 4 h = 50%** + **chờ hạn chót straggler 4 h = 50%**; phần tải + cài thực tế (48,7 phút) **nằm lọt bên trong** thời gian chờ nên gần như không cộng thêm.
- Nếu **giữ đúng mặc định Q7 24 h** (100,00 h): **96 h chờ hạn chót = 96%** tổng thời gian — đây chính là lý do phải chốt lại hạn chót thay vì "để mặc định".
- Vì vậy **băng thông 20 Gbps và 500 slot KHÔNG phải yếu tố quyết định thời gian campaign** — yếu tố quyết định là **soak time** và **chính sách hạn chót cho thiết bị OFFLINE**.
- Hệ quả thiết kế: (1) chỉ đưa thiết bị **ONLINE** vào wave, thiết bị OFFLINE tách campaign riêng → 4,81 h; (2) cho phép **promotion khi đạt `minSuccessRateToProceed` 95%** thay vì chờ 100% task terminal → 5,81 h; (3) đặt hạn chót wave **1 h** thay vì 24 h → 8,00 h.

### D.5 Đối chiếu con số "~2–3 giờ cho 50.000 máy" trong Specification §4

Specification §4 viết:

> *"Giả định đặt `maxConcurrentDevices = 500`. Băng thông tải trung bình 5 MB/s (10s tải + ~3 phút cài/reboot/verify = ~3,2 phút/thiết bị). (…) **~2–3 giờ** cho phần tải & cài 50.000 máy (tổng thời gian chiến dịch gồm Soak Time: **~6–8 giờ**)."*

**Kết quả kiểm chứng:**

| Cách tính | Kết quả |
| :--- | ---: |
| (a) Tải thuần theo Q6 (slot chỉ giữ lúc `DOWNLOADING`) | 2.500 GB / 2,5 GB/s = **16,67 phút** |
| (b) Nếu slot bị giữ suốt 3,2 phút/thiết bị (mâu thuẫn Q6) | 50.000 / 500 × 3,2 phút = **320 phút = 5,33 h** |
| (c) Mô hình của tài liệu này (tải + cài, 4 wave) | **29,7 – 100,7 phút** (thực tế 48,7 phút) |
| (d) Tổng campaign theo mô hình | **4,49 – 8,00 h** với chính sách điều chỉnh; **100 h** nếu giữ đúng mặc định Q7 24 h |

**Đối chiếu (viết theo hướng "ước tính đã hiệu chỉnh", không phán xử "SAI"):**

- **Phần tải + cài:** theo Q6, cả 4 wave chỉ mất **~49 phút** (thực tế) / 16,67 phút nếu chỉ tính byte (tải thuần). Ước tính **2–3 giờ** trong §4 chỉ tái lập được khi **slot bị giữ suốt 3,2 phút/thiết bị** (ra 5,33 h) — tức là **trộn với một giả định khác Q6** (Q6 quy định trả slot khi thiết bị báo `INSTALLING`).
- **Phần tổng campaign:** ước tính **2–3 giờ** bỏ qua **soak 4 h** và **thời gian chờ thiết bị OFFLINE**; ước tính đã hiệu chỉnh là **4,81 h – 8,00 h** (có chính sách điều chỉnh) hoặc **100 h** (giữ mặc định Q7).
- **"~6–8 giờ" của §4** trùng bậc độ lớn với **8,00 h** của kịch bản đề xuất 1 h và **5,81 h** của kịch bản tối ưu — có thể giữ câu này, chỉ cần ghi rõ điều kiện hạn chót.
- **Việc cần làm (không sửa trong tài liệu này):** cập nhật **Specification §4** để hai tài liệu khớp nhau — thay "~2–3 giờ" bằng "**~49 phút tải + cài / 4,5–8 h tổng, tùy hạn chót wave**" (việc của người giữ spec: C/người phụ trách spec). Slide 10 dùng cụm **"ước tính đã hiệu chỉnh so với bản trước"**, không nói "spec sai".

### D.6 Kết luận (1 câu)

**Thời gian campaign bị chi phối bởi soak time và hạn chót thiết bị OFFLINE chứ không phải băng thông; ước tính đã hiệu chỉnh là 4,81–8,00 h nếu nhóm chốt chính sách (chọn máy ONLINE / promotion 95% / hạn chót wave 1 h), còn giữ đúng mặc định Q7 24 h thì tổng là 100 h — vì vậy "~2–3 giờ" trong Specification §4 cần được cập nhật lại.**

---

## E. TĂNG TRƯỞNG `device_tasks` VÀ `audit_logs` MỖI NĂM

### E.1 Công thức

```text
device_tasks/năm = campaigns/năm × thiết_bị/campaign
audit_logs/năm   = device_tasks/năm × số_dòng_audit_mỗi_task
Dung lượng/năm   = số_dòng × kích_thước_dòng
Check-in/năm     = FLEET × (365 × 24 × 3600) / T_checkin
```

### E.2 Giả định

- **10 campaign/năm**, mỗi campaign **50.000** thiết bị.
- **Retry không tạo dòng mới:** `attemptCount` tăng trên cùng một `device_tasks` (đúng thiết kế A) → 1 thiết bị/campaign = 1 dòng.
- **+10% khối lượng cho campaign rollback hàng loạt** (Bonus #13 của D; giả định 1 campaign rollback cho mỗi 10 campaign triển khai).
- **5 dòng `audit_logs` trên mỗi `device_task`:** PENDING → DOWNLOADING → INSTALLING → VERIFYING → SUCCESS/terminal. **Không audit heartbeat** (heartbeat chỉ cập nhật `lastHeartbeatAt` theo Q5); nếu audit cả heartbeat sẽ thành **10,5 tỷ dòng/năm** — không thể chấp nhận.
- Kích thước dòng (giả định): `device_tasks` ≈ **0,5 KB**, `audit_logs` ≈ **0,4 KB**.

### E.3 Kết quả

| Hạng mục | Công thức | Kết quả |
| :--- | :--- | ---: |
| `device_tasks`/năm | 10 × 50.000 | **500.000 dòng** |
| + campaign rollback | × 1,10 | **550.000 dòng/năm** |
| `audit_logs`/năm | 500.000 × 5 | **2.500.000 dòng** |
| + rollback | 550.000 × 5 | **2.750.000 dòng/năm** |
| Dung lượng `device_tasks` | 550.000 × 0,5 KB | **275 MB/năm** |
| Dung lượng `audit_logs` | 2.750.000 × 0,4 KB | **1.100 MB/năm** |
| **Tổng dung lượng tăng** | | **1.375 MB = 1,375 GB ≈ 1,4 GB/năm** (5 năm ≈ 6,88 GB) |
| `device_firmware_histories`/năm | 1 dòng/task SUCCESS | **500.000 dòng** |
| Check-in/năm | 100.000 × 31.536.000 / 300 | **10,51 tỷ request** (28,8 triệu/ngày) |
| Audit đỉnh khi tải | 50 task/s × 5 | **250 dòng/s** (bé) |

### E.4 Kết luận (1 câu)

**Dung lượng tăng thêm (~1,4 GB/năm) không phải vấn đề, nhưng 2,5 triệu dòng `audit_logs`/năm và 10,5 tỷ lượt check-in/năm buộc phải partition theo thời gian + ghi audit bất đồng bộ, và tuyệt đối không được đưa heartbeat vào `audit_logs`.**

---

## F. ĐIỂM NGHẼN & GIẢI PHÁP

| # | Điểm nghẽn | Số liệu chốt | Vì sao gãy | Giải pháp |
| :-: | :--- | :--- | :--- | :--- |
| 1 | **Egress firmware** | 20 Gbps đỉnh; 2.500 GB/campaign; 30 TB/năm ở edge | Vượt egress 1 vùng storage/1 đường transit; làm nghẽn cả ingress nếu đi qua backend | Pre-signed URL + **CDN 50 PoP**, giới hạn `maxConcurrentDevices`, cache object 50 MB |
| 2 | **Origin storage** | Không CDN phải phát 2.500 GB/campaign từ 1 vùng | Băng thông + chi phí + single point | CDN giảm egress origin **~1.000×** (50 PoP × 50 MB ≈ 2,5 GB) |
| 3 | **Burst check-in** | 333 RPS TB; **3.000 RPS** đỉnh (4,5–9×) | Đồng pha sau sự cố → nghẽn TLS/ingress, DB | Lệch pha theo `serialNo` + full-jitter backoff + rate limit theo ISP + autoscale stateless |
| 4 | **Ghi DB đường check-in** | 3.000 UPDATE/s (đỉnh) nếu ghi trực tiếp `lastCheckInAt` | Write amplification + lock + audit | Redis giữ `lastCheckInAt`, **batch flush 30–60 s**, PgBouncer, không audit heartbeat |
| 5 | **Redis semaphore** | 500 token/campaign; cấp/thu hồi ~50 lần/s khi bão hòa | Hot key + slot "rò" khi thiết bị im lặng | Lua script nguyên tử, key theo campaign, TTL + worker thu hồi slot sau timeout tải (Q9) |
| 6 | **Scan timeout của worker** | 30 s/lần; wave 4 có tới **~25.000 task chưa terminal** | Full scan bảng lớn | Partial index `(status, lastHeartbeatAt)`, partition theo `campaignId`/tháng |
| 7 | **Dashboard/aggregate** | 500.000 task + 2,5 triệu audit/năm | Aggregate trực tiếp trên bảng lớn làm chậm DB | Counter trong Redis, dashboard đọc bản tổng hợp, partition + cold storage |

**Những thứ KHÔNG phải điểm nghẽn (cần nói rõ để tránh "phòng bệnh không có bệnh"):**

- Băng thông / CPU của API check-in: cao điểm chỉ **24 Mbps**, ~0,12% của 20 Gbps.
- Ghi `device_tasks` và `audit_logs`: đỉnh chỉ **250 dòng/s** khi tải — quá nhỏ so với sức chịu của PostgreSQL.
- Do đó thứ tự nghẽn thực tế là: **(1) egress/CDN ≫ (2) burst check-in > (3) đường ghi DB check-in**; hai hạng mục sau chỉ gãy nếu thiết kế ghi DB đồng bộ trên mỗi check-in.

**Kết luận (1 câu):** Điểm nghẽn số 1 là **20 Gbps egress và dung lượng 2,5 TB/campaign** — chỉ CDN + slot tải mới giải quyết được, còn "thêm máy chủ" không làm tăng băng thông file.

---

## G. KỊCH BẢN 1.000.000 THIẾT BỊ (×10)

### G.1 Số liệu quy mô mới

| Chỉ số | 100.000 thiết bị | **1.000.000 thiết bị (×10)** |
| :--- | ---: | ---: |
| Check-in trung bình | 333,33 RPS | **3.333,33 RPS** |
| Check-in cao điểm (herd 30%) | 1.500–3.000 RPS | **15.000–30.000 RPS** |
| Campaign lớn nhất | 50.000 máy | **500.000 máy** |
| Cỡ đợt (1/9/40/50%) | 500 / 4.500 / 20.000 / 25.000 | **5.000 / 45.000 / 200.000 / 250.000** |
| Dữ liệu/campaign | 2,5 TB | **25 TB** (30 TB kèm retry) |
| Lưu lượng edge/năm | 30 TB | **300 TB** |
| Egress đỉnh nếu scale slot ×10 | 20 Gbps | **200 Gbps** (5.000 slot × 5 MB/s) |
| `device_tasks`/năm | 500.000 | **5.000.000** |
| `audit_logs`/năm | 2.500.000 | **25.000.000** |
| Check-in/năm | 10,51 tỷ | **105,12 tỷ** |

### G.2 Cái gì gãy đầu tiên & sửa thế nào

| Thứ tự gãy | Thành phần | Vì sao gãy ở ×10 | Cách sửa |
| :-: | :--- | :--- | :--- |
| **1** | **Egress/CDN một vùng** | 200 Gbps + 25 TB/campaign vượt năng lực 1 vùng CDN/origin | **CDN đa vùng theo ISP**; chia **ngân sách slot theo vùng** (VD 2.000 slot × 10 vùng thay vì 20.000 slot toàn cầu); pre-signed URL trỏ PoP gần nhất |
| **2** | **Burst check-in** | 15.000–30.000 RPS + 105 tỷ request/năm → nghẽn ingestion & TLS | Stateless ingestion **scale ngang** sau LB; **Kafka/queue** đệm check-in; rate limit theo ISP; jitter toàn cục |
| **3** | **Đường ghi DB** | 30.000 UPDATE/s nếu ghi đồng bộ mỗi check-in | Gom batch vào Redis rồi flush; sharding ghi theo vùng; tách DB đọc/ghi |
| **4** | **Redis (semaphore + counter)** | 5.000 token, hàng chục nghìn thao tác/s, hot key | **Redis Cluster** shard theo `campaignId`/vùng; token bucket cục bộ theo instance; Lua nguyên tử |
| **5** | **Bảng lớn & dashboard** | 5 triệu `device_tasks` + 25 triệu `audit_logs`/năm | **Partition theo tháng** + cold storage; sharding theo `campaignId`; counter tổng hợp sẵn |
| **6** | **Scheduler quét wave** | Wave 250.000 task, quét timeout 30 s | Queue-driven (mỗi task có delayed message), partial index, worker shard theo wave |

**Lưu ý quan trọng:** giữ nguyên `maxConcurrentDevices = 500` thì egress vẫn 20 Gbps nhưng **thời gian campaign tăng tuyến tính**: riêng wave 4 = 250.000 / 50 = **5.000 s = 83,3 phút**, cả campaign tải hết **166,7 phút**. Vì vậy ở quy mô ×10 phải **scale số slot theo ngân sách băng thông từng vùng** (đánh đổi: egress ↑, thời gian ↓), không thể vừa giữ 500 slot vừa giữ SLA thời gian.

### G.3 Kết luận (1 câu)

**×10 là bài toán phân tán hạ tầng (CDN đa vùng + queue + partition + Redis Cluster), không phải bài toán thêm CPU; thứ gãy đầu tiên luôn là egress 200 Gbps và burst 30.000 RPS, không phải database.**

---

## H. GIẢ ĐỊNH BỔ SUNG (mọi giả định không có trong đề đều nằm ở đây)

| # | Giả định | Giá trị dùng | Lý do / ảnh hưởng |
| :-: | :--- | :--- | :--- |
| H1 | Quy ước đơn vị | 1 MB = 10⁶ B; 1 GB = 1.000 MB; 1 TB = 1.000 GB | Tránh nhầm với GiB (nhỏ hơn ~7%) |
| H2 | Tốc độ tải thực nhận mỗi thiết bị | **5 MB/s** (≈ 40 Mbps) | Specification §4 giả định "băng thông tải trung bình 5 MB/s"; đây là tốc độ *thực nhận*, không phải tốc độ gói cước |
| H3 | Kích thước 1 lượt check-in | **1 KB** (0,4 KB request + 0,6 KB response) | Dùng để tính tải API; nếu response có task thì lớn hơn (~1,5 KB) nhưng vẫn không đáng kể |
| H4 | Năng lực 1 instance ingestion | **1.000 RPS/instance** | Giả định để tính số instance; **không phải benchmark thực tế** — phải đo lại khi triển khai |
| H5 | Chi phí CPU mã hoá | HMAC 0,2 ms/lượt; TLS full handshake 2 ms/lượt | Giả định thô để so sánh; TLS thực tế phụ thuộc thuật toán/CPU |
| H6 | Thundering herd | **30% fleet** online lại trong **10–20 s** | Khớp dải 1.500–3.000 RPS mà Specification §4 đưa ra; là kịch bản sự cố diện rộng |
| H7 | Thời gian cài + reboot + verify thực tế | **180 s** (3 phút) | Lấy theo giả định "~3 phút/thiết bị" của Specification §4; timeout Q9 (10 ph + 5 ph) chỉ dùng cho kịch bản xấu |
| H8 | Tỷ lệ thiết bị OFFLINE trong nhóm đích | **5%** | Thực tế vận hành ISP; ảnh hưởng quyết định tới tổng thời gian (xem H9) |
| H9 | Hạn chót wave (`waveDeadline`) | **24 h mặc định (Q7)**; tài liệu **đề xuất 1 h** | 1 h là **thay đổi chính sách so với mặc định Q7, cần nhóm chốt**; đây là giả định nhạy nhất: 1 h → 8,00 h, 24 h → 100,00 h |
| H10 | Soak time | **2 h sau wave 1 và wave 2**; wave 3–4 không soak | Câu chữ Q2 ghi ≥ 2 h cho wave 1, 2; tài liệu của C nhắc dải "2–4 h" → **2 h là cận dưới, cần chốt với C**; nếu 4 h thì tổng +4 h (8,00 → 12,00 h; 100 → 104 h) |
| H11 | Retry | Tối đa **3** lần, backoff **1 → 5 → 15 phút**, `ROLLED_BACK` không retry; hệ số lưu lượng **×1,2** | Theo Q9; chỉ dùng để tính egress/năm và kịch bản xấu |
| H12 | Retry không tạo dòng mới | `attemptCount` tăng trên cùng `device_tasks` | Giả định thiết kế (A); nếu mỗi attempt tạo dòng mới thì bảng phình ×3 |
| H13 | Audit | **5 dòng `audit_logs`/`device_task`**; **không** audit heartbeat | Đúng yêu cầu #7 (ai, làm gì, khi nào); heartbeat theo Q5 chỉ cập nhật `lastHeartbeatAt` |
| H14 | Kích thước dòng | `device_tasks` 0,5 KB; `audit_logs` 0,4 KB | Giả định để tính dung lượng; chỉ ảnh hưởng bảng "dung lượng/năm" |
| H15 | Khối lượng rollback | **+10%** (1 campaign rollback cho mỗi 10 campaign) | Bonus #13 của D; là cận trên thận trọng |
| H16 | Số PoP CDN | **~50 PoP** | Để tính egress origin; thực tế phụ thuộc nhà cung cấp CDN |
| H17 | Wave chạy tuần tự, không chồng campaign | Không có 2 campaign cùng chạy trên 1 thiết bị; peak các campaign không cộng dồn | Đúng ràng buộc concurrency #9; nếu campaign chồng nhau thì cộng peak |
| H18 | File firmware không nén / không delta-update | Mỗi máy tải đủ **50 MB** | Nếu dùng delta update thì dung lượng giảm mạnh — đây là hướng tối ưu tiềm năng |
| H19 | Chỉ số 95% (`minSuccessRateToProceed`) không được mô hình hoá vào thời gian | Chỉ dùng làm cổng chuyển wave; nếu wave fail → `PAUSED` thì thời gian **không xác định** (không tính) | Q2/Q3; kịch bản auto-pause không nằm trong ước lượng thời gian |
| H20 | Kịch bản ×10 | Fleet ×10, campaign ×10 (500.000 máy), **slot tải hoặc giữ 500, hoặc scale ×10** | Đề bài không nói slot ở quy mô mới → trình bày cả hai để thấy đánh đổi egress ↔ thời gian |
| H21 | Kịch bản "tốt nhất" | Giả định **điều phối hoàn hảo** (không máy nào bị từ chối slot) | Chỉ là **lower bound lý thuyết**; với check-in ngẫu nhiên, wave 3–4 luôn có máy bị từ chối slot (xem `C0` ở D.1) |
| H22 | Mô hình thời gian **chưa được B và C review** | Tài liệu v1.1 chưa có xác nhận của B (Q6 / timeout) và C (semaphore / soak) | **Bắt buộc review trước khi chốt slide 10**; nếu B/C xác nhận khác thì phải tính lại mục D (xem ghi chú cuối D.2) |

**Độ nhạy (giả định nào làm kết quả đổi mạnh nhất):**

1. **H8 + H9 (OFFLINE % và hạn chót wave):** đổi từ 5%/1 h sang 5%/24 h làm tổng thời gian từ **8,00 h → 100,00 h**. Đây là giả định *quan trọng nhất* — phải nói rõ trên slide.
2. **H7 (thời gian cài):** 3 phút → timeout Q9 (15 phút) làm phase 4 wave từ 48,7 phút lên 100,7 phút, nhưng vẫn nhỏ so với soak.
3. **H10 (soak):** soak là 50% tổng thời gian của kịch bản 8,00 h; nếu chốt 4 h thì 8,00 h → 12,00 h và 100 h → 104 h; giảm soak thì giảm thời gian tuyến tính nhưng tăng rủi ro firmware lỗi.
4. **H2 (5 MB/s):** giảm còn 2 MB/s làm băng thông đỉnh còn 8 Gbps nhưng số lượt tải/giây còn 20 → tải lâu hơn gấp 2,5 lần.

---

## PHỤ LỤC 1 — OUTPUT CỦA `capacity_calc.py` (kiểm chứng)

Cách chạy:

```bash
python docs/member-d/capacity_calc.py
```

Kết quả in ra (nguyên văn, đã dán tự động từ lần chạy cuối):

```text
====================================================================================================
A. CHECK-IN: RPS TRUNG BÌNH, CAO ĐIỂM (THUNDERING HERD) & TẢI API
====================================================================================================
  Công thức : RPS_tb = FLEET / chu_kỳ = 100.000 / 300
  Kết quả   : RPS trung bình = 333,33 RPS
  Cao điểm  : giả định 30% fleet (30 000 máy) online lại cùng lúc sau sự cố mất điện/mạng:
              - dàn trong 20 s -> 1.500 RPS
              - dàn trong 10 s -> 3.000 RPS
  Hệ số     : 4,5x - 9,0x RPS trung bình
  Cao điểm phụ khi mở wave 4 (25.000 máy): +83,33 RPS (nhỏ, không phải điểm nghẽn)
  Tải API check-in (giả định 1,0 KB/lượt): trung bình 2,7 Mbps; cao điểm 24,0 Mbps
  Jitter    : dàn herd 30.000 máy trên 1 chu kỳ 300 s -> +100,00 RPS
              => cao điểm còn ~433,33 RPS, giảm 6,9x so với 3.000 RPS
              (jitter ±30 s theo Q thiết kế chỉ dàn được ±60 s; cần full-jitter/backoff khi lỗi)
  Instance  : giả định 1.000 RPS/instance -> cần 3 instance, cấp 5 (dư N+2)
  CPU       : HMAC-SHA256 ~0,2 ms/lượt -> 0,60 core; TLS full handshake ~2 ms/lượt -> 6,00 core
              => ưu tiên keep-alive/session resumption thay vì bắt tay TLS mỗi check-in

====================================================================================================
B. DỮ LIỆU CỦA TỪNG WAVE — CỘNG DỒN 1/10/50/100 % (QUY ƯỚC Q1)
====================================================================================================
  Công thức: dung lượng = số_máy x 50 MB; 1 GB = 1000 MB (thập phân)

  Mốc cộng dồn                  Số máy    Dung lượng    Thời gian tải đỉnh
  Wave 1 (1% cộng dồn)             500         25 GB               10,00 s
  Wave 2 (10% cộng dồn)          5.000        250 GB              100,00 s
  Wave 3 (50% cộng dồn)         25.000      1.250 GB              500,00 s
  Wave 4 (100% cộng dồn)        50.000      2.500 GB            1.000,00 s

  Đợt riêng (hiệu số)           Số máy    Dung lượng    Thời gian tải đỉnh
  Wave 1 (đợt riêng)               500         25 GB               10,00 s
  Wave 2 (đợt riêng)             4.500        225 GB               90,00 s
  Wave 3 (đợt riêng)            20.000      1.000 GB              400,00 s
  Wave 4 (đợt riêng)            25.000      1.250 GB              500,00 s

  PHÂN BIỆT: mốc 10% CỘNG DỒN = 5.000 máy = 250 GB
             đợt riêng wave 2 (9%) = 4.500 máy = 225 GB
             chênh lệch = 500 máy của wave 1 = 25 GB
  Tổng campaign 50 000 máy = 2.500 GB = 2,50 TB
  Cộng retry (x1,2) = 3,00 TB/campaign
  10 campaign/năm -> 30,00 TB/năm lưu lượng EDGE (CDN)

====================================================================================================
C. BĂNG THÔNG ĐỈNH & VÌ SAO BẮT BUỘC CDN
====================================================================================================
  Công thức : B_đỉnh = maxConcurrentDevices x tốc_độ_tải
            = 500 x 5,0 MB/s = 2.500 MB/s
  Kết quả   : 2,50 GB/s = 2,44 GiB/s = 20,00 Gbps
  1 thiết bị : 5,0 MB/s = 40,00 Mbps (giả định đường truyền hộ gia đình)
  KHÔNG giới hạn slot: 50.000 x 40,00 Mbps = 2.000 Gbps = 2,0 Tbps (100x băng thông đỉnh)
  Toàn campaign 50.000 máy = 2.500 GB; tại 2,50 GB/s -> 16,67 phút
  CDN 50 PoP : origin chỉ phát 50 bản x 50 MB = 2,50 GB (thay vì 2.500 GB ra edge)
              => giảm egress origin ~1.000x; hit ratio gần 100% vì mỗi version chỉ 1 object
  So sánh   : tải check-in cao điểm 24,0 Mbps = 0,12% của 20,00 Gbps
              => băng thông check-in KHÔNG đáng kể; toàn bộ áp lực nằm ở file firmware

====================================================================================================
D. THỜI GIAN HOÀN TẤT CAMPAIGN 50 000 THIẾT BỊ — TÍNH THEO TỪNG WAVE
====================================================================================================
  Năng lực tải : D = SLOTS x SPEED / FW = 500 x 5,0 / 50 = 50,00 lượt tải/giây
  Năng lực trong 1 chu kỳ check-in: C0 = D x T_checkin = 50,00 x 300 = 15.000 máy
  Công thức mỗi wave:
    T_tải_xong = max(T_khám_phá, N/D) + 10 s + (T_checkin nếu N > C0)
    T_phase    = T_tải_xong + T_cài/verify
    T_wave     = max(T_phase, hạn_chót_của_wave) + soak   (chỉ chờ hạn chót khi còn thiết bị OFFLINE)

  Giải thích số hạng '(T_checkin nếu N > C0)': mỗi máy chỉ check-in 1 lần/chu kỳ; nếu số máy của
  wave vượt C0 thì phần dôi ra bị từ chối slot và phải chờ tới vòng check-in KẾ TIẾP -> cộng 1 chu kỳ
  (300 s) cho máy cuối. Đây là CẬN TRÊN; nếu server trả 'thử lại sau 60 s' cho máy bị từ chối thì
  số hạng này còn ~60 s. Cả hai đều không đổi kết luận vì tổng thời gian bị soak/hạn chót chi phối.

  Giả định then chốt: slot CHỈ bị giữ lúc DOWNLOADING (Q6) -> cài/verify các máy chạy SONG SONG,
  không chiếm slot; vì vậy tải+cài nhanh hơn nhiều so với cảm giác '500 slot chia 50 000 máy'.
TỐT NHẤT — lý thuyết: 0% OFFLINE, điều phối hoàn hảo, cài nhanh
  Wave          N  Khám phá   Tải xong  Cài/verify  Phase(ph)   Chờ(ph)  Soak(h)  Wall(h)  Cộng dồn
  1           500     300 s      310 s        60 s        6,2       0,0      2,0     0,10      2,10
  2         4.500     300 s      310 s        60 s        6,2       0,0      2,0     0,10      4,21
  3        20.000     300 s      410 s        60 s        7,8       0,0      0,0     0,13      4,34
  4        25.000     300 s      510 s        60 s        9,5       0,0      0,0     0,16      4,49
  => thực thi (tải+cài, chưa soak/chờ): 29,7 phút | TỔNG = 4,49 h

THỰC TẾ — chỉ chọn thiết bị ONLINE (không có straggler)
  Wave          N  Khám phá   Tải xong  Cài/verify  Phase(ph)   Chờ(ph)  Soak(h)  Wall(h)  Cộng dồn
  1           500     330 s      340 s       180 s        8,7       0,0      2,0     0,14      2,14
  2         4.500     330 s      340 s       180 s        8,7       0,0      2,0     0,14      4,29
  3        20.000     330 s      710 s       180 s       14,8       0,0      0,0     0,25      4,54
  4        25.000     330 s      810 s       180 s       16,5       0,0      0,0     0,28      4,81
  => thực thi (tải+cài, chưa soak/chờ): 48,7 phút | TỔNG = 4,81 h

THỰC TẾ (ĐỀ XUẤT 1 h) — KHÁC mặc định 24 h của Q7
  Wave          N  Khám phá   Tải xong  Cài/verify  Phase(ph)   Chờ(ph)  Soak(h)  Wall(h)  Cộng dồn
  1           500     330 s      340 s       180 s        8,7      51,3      2,0     1,00      3,00
  2         4.500     330 s      340 s       180 s        8,7      51,3      2,0     1,00      6,00
  3        20.000     330 s      710 s       180 s       14,8      45,2      0,0     1,00      7,00
  4        25.000     330 s      810 s       180 s       16,5      43,5      0,0     1,00      8,00
  => thực thi (tải+cài, chưa soak/chờ): 48,7 phút | TỔNG = 8,00 h

THỰC TẾ + TỐI ƯU — promotion ở 95%, straggler chạy song song
  Wave          N  Khám phá   Tải xong  Cài/verify  Phase(ph)   Chờ(ph)  Soak(h)  Wall(h)  Cộng dồn
  1           500     330 s      340 s       180 s        8,7      51,3      2,0     1,00      3,00
  2         4.500     330 s      340 s       180 s        8,7      51,3      2,0     1,00      6,00
  3        20.000     330 s      710 s       180 s       14,8      45,2      0,0     1,00      7,00
  4        25.000     330 s      810 s       180 s       16,5      43,5      0,0     1,00      8,00
  (cột 'Cộng dồn' phía trên là mốc TUẦN TỰ để tham chiếu; tổng tối ưu tính lại bên dưới)
  => exec 48,7 phút + soak 4,0 h + straggler cuối 1,0 h = 5,81 h

ĐÚNG MẶC ĐỊNH Q7 — waveDeadline 24 h (literal Q7, xấu nhất)
  Wave          N  Khám phá   Tải xong  Cài/verify  Phase(ph)   Chờ(ph)  Soak(h)  Wall(h)  Cộng dồn
  1           500     600 s      610 s       900 s       25,2   1.414,8      2,0    24,00     26,00
  2         4.500     600 s      610 s       900 s       25,2   1.414,8      2,0    24,00     52,00
  3        20.000     600 s      610 s       900 s       25,2   1.414,8      0,0    24,00     76,00
  4        25.000     600 s      610 s       900 s       25,2   1.414,8      0,0    24,00    100,00
  => thực thi (tải+cài, chưa soak/chờ): 100,7 phút | TỔNG = 100,00 h

  BẢNG TỔNG HỢP 5 KỊCH BẢN:
    - TỐT NHẤT — lý thuyết: 0% OFFLINE, điều phối hoàn hảo, cài nhanh        exec    29,67 phút | tổng    4,49 h
    - THỰC TẾ — chỉ chọn thiết bị ONLINE (không có straggler)                exec    48,67 phút | tổng    4,81 h
    - THỰC TẾ (ĐỀ XUẤT 1 h) — KHÁC mặc định 24 h của Q7                      exec    48,67 phút | tổng    8,00 h
    - THỰC TẾ + TỐI ƯU — promotion ở 95%, straggler chạy song song           exec    48,67 phút | tổng    5,81 h
    - ĐÚNG MẶC ĐỊNH Q7 — waveDeadline 24 h (literal Q7, xấu nhất)            exec   100,67 phút | tổng  100,00 h

  LƯU Ý NHÃN KỊCH BẢN (quan trọng khi bảo vệ):
    - Q7 quy định waveDeadline MẶC ĐỊNH = 24 h. Đúng nguyên văn Q7 -> tổng = 100,00 h.
    - Con số 8,00 h (và 5,81 h) chỉ đạt được khi ĐỔI hạn chót xuống 1 h. Đó là ĐỀ XUẤT của D,
      KHÁC mặc định Q7, phải được cả nhóm/campaign owner CHỐT trước khi đưa lên slide.

  PHÂN RÃ THỜI GIAN KỊCH BẢN 'THỰC TẾ (ĐỀ XUẤT 1 h)' (tổng 8,00 h):
    - soak 2 wave x 2 h            = 4,00 h (50%)
    - chờ hạn chót straggler 4 wave = 4,00 h (50%)
    - tải + cài thực tế nằm LỌT trong thời gian chờ nên gần như không cộng thêm

  ĐỐI CHIẾU CON SỐ '~2-3 GIỜ' TRONG SPECIFICATION (mục 4):
    (a) Tải thuần theo Q6 (slot chỉ giữ lúc DOWNLOADING):
        50.000 x 50 MB / 2,50 GB/s = 2.500 GB / 2,50 GB/s = 16,67 phút
    (b) Nếu slot bị giữ suốt 3,2 phút/thiết bị (MÂU THUẪN Q6):
        50.000 / 500 x 3,2 phút = 320,00 phút = 5,33 h
    (c) Thực thi theo mô hình này (4 wave, tải+cài):
        TỐT NHẤT — lý thuyết: 0% OFFLINE, điều phối hoàn hảo, cài nhanh       29,67 phút
        THỰC TẾ — chỉ chọn thiết bị ONLINE (không có straggler)               48,67 phút
        THỰC TẾ (ĐỀ XUẤT 1 h) — KHÁC mặc định 24 h của Q7                     48,67 phút
        THỰC TẾ + TỐI ƯU — promotion ở 95%, straggler chạy song song          48,67 phút
        ĐÚNG MẶC ĐỊNH Q7 — waveDeadline 24 h (literal Q7, xấu nhất)          100,67 phút
    => '2-3 giờ' không tái lập được từ chính các giả định của §4: muốn ra 2-3 h phải giữ slot
       suốt lúc cài (trái Q6); còn nếu tính đủ soak + straggler thì > 4,5 h. Đây là ước tính
       CHƯA HIỆU CHỈNH, cần cập nhật lại Specification §4 (việc của người giữ spec).

====================================================================================================
E. TĂNG TRƯỞNG device_tasks & audit_logs MỖI NĂM
====================================================================================================
  Công thức: device_tasks/năm = campaigns/năm x thiết bị/campaign
           = 10 x 50.000 = 500.000 dòng/năm
           + 10% campaign rollback (giả định) -> 550.000 dòng/năm
  Lưu ý    : retry KHÔNG tạo dòng mới (attemptCount tăng trên cùng device_tasks) — giả định thiết kế
  audit_logs/năm = device_tasks x 5 dòng/task = 2.500.000 dòng/năm
             5 dòng gồm: PENDING, DOWNLOADING, INSTALLING, VERIFYING, SUCCESS/terminal
             + rollback -> 2.750.000 dòng/năm
  Dung lượng: device_tasks 275,00 MB/năm | audit_logs 1.100,00 MB/năm | tổng 1.375,00 MB/năm
              5 năm lưu trữ ~ 6,88 GB
  Check-in/năm = 100.000 x 31.536.000 / 300 = 10,51 tỷ request/năm
               = 28,80 triệu request/ngày = 333,33 request/s
  Nếu ghi DB mỗi check-in: 28,80 triệu UPDATE/ngày (333,33 UPDATE/s) — mức này chịu được,
              nhưng burst 3.000 RPS lúc herd phải gom batch/Redis (xem F)
  Audit đỉnh lúc tải: D = 50,00 task/s x 5 = 250 dòng/s (bé)
  device_firmware_histories/năm ~ 500.000 dòng (1 dòng mỗi task SUCCESS)

====================================================================================================
F. ĐIỂM NGHẼN & GIẢI PHÁP (SỐ LIỆU CHỐT)
====================================================================================================
  1) Egress firmware : đỉnh 20,00 Gbps, 2.500 GB/campaign, 30,00 TB/năm ở edge
     -> Pre-signed URL + CDN 50 PoP, slot tải 500, cache object 50 MB tại PoP
  2) Origin storage  : nếu không CDN phải phát 2.500 GB/campaign từ 1 vùng -> CDN giảm ~1.000x
  3) Ghi DB check-in : 333,33 UPDATE/s trung bình, 3.000 UPDATE/s cao điểm
     -> Redis giữ lastCheckInAt, batch flush 30-60 s; PgBouncer; không ghi audit cho heartbeat
  4) Redis semaphore : 500 token/campaign; cấp/thu hồi ~50,00 lần/s khi bão hòa
     -> Lua script nguyên tử, key theo campaign, TTL + worker thu hồi slot 'rò' sau timeout tải
  5) Scan timeout    : worker 30 s phải quét task DOWNLOADING/INSTALLING/VERIFYING
     -> partial index (status, lastHeartbeatAt); tối đa ~25.000 task chưa terminal/wave 4
  6) Dashboard/audit : 500.000 task/năm + 2.500.000 audit/năm (bé) nhưng đừng aggregate
     trực tiếp trên bảng lớn -> counter trong Redis, partition theo tháng
  KẾT LUẬN THỨ TỰ NGHẼN: (1) egress/CDN >> (2) burst check-in 3 000 RPS >> (3) DB write check-in; ghi task/audit KHÔNG phải nghẽn ở mức 100 000 thiết bị

====================================================================================================
G. KỊCH BẢN 1 000 000 THIẾT BỊ (x10)
====================================================================================================
  Check-in: 3.333,33 RPS trung bình; cao điểm 15.000 - 30.000 RPS
  Campaign : 500.000 máy; các đợt 5.000 / 45.000 / 200.000 / 250.000
  Dữ liệu  : 25.000 GB/campaign; 300,00 TB/năm edge
  Nếu scale slot x10: 5.000 slot x 5,0 MB/s = 25,00 GB/s = 200 Gbps (một vùng CDN)
  Nếu GIỮ 500 slot: D = 50,00 lượt/s; riêng wave 4 = 250.000/50,00 = 83,3 phút; cả campaign 166,7 phút
  Nếu scale slot x10: D = 500,00 lượt/s; wave 4 = 8,3 phút
  Dữ liệu bảng: device_tasks 5.000.000 dòng/năm; audit_logs 25.000.000 dòng/năm; ~12,5 GB/năm
  Check-in/năm: 105,12 tỷ request
  GÃY ĐẦU TIÊN (theo thứ tự):
    (1) Egress 1 vùng CDN/origin: 200 Gbps + 25.000 GB/campaign
        -> CDN đa vùng theo ISP, slot tải chia NGÂN SÁCH theo vùng (VD 2 000 slot x 10 vùng)
    (2) Burst check-in 30.000 RPS + 105,12 tỷ req/năm
        -> stateless ingestion scale ngang, Kafka/queue, rate limit theo ISP, jitter toàn cục
    (3) Ghi DB 30.000 UPDATE/s check-in -> gom batch, Redis, partition theo thời gian
    (4) Redis 5.000 token + counter: Redis Cluster shard theo campaign/vùng
    (5) Bảng lớn 5.000.000 task + 25.000.000 audit/năm -> partition tháng + cold storage

====================================================================================================
H. GIẢ ĐỊNH BỔ SUNG — IN LẠI THAM SỐ ĐANG DÙNG
====================================================================================================
  FLEET              = 100000
  CHECKIN_S          = 300
  FW_MB              = 50.0
  TARGET             = 50000
  SLOTS              = 500
  SPEED              = 5.0
  CAMPAIGNS_Y        = 10
  SOAK_H             = (2.0, 2.0, 0.0, 0.0)
  TIMEOUT tải        = 900
  TIMEOUT cài        = 600
  TIMEOUT verify     = 300
  OFFLINE_PCT        = 0.05
  GRACE_H            = 1.0
  DEADLINE_H         = 24.0
  AUDIT_PER_TASK     = 5
  RETRY_MULT         = 1.2
  POPS               = 50
  TASK_KB            = 0.5
  AUDIT_KB           = 0.4

----------------------------------------------------------------------------------------------------
KIỂM TRA CHÉO (assert)
  [OK] RPS trung bình 333,33 | kích thước wave | 20 Gbps | 2 500 GB | D = 50 lượt/s
  [OK] 5 kịch bản thời gian | 500 000 device_tasks | 2 500 000 audit_logs
  [OK] Mọi con số trong tài liệu được sinh từ các tham số ở MỤC 0.
```

---

## PHỤ LỤC 2 — RÚT GỌN CHO SLIDE 10

**6 bullet tối đa:**

1. **Check-in:** 100.000 máy / 300 s = **333 RPS trung bình**; khi thundering herd lên **1.500–3.000 RPS (4,5–9×)** → xử lý bằng lệch pha theo `serialNo` + full-jitter backoff + ingestion stateless autoscale; tải API check-in chỉ **~24 Mbps** nên không phải nút thắt.
2. **Chia đợt (Q1):** cỡ đợt **500 / 4.500 / 20.000 / 25.000** máy; **mốc 10% cộng dồn = 250 GB**, còn **đợt riêng wave 2 = 225 GB** — hai con số khác nhau, đừng nhầm.
3. **Băng thông đỉnh:** 500 slot × 5 MB/s = **2,5 GB/s = 20 Gbps** → bắt buộc **Object Storage + CDN** (origin chỉ phát ~2,5 GB/firmware, giảm ~1.000×) + pre-signed URL.
4. **Thời gian (ước tính đã hiệu chỉnh):** tải + cài thực tế chỉ **~49 phút** (29,7–48,7 phút) cho 50.000 máy vì slot chỉ giữ lúc `DOWNLOADING` — Q6; tổng campaign **4,81 h (chỉ chọn máy ONLINE) → 8,00 h (nếu chốt hạn chót wave 1 h)** do **soak 4 h + chờ thiết bị OFFLINE** chi phối.
5. **Hạn chót Q7 (phải nói rõ trên slide):** Q7 mặc định `waveDeadline` **24 h** → giữ nguyên thì tổng là **100 h**; con số **8 h chỉ đúng khi nhóm chốt đổi hạn chót xuống 1 h** (đề xuất của D, cần cả nhóm thông qua). "~2–3 giờ" trong Specification §4 là **ước tính chưa hiệu chỉnh**, cần cập nhật lại spec (việc của người giữ spec).
6. **Tăng trưởng & ×10:** **500.000 `device_tasks` + 2,5 triệu `audit_logs`/năm** (~1,4 GB/năm — không nghẽn dung lượng nhưng phải partition); ×10 gãy đầu tiên ở **egress 200 Gbps** và **burst 30.000 RPS**, không phải DB.

**Bảng nhỏ (dán cạnh bullet):**

| Hạng mục | Con số | Hệ quả thiết kế |
| :--- | :--- | :--- |
| Check-in | 333 RPS TB · 1.500–3.000 RPS đỉnh | Lệch pha + jitter + autoscale |
| Đợt lớn nhất (wave 4) | 25.000 máy · 1.250 GB · 500 s @ 20 Gbps | CDN + 500 slot tải |
| Băng thông đỉnh | 20 Gbps | CDN bắt buộc, pre-signed URL |
| Tổng campaign | 4,81–8,00 h nếu chốt hạn chót 1 h · **100 h nếu giữ mặc định Q7 24 h** | Chốt hạn chót với C + cắt straggler |
| Dữ liệu/năm | 500k task · 2,5M audit (~1,4 GB) | Partition theo tháng + async audit |
| Quy mô ×10 | 3.333 RPS · 200 Gbps nếu scale slot | CDN đa vùng + queue + Redis Cluster |
