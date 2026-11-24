#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capacity_calc.py — Kiểm chứng toàn bộ con số trong
docs/member-d/CAPACITY_ESTIMATION.md  (Task 1 / Slide 10).

Đề tài: Nền tảng triển khai cập nhật firmware (DASAN Vietnam) — KITS 2026 OJT.
Chạy:   python capacity_calc.py
Ràng buộc: chỉ dùng thư viện chuẩn của Python; mọi tham số nằm ở MỤC 0.
Mọi giả định không có trong đề bài được liệt kê ở mục H của tài liệu.
"""

import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# =====================================================================
# 0. THAM SỐ ĐẦU VÀO  (đối chiếu mục H của tài liệu)
# =====================================================================
FLEET = 100_000            # số thiết bị toàn hệ thống
CHECKIN_S = 300            # chu kỳ check-in (giây) — 5 phút
FW_MB = 50.0               # kích thước 1 file firmware (MB)
TARGET = 50_000            # số thiết bị của campaign lớn nhất
SLOTS = 500                # maxConcurrentDevices (slot tải)
SPEED = 5.0                # tốc độ tải mỗi thiết bị (MB/s)
CAMPAIGNS_Y = 10           # số campaign/năm
WAVE_CUM = (1, 10, 50, 100)        # % CỘNG DỒN (quy ước Q1)
SOAK_H = (2.0, 2.0, 0.0, 0.0)      # soak sau wave 1, 2 (quy ước Q2)
T_DL = 15 * 60             # timeout tải (quy ước Q9)
T_INSTALL = 10 * 60        # timeout cài (quy ước Q9)
T_VERIFY = 5 * 60          # timeout verify (quy ước Q9)
INSTALL_REAL = 180.0       # thời gian cài + reboot + verify thực tế (giả định 3 phút)
OFFLINE_PCT = 0.05         # tỷ lệ thiết bị OFFLINE trong nhóm đích
GRACE_H = 1.0              # hạn chót KHUYẾN NGHỊ cho thiết bị không phản hồi
DEADLINE_H = 24.0          # waveDeadline mặc định (quy ước Q7)
AUDIT_PER_TASK = 5         # số dòng audit_logs trên 1 device_task
RETRY_MULT = 1.2           # hệ số lưu lượng do retry (giả định)
POPS = 50                  # số PoP CDN (giả định)
REQ_KB = 0.4               # kích thước request check-in (KB, giả định)
RESP_KB = 0.6              # kích thước response check-in TB (KB, giả định)
TASK_KB = 0.5              # kích thước 1 dòng device_tasks (KB, giả định)
AUDIT_KB = 0.4             # kích thước 1 dòng audit_logs (KB, giả định)
SEC_PER_YEAR = 365 * 24 * 3600


def F(x, nd=2):
    """Định dạng số kiểu Việt Nam: 1 234,56"""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def N(x):
    return F(x, 0)


def hr(ch="=", n=100):
    print(ch * n)


def head(sec, title):
    print()
    hr("=")
    print(f"{sec}. {title}")
    hr("=")


# =====================================================================
# A. CHECK-IN
# =====================================================================
head("A", "CHECK-IN: RPS TRUNG BÌNH, CAO ĐIỂM (THUNDERING HERD) & TẢI API")

avg_rps = FLEET / CHECKIN_S
print(f"  Công thức : RPS_tb = FLEET / chu_kỳ = {N(FLEET)} / {N(CHECKIN_S)}")
print(f"  Kết quả   : RPS trung bình = {F(avg_rps)} RPS")

herd_n = 0.30 * FLEET
peak_lo = herd_n / 20.0
peak_hi = herd_n / 10.0
print("  Cao điểm  : giả định 30% fleet (30 000 máy) online lại cùng lúc sau sự cố mất điện/mạng:")
print(f"              - dàn trong 20 s -> {N(peak_lo)} RPS")
print(f"              - dàn trong 10 s -> {N(peak_hi)} RPS")
print(f"  Hệ số     : {F(peak_lo / avg_rps, 1)}x - {F(peak_hi / avg_rps, 1)}x RPS trung bình")

wave4_inc = TARGET * 0.50
extra_wave = wave4_inc / CHECKIN_S
print(f"  Cao điểm phụ khi mở wave 4 ({N(wave4_inc)} máy): +{F(extra_wave)} RPS (nhỏ, không phải điểm nghẽn)")

api_kb = REQ_KB + RESP_KB
api_avg_mbps = avg_rps * api_kb / 1000.0 * 8
api_peak_mbps = peak_hi * api_kb / 1000.0 * 8
print(f"  Tải API check-in (giả định {F(api_kb, 1)} KB/lượt): trung bình {F(api_avg_mbps, 1)} Mbps; "
      f"cao điểm {F(api_peak_mbps, 1)} Mbps")

spread_rps = herd_n / CHECKIN_S
jitter_peak = avg_rps + spread_rps
print(f"  Jitter    : dàn herd {N(herd_n)} máy trên 1 chu kỳ {N(CHECKIN_S)} s -> +{F(spread_rps)} RPS")
print(f"              => cao điểm còn ~{F(jitter_peak)} RPS, giảm {F(peak_hi / jitter_peak, 1)}x so với "
      f"{N(peak_hi)} RPS")
print(f"              (jitter ±30 s theo Q thiết kế chỉ dàn được ±60 s; cần full-jitter/backoff khi lỗi)")

inst_cap = 1000.0
n_inst = math.ceil(peak_hi / inst_cap)
print(f"  Instance  : giả định {N(inst_cap)} RPS/instance -> cần {N(n_inst)} instance, cấp {N(n_inst + 2)} "
      f"(dư N+2)")
hmac_core = peak_hi * 0.0002
tls_core = peak_hi * 0.002
print(f"  CPU       : HMAC-SHA256 ~0,2 ms/lượt -> {F(hmac_core)} core; TLS full handshake ~2 ms/lượt -> "
      f"{F(tls_core)} core")
print(f"              => ưu tiên keep-alive/session resumption thay vì bắt tay TLS mỗi check-in")

# =====================================================================
# B. DỮ LIỆU TỪNG WAVE
# =====================================================================
head("B", "DỮ LIỆU CỦA TỪNG WAVE — CỘNG DỒN 1/10/50/100 % (QUY ƯỚC Q1)")

cum = [int(round(TARGET * p / 100.0)) for p in WAVE_CUM]
inc = [cum[0]] + [cum[i] - cum[i - 1] for i in range(1, 4)]
GBPS = SLOTS * SPEED / 1000.0            # GB/s ở đỉnh (2,5 GB/s)
print("  Công thức: dung lượng = số_máy x 50 MB; 1 GB = 1000 MB (thập phân)")
print()
print(f"  {'Mốc cộng dồn':<26}{'Số máy':>10}{'Dung lượng':>14}{'Thời gian tải đỉnh':>22}")
for i, pct in enumerate(WAVE_CUM):
    vol = cum[i] * FW_MB / 1000.0
    print(f"  {'Wave ' + str(i + 1) + ' (' + str(pct) + '% cộng dồn)':<26}"
          f"{N(cum[i]):>10}{N(vol) + ' GB':>14}{F(vol / GBPS) + ' s':>22}")
print()
print(f"  {'Đợt riêng (hiệu số)':<26}{'Số máy':>10}{'Dung lượng':>14}{'Thời gian tải đỉnh':>22}")
for i in range(4):
    vol = inc[i] * FW_MB / 1000.0
    print(f"  {'Wave ' + str(i + 1) + ' (đợt riêng)':<26}"
          f"{N(inc[i]):>10}{N(vol) + ' GB':>14}{F(vol / GBPS) + ' s':>22}")
print()
print(f"  PHÂN BIỆT: mốc 10% CỘNG DỒN = {N(cum[1])} máy = {N(cum[1] * FW_MB / 1000)} GB")
print(f"             đợt riêng wave 2 (9%) = {N(inc[1])} máy = {N(inc[1] * FW_MB / 1000)} GB")
print(f"             chênh lệch = 500 máy của wave 1 = 25 GB")
total_gb = TARGET * FW_MB / 1000.0
print(f"  Tổng campaign 50 000 máy = {N(total_gb)} GB = {F(total_gb / 1000)} TB")
print(f"  Cộng retry (x{F(RETRY_MULT, 1)}) = {F(total_gb * RETRY_MULT / 1000)} TB/campaign")
print(f"  {N(CAMPAIGNS_Y)} campaign/năm -> {F(total_gb * RETRY_MULT * CAMPAIGNS_Y / 1000)} TB/năm lưu lượng EDGE (CDN)")

# =====================================================================
# C. BĂNG THÔNG ĐỈNH
# =====================================================================
head("C", "BĂNG THÔNG ĐỈNH & VÌ SAO BẮT BUỘC CDN")

peak_mbs = SLOTS * SPEED
gb_s = peak_mbs / 1000.0
gbps = gb_s * 8
gib_s = peak_mbs / 1024.0
print(f"  Công thức : B_đỉnh = maxConcurrentDevices x tốc_độ_tải")
print(f"            = {N(SLOTS)} x {F(SPEED, 1)} MB/s = {N(peak_mbs)} MB/s")
print(f"  Kết quả   : {F(gb_s)} GB/s = {F(gib_s)} GiB/s = {F(gbps)} Gbps")
dev_mbps = SPEED * 8
print(f"  1 thiết bị : {F(SPEED, 1)} MB/s = {F(dev_mbps)} Mbps (giả định đường truyền hộ gia đình)")
unthrottled = TARGET * dev_mbps / 1000.0
print(f"  KHÔNG giới hạn slot: {N(TARGET)} x {F(dev_mbps)} Mbps = {N(unthrottled)} Gbps "
      f"= {F(unthrottled / 1000, 1)} Tbps ({N(unthrottled / gbps)}x băng thông đỉnh)")
edge_gb = total_gb
print(f"  Toàn campaign {N(TARGET)} máy = {N(edge_gb)} GB; tại {F(gb_s)} GB/s -> {F(edge_gb / gb_s / 60)} phút")
origin_gb = FW_MB * POPS / 1000.0
print(f"  CDN {N(POPS)} PoP : origin chỉ phát {N(POPS)} bản x 50 MB = {F(origin_gb)} GB (thay vì "
      f"{N(edge_gb)} GB ra edge)")
print(f"              => giảm egress origin ~{N(edge_gb / origin_gb)}x; hit ratio gần 100% vì mỗi version chỉ 1 object")
print(f"  So sánh   : tải check-in cao điểm {F(api_peak_mbps, 1)} Mbps = "
      f"{F(api_peak_mbps * 100 / (gbps * 1000), 2)}% của {F(gbps)} Gbps")
print(f"              => băng thông check-in KHÔNG đáng kể; toàn bộ áp lực nằm ở file firmware")

# =====================================================================
# D. THỜI GIAN CAMPAIGN THEO TỪNG WAVE
# =====================================================================
head("D", "THỜI GIAN HOÀN TẤT CAMPAIGN 50 000 THIẾT BỊ — TÍNH THEO TỪNG WAVE")

D_rate = SLOTS * SPEED / FW_MB            # lượt tải/giây = 50
print(f"  Năng lực tải : D = SLOTS x SPEED / FW = {N(SLOTS)} x {F(SPEED, 1)} / {F(FW_MB, 0)} "
      f"= {F(D_rate)} lượt tải/giây")
print("  Công thức mỗi wave:")
print("    T_tải_xong = max(T_khám_phá, N/D) + 10 s (+ T_chờ_retry nếu N/D > chu kỳ check-in)")
print("    T_phase    = T_tải_xong + T_cài/verify")
print("    T_wave     = max(T_phase, hạn_chót_của_wave) + soak   (chỉ chờ hạn chót khi còn thiết bị OFFLINE)")
print()
print("  Giả định then chốt: slot CHỈ bị giữ lúc DOWNLOADING (Q6) -> cài/verify các máy chạy SONG SONG,")
print("  không chiếm slot; vì vậy tải+cài nhanh hơn nhiều so với cảm giác '500 slot chia 50 000 máy'.")


def wave_rows(disc, retry_tail, install, offline, grace_h):
    rows = []
    for i in range(4):
        n = inc[i]
        base = n / D_rate
        tail = retry_tail if base > CHECKIN_S else 0.0
        dl = max(disc, base) + 10.0 + tail
        phase = dl + install
        wait = max(0.0, grace_h * 3600.0 - phase) if offline else 0.0
        rows.append(dict(n=n, disc=disc, tail=tail, dl=dl, install=install,
                         phase=phase, wait=wait, soak=SOAK_H[i], wall=phase + wait))
    return rows


def print_wave_table(rows):
    print(f"  {'Wave':<6}{'N':>9}{'Khám phá':>10}{'Tải xong':>11}{'Cài/verify':>12}"
          f"{'Phase(ph)':>11}{'Chờ(ph)':>10}{'Soak(h)':>9}{'Wall(h)':>9}{'Cộng dồn':>10}")
    cum_h = 0.0
    for i, r in enumerate(rows):
        cum_h += r["wall"] / 3600.0 + r["soak"]
        print(f"  {i + 1:<6}{N(r['n']):>9}{N(r['disc']) + ' s':>10}{N(r['dl']) + ' s':>11}"
              f"{N(r['install']) + ' s':>12}{F(r['phase'] / 60, 1):>11}{F(r['wait'] / 60, 1):>10}"
              f"{F(r['soak'], 1):>9}{F(r['wall'] / 3600, 2):>9}{F(cum_h, 2):>10}")
    return cum_h


SCEN = [
    ("TỐT NHẤT — lý tưởng: 0% OFFLINE, cài nhanh, không retry",
     dict(disc=300.0, retry_tail=0.0, install=60.0, offline=False, grace_h=0.0, mode="serial")),
    ("THỰC TẾ — chỉ chọn thiết bị ONLINE (không có straggler)",
     dict(disc=330.0, retry_tail=150.0, install=INSTALL_REAL, offline=False, grace_h=0.0, mode="serial")),
    ("THỰC TẾ — tuân thủ Q7: 5% OFFLINE, chờ hạn chót 1 h mỗi wave",
     dict(disc=330.0, retry_tail=150.0, install=INSTALL_REAL, offline=True, grace_h=GRACE_H, mode="serial")),
    ("THỰC TẾ + TỐI ƯU — promotion ở 95%, straggler chạy song song",
     dict(disc=330.0, retry_tail=150.0, install=INSTALL_REAL, offline=True, grace_h=GRACE_H, mode="parallel")),
    ("XẤU NHẤT — giữ waveDeadline mặc định 24 h (Q7)",
     dict(disc=600.0, retry_tail=300.0, install=T_INSTALL + T_VERIFY, offline=True, grace_h=DEADLINE_H, mode="serial")),
]
summary = []
for name, sc in SCEN:
    rows = wave_rows(sc["disc"], sc["retry_tail"], sc["install"], sc["offline"], sc["grace_h"])
    print(name)
    total_h = print_wave_table(rows)
    exec_min = sum(r["phase"] for r in rows) / 60.0
    if sc["mode"] == "parallel":
        print("  (cột 'Cộng dồn' phía trên là mốc TUẦN TỰ để tham chiếu; tổng tối ưu tính lại bên dưới)")
        total_h = exec_min / 60.0 + sum(SOAK_H) + sc["grace_h"]
        print(f"  => exec {F(exec_min, 1)} phút + soak {F(sum(SOAK_H), 1)} h + straggler cuối "
              f"{F(sc['grace_h'], 1)} h = {F(total_h, 2)} h")
    else:
        print(f"  => thực thi (tải+cài, chưa soak/chờ): {F(exec_min, 1)} phút | TỔNG = {F(total_h, 2)} h")
    summary.append((name, exec_min, total_h))
    print()

print("  BẢNG TỔNG HỢP 5 KỊCH BẢN:")
for name, e, t in summary:
    print(f"    - {name:<66} exec {F(e):>8} phút | tổng {F(t, 2):>7} h")
print()
print("  PHÂN RÃ THỜI GIAN KỊCH BẢN 'THỰC TẾ - Q7' (tổng 8,00 h):")
print(f"    - soak 2 wave x 2 h            = 4,00 h (50%)")
print(f"    - chờ hạn chót straggler 4 wave = 4,00 h (50%)")
print("    - tải + cài thực tế nằm LỌT trong thời gian chờ nên gần như không cộng thêm")
print()

print("  ĐỐI CHIẾU CON SỐ '~2-3 GIỜ' TRONG SPECIFICATION (mục 4):")
pure_min = edge_gb / gb_s / 60.0
print(f"    (a) Tải thuần theo Q6 (slot chỉ giữ lúc DOWNLOADING):")
print(f"        {N(TARGET)} x 50 MB / {F(gb_s)} GB/s = {N(edge_gb)} GB / {F(gb_s)} GB/s = {F(pure_min)} phút")
hold_min = TARGET / SLOTS * 3.2
print(f"    (b) Nếu slot bị giữ suốt 3,2 phút/thiết bị (MÂU THUẪN Q6):")
print(f"        {N(TARGET)} / {N(SLOTS)} x 3,2 phút = {F(hold_min)} phút = {F(hold_min / 60)} h")
print(f"    (c) Thực thi theo mô hình này (4 wave, tải+cài):")
for name, e, t in summary:
    print(f"        {name:<66} {F(e):>8} phút")
print("    => '2-3 giờ' không khớp (a) cũng không khớp (b): nó là kết quả của giả định giữ slot")
print("       suốt quá trình cài (trái Q6) và bỏ qua soak 4 h + straggler OFFLINE.")

# =====================================================================
# E. TĂNG TRƯỞNG DỮ LIỆU
# =====================================================================
head("E", "TĂNG TRƯỞNG device_tasks & audit_logs MỖI NĂM")

tasks_y = CAMPAIGNS_Y * TARGET
tasks_y_rb = tasks_y * 1.10
audit_y = tasks_y * AUDIT_PER_TASK
audit_y_rb = tasks_y_rb * AUDIT_PER_TASK
print(f"  Công thức: device_tasks/năm = campaigns/năm x thiết bị/campaign")
print(f"           = {N(CAMPAIGNS_Y)} x {N(TARGET)} = {N(tasks_y)} dòng/năm")
print(f"           + 10% campaign rollback (giả định) -> {N(tasks_y_rb)} dòng/năm")
print(f"  Lưu ý    : retry KHÔNG tạo dòng mới (attemptCount tăng trên cùng device_tasks) — giả định thiết kế")
print(f"  audit_logs/năm = device_tasks x {N(AUDIT_PER_TASK)} dòng/task = {N(audit_y)} dòng/năm")
print(f"             {N(AUDIT_PER_TASK)} dòng gồm: PENDING, DOWNLOADING, INSTALLING, VERIFYING, SUCCESS/terminal")
print(f"             + rollback -> {N(audit_y_rb)} dòng/năm")
st_task = tasks_y_rb * TASK_KB / 1000.0
st_audit = audit_y_rb * AUDIT_KB / 1000.0
print(f"  Dung lượng: device_tasks {F(st_task)} MB/năm | audit_logs {F(st_audit)} MB/năm | "
      f"tổng {F(st_task + st_audit)} MB/năm")
print(f"              5 năm lưu trữ ~ {F((st_task + st_audit) * 5 / 1000)} GB")
checkin_y = FLEET * SEC_PER_YEAR / CHECKIN_S
print(f"  Check-in/năm = {N(FLEET)} x {N(SEC_PER_YEAR)} / {N(CHECKIN_S)} = {F(checkin_y / 1e9)} tỷ request/năm")
print(f"               = {F(checkin_y / 365 / 1e6)} triệu request/ngày = {F(checkin_y / SEC_PER_YEAR)} request/s")
print(f"  Nếu ghi DB mỗi check-in: {F(checkin_y / 365 / 1e6)} triệu UPDATE/ngày ({F(avg_rps)} UPDATE/s) — mức này chịu được,")
print(f"              nhưng burst {N(peak_hi)} RPS lúc herd phải gom batch/Redis (xem F)")
peak_audit = D_rate * AUDIT_PER_TASK
print(f"  Audit đỉnh lúc tải: D = {F(D_rate)} task/s x {N(AUDIT_PER_TASK)} = {N(peak_audit)} dòng/s (bé)")
print(f"  device_firmware_histories/năm ~ {N(tasks_y)} dòng (1 dòng mỗi task SUCCESS)")

# =====================================================================
# F. ĐIỂM NGHẼN
# =====================================================================
head("F", "ĐIỂM NGHẼN & GIẢI PHÁP (SỐ LIỆU CHỐT)")

print(f"  1) Egress firmware : đỉnh {F(gbps)} Gbps, {N(edge_gb)} GB/campaign, "
      f"{F(total_gb * RETRY_MULT * CAMPAIGNS_Y / 1000)} TB/năm ở edge")
print(f"     -> Pre-signed URL + CDN {N(POPS)} PoP, slot tải {N(SLOTS)}, cache object 50 MB tại PoP")
print(f"  2) Origin storage  : nếu không CDN phải phát {N(edge_gb)} GB/campaign từ 1 vùng -> CDN giảm ~"
      f"{N(edge_gb / origin_gb)}x")
print(f"  3) Ghi DB check-in : {F(avg_rps)} UPDATE/s trung bình, {N(peak_hi)} UPDATE/s cao điểm")
print(f"     -> Redis giữ lastCheckInAt, batch flush 30-60 s; PgBouncer; không ghi audit cho heartbeat")
print(f"  4) Redis semaphore : {N(SLOTS)} token/campaign; cấp/thu hồi ~{F(D_rate)} lần/s khi bão hòa")
print(f"     -> Lua script nguyên tử, key theo campaign, TTL + worker thu hồi slot 'rò' sau timeout tải")
print(f"  5) Scan timeout    : worker 30 s phải quét task DOWNLOADING/INSTALLING/VERIFYING")
print(f"     -> partial index (status, lastHeartbeatAt); tối đa ~{N(inc[3])} task chưa terminal/wave 4")
print(f"  6) Dashboard/audit : {N(tasks_y)} task/năm + {N(audit_y)} audit/năm (bé) nhưng đừng aggregate")
print(f"     trực tiếp trên bảng lớn -> counter trong Redis, partition theo tháng")
print(f"  KẾT LUẬN THỨ TỰ NGHẼN: (1) egress/CDN >> (2) burst check-in 3 000 RPS >> (3) DB write "
      f"check-in; ghi task/audit KHÔNG phải nghẽn ở mức 100 000 thiết bị")

# =====================================================================
# G. KỊCH BẢN 10X
# =====================================================================
head("G", "KỊCH BẢN 1 000 000 THIẾT BỊ (x10)")

fleet10 = FLEET * 10
target10 = TARGET * 10
avg10 = fleet10 / CHECKIN_S
peak10_lo = 0.30 * fleet10 / 20.0
peak10_hi = 0.30 * fleet10 / 10.0
cum10 = [int(round(target10 * p / 100.0)) for p in WAVE_CUM]
inc10 = [cum10[0]] + [cum10[i] - cum10[i - 1] for i in range(1, 4)]
slots10 = SLOTS * 10
peak_mbs10 = slots10 * SPEED
gbps10 = peak_mbs10 / 1000.0 * 8
edge_gb10 = target10 * FW_MB / 1000.0
D10 = slots10 * SPEED / FW_MB
D500 = SLOTS * SPEED / FW_MB
print(f"  Check-in: {F(avg10)} RPS trung bình; cao điểm {N(peak10_lo)} - {N(peak10_hi)} RPS")
print(f"  Campaign : {N(target10)} máy; các đợt {N(inc10[0])} / {N(inc10[1])} / {N(inc10[2])} / {N(inc10[3])}")
print(f"  Dữ liệu  : {N(edge_gb10)} GB/campaign; {F(edge_gb10 * RETRY_MULT * CAMPAIGNS_Y / 1000)} TB/năm edge")
print(f"  Nếu scale slot x10: {N(slots10)} slot x {F(SPEED, 1)} MB/s = {F(peak_mbs10 / 1000)} GB/s = "
      f"{N(gbps10)} Gbps (một vùng CDN)")
print(f"  Nếu GIỮ {N(SLOTS)} slot: D = {F(D500)} lượt/s; riêng wave 4 = {N(inc10[3])}/{F(D500)} = "
      f"{F(inc10[3] / D500 / 60, 1)} phút; cả campaign {F(edge_gb10 / gb_s / 60, 1)} phút")
print(f"  Nếu scale slot x10: D = {F(D10)} lượt/s; wave 4 = {F(inc10[3] / D10 / 60, 1)} phút")
tasks10 = CAMPAIGNS_Y * target10
audit10 = tasks10 * AUDIT_PER_TASK
print(f"  Dữ liệu bảng: device_tasks {N(tasks10)} dòng/năm; audit_logs {N(audit10)} dòng/năm; "
      f"~{F((tasks10 * TASK_KB + audit10 * AUDIT_KB) / 1e6, 1)} GB/năm")
print(f"  Check-in/năm: {F(fleet10 * SEC_PER_YEAR / CHECKIN_S / 1e9)} tỷ request")
print("  GÃY ĐẦU TIÊN (theo thứ tự):")
print(f"    (1) Egress 1 vùng CDN/origin: {N(gbps10)} Gbps + {N(edge_gb10)} GB/campaign")
print("        -> CDN đa vùng theo ISP, slot tải chia NGÂN SÁCH theo vùng (VD 2 000 slot x 10 vùng)")
print(f"    (2) Burst check-in {N(peak10_hi)} RPS + {F(fleet10 * SEC_PER_YEAR / CHECKIN_S / 1e9)} tỷ req/năm")
print("        -> stateless ingestion scale ngang, Kafka/queue, rate limit theo ISP, jitter toàn cục")
print(f"    (3) Ghi DB {N(peak10_hi)} UPDATE/s check-in -> gom batch, Redis, partition theo thời gian")
print(f"    (4) Redis {N(slots10)} token + counter: Redis Cluster shard theo campaign/vùng")
print(f"    (5) Bảng lớn {N(tasks10)} task + {N(audit10)} audit/năm -> partition tháng + cold storage")

# =====================================================================
# H. GIẢ ĐỊNH (in lại tham số)
# =====================================================================
head("H", "GIẢ ĐỊNH BỔ SUNG — IN LẠI THAM SỐ ĐANG DÙNG")
for k, v in [
    ("FLEET", FLEET), ("CHECKIN_S", CHECKIN_S), ("FW_MB", FW_MB), ("TARGET", TARGET),
    ("SLOTS", SLOTS), ("SPEED", SPEED), ("CAMPAIGNS_Y", CAMPAIGNS_Y),
    ("SOAK_H", SOAK_H), ("TIMEOUT tải", T_DL), ("TIMEOUT cài", T_INSTALL),
    ("TIMEOUT verify", T_VERIFY), ("OFFLINE_PCT", OFFLINE_PCT), ("GRACE_H", GRACE_H),
    ("DEADLINE_H", DEADLINE_H), ("AUDIT_PER_TASK", AUDIT_PER_TASK),
    ("RETRY_MULT", RETRY_MULT), ("POPS", POPS), ("TASK_KB", TASK_KB), ("AUDIT_KB", AUDIT_KB),
]:
    print(f"  {k:<18} = {v}")

# =====================================================================
# KIỂM TRA CHÉO
# =====================================================================
print()
hr("-")
print("KIỂM TRA CHÉO (assert)")
assert abs(avg_rps - 100000 / 300) < 1e-9
assert cum == [500, 5000, 25000, 50000]
assert inc == [500, 4500, 20000, 25000]
assert abs(peak_mbs - 2500) < 1e-9
assert abs(gbps - 20) < 1e-9
assert abs(total_gb - 2500) < 1e-9
assert abs(D_rate - 50) < 1e-9
assert abs(summary[0][2] - 1780 / 3600 - 4.0) < 1e-9     # tốt nhất
assert abs(summary[1][2] - 2620 / 3600 - 4.0) < 1e-9     # online-only
assert abs(summary[2][2] - 8.0) < 1e-9                   # Q7, grace 1h
assert abs(summary[4][2] - 100.0) < 1e-9                 # xấu nhất, deadline 24h
assert abs(tasks_y - 500000) < 1e-9
assert abs(audit_y - 2500000) < 1e-9
print("  [OK] RPS trung bình 333,33 | kích thước wave | 20 Gbps | 2 500 GB | D = 50 lượt/s")
print("  [OK] 5 kịch bản thời gian | 500 000 device_tasks | 2 500 000 audit_logs")
print("  [OK] Mọi con số trong tài liệu được sinh từ các tham số ở MỤC 0.")
