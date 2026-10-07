# Reflection — Day 20 Lab (Personal Report)

> **Đây là báo cáo cá nhân.** Số liệu của bạn **không** so sánh được với bạn cùng lớp
> — chỉ so **before vs after trên chính máy bạn**. Rubric chấm độ rõ ràng của setup,
> đo lường và **lập luận**, không chấm tốc độ tuyệt đối.

**Họ Tên:** Phan Van Nghi
**MSSV:** 2A202602632
**Cohort:** A20-K1
**Ngày submit:** 2026-10-07

---

## 1. Hardware & runtime  *(rubric 1, 2 — 10 điểm)*

- **OS:** macOS 27.0 (Darwin 27.0.0, arm64)
- **CPU:** Apple M1 Pro
- **Cores:** 8 physical / 8 logical (6 performance + 2 efficiency)
- **CPU extensions:** NEON
- **RAM:** 16 GB (unified memory)
- **Accelerator:** Apple Metal (GPU tích hợp, `ngl=99`)
- **llama.cpp asset đã tải:** llama-b10488-bin-macos-arm64.tar.gz
- **Model đã dùng:** Qwen3.5 0.8B (`LAB_MODEL=qwen35-0.8b`)
- **Quantization:** Q4_K_M + UD-Q2_K_XL (từ `models/active.json`)

**Chạy ở đâu:** laptop của tôi (không dùng Colab/Kaggle).

**Setup story** (≤ 80 chữ): Máy 16 GB đủ cho Gemma 4 E2B, nhưng tôi chọn Qwen3.5 0.8B
(`LAB_MODEL=qwen35-0.8b make setup`) vì tải chỉ 0.9 GB và mỗi lần chạy nhanh hơn, để kịp
deadline. Setup không lỗi trên Python 3.14. Workaround duy nhất: `make tune` CPU-only ở
`-t 16` chạy hơn 9 phút không xong nên tôi phải kill tay (giải thích ở §5).

---

## 2. Đo lường  *(rubric 3, 4, 5 — 20 điểm)*

| Quantization | Size (GB) | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode (tok/s) |
|---|--:|--:|--:|--:|--:|--:|
| Q4_K_M | 0.50 | 2079 | 61 / 89 | 10.2 / 10.8 | 691 / 728 / 728 | 98.0 |
| UD-Q2_K_XL | 0.39 | 2048 | 67 / 94 | 12.9 / 14.6 | 868 / 989 / 989 | 77.7 |

**Quan sát** (≤ 60 chữ): Lần đo này 2-bit **chậm hơn 1.26×** (77.7 vs 98.0 tok/s); lần
đo trước thì nhanh hơn 1.20×, nên khác biệt chỉ ngang nhiễu. Model 0.8B trên Metal không bị
chặn bởi bandwidth, nên ít byte hơn không giúp. Hỏi cùng một câu: 2-bit tính 17×23 = 381
(sai), 4-bit = 391 (đúng). **Không đáng.**

---

## 3. Serving under load  *(rubric 8, 9, 10 — 20 điểm)*

| Users | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|--:|--:|--:|--:|--:|--:|--:|
| 10 | 2.37 | 3100 | 4900 | 5600 | 7.6 | 0.0% |
| 50 | 2.34 | 19000 | 22000 | 35000 | 39.1 | 0.0% |

- **Offered load tăng 5×, throughput thực tăng:** 0.99×
- **P95 tăng:** 4.49×
- **Effective concurrency ở 50 users:** 39.1 so với `--parallel` = 4 slots

**Peak `llamacpp:n_busy_slots_per_decode`** (từ `make metrics` khi `make load-50` đang
chạy): 3.94 / 4 slots

**Saturation reading** (≤ 80 chữ): Server bão hoà ngay từ 10 users: RPS chỉ đi từ
2.37 lên 2.34 trong khi P95 tăng 4.49×. Phần tăng thêm là **queue time**:
`requests_processing` luôn bằng 4, `requests_deferred` ở mức 40–46, và theo Little's Law
~90% latency trung bình (16.7 s) là thời gian chờ slot. Knob đầu tiên tôi thử là
`--parallel` 4→8 (slot đang cạn, 3.94/4), nhưng lợi ích sẽ giảm dần; thứ giữ được goodput@SLO
là admission control.

---

## 4. Integration  *(rubric 12, 13 — 15 điểm)*

| Day | Piece | Real hay stub? |
|---|---|---|
| N16 Cloud/IaC | không có, chạy local trên laptop | stub |
| N17 Data pipeline | `TOY_DOCS` hard-code 6 câu trong `pipeline.py` | stub |
| N18 Lakehouse | Python list trong memory | stub |
| N19 Vector + features | keyword overlap, không có embedding server | stub |
| N20 Serving | `llama-server` | real |

**Latency split** (mean của 3 query, từ output của `pipeline.py`):

- embed: 0.0 ms (không có embedding server, dùng keyword fallback)
- retrieve: 0.0 ms
- llm: 1761.5 ms
- **stage chiếm nhiều nhất:** llm (100% của total 1761.6 ms)

**Reflection** (≤ 60 chữ): Bottleneck là llm, đúng kỳ vọng vì retrieval đang là stub. Trong
llm, decode (759–2064 ms) lớn hơn prefill (99–475 ms) nhiều. Để giảm 2× tôi sẽ cắt số token
output (`max_tokens` 200 → ~80, yêu cầu trả lời ngắn). Prompt caching chỉ cứu được ~100 ms
prefill nên không đủ.

---

## 5. The single change that mattered most  *(rubric 11 — 10 điểm)*

**Change:** hạ thread count từ `-t 8` (mặc định = số physical core) xuống `-t 4`, decode
chạy trên CPU (`LAB_N_GPU_LAYERS=0 make tune` → `benchmarks/01-tuning-tg128-cpu.md`).

```
before:  11.7 tok/s   (-t 8, tg128, CPU-only)
after:   89.9 tok/s   (-t 4, tg128, CPU-only)
speedup: 7.7×
```

Đối chứng với Metal (`make tune` mặc định, `ngl=99`, `benchmarks/01-tuning-tg128.md`):
`-t 8` 103.1 → `-t 4` 114.7 tok/s = **1.11×**; `-t 1` 113.3 tok/s gần bằng `-t 4`.

**Tại sao nó work:**

Deck kỳ vọng decode tăng tới số physical core rồi đi ngang. Máy tôi **không** như vậy: peak
ở 4 thread, và ở 8 thread hiệu năng **sụp đổ 7.7×** chứ không đi ngang. Nguyên nhân là cách
ggml chạy song song: mỗi matmul được chia **đều** cho N thread, sau mỗi op có một **barrier**
và tất cả phải chờ thread chậm nhất. Mỗi token có hàng trăm barrier như vậy. M1 Pro có 6
P-core + 2 E-core, nên với `-t 8` chắc chắn có 2 thread nằm trên E-core chậm, và mọi op đều
chờ chúng. Tệ hơn, 8 thread chiếm **hết** core, nên khi VS Code hay một daemon macOS cần CPU,
OS phải tạm dừng một worker thread. Trong lúc đó 7 thread kia spin-wait ở barrier (tôi thấy
`llama-bench` dùng ~550% CPU mà gần như không ra token). `-t 16` là trường hợp cực đoan:
luôn có 8 thread không được chạy, và lần chạy không xong sau hơn 9 phút. Với `-t 4`, cả 4
thread nằm gọn trên P-core, còn dư core cho OS, nên barrier thoát nhanh. Từ 1 lên 4 thread
chỉ tăng 2.34× (dưới tuyến tính) vì mỗi thread thêm vào cũng thêm chi phí chia việc và
đồng bộ ở barrier.

Khi offload hết lên Metal thì thread gần như không còn ý nghĩa (1.11×), vì CPU chỉ còn dựng
graph, submit command buffer và sampling; phần này gần như đơn luồng. Điều bất ngờ là Metal
tốt nhất (114.7) chỉ nhanh hơn CPU tốt nhất (89.9) **1.28×**. Đây **không** phải do bandwidth:
114.7 tok/s × 0.5 GB ≈ 57 GB/s và CPU ≈ 45 GB/s, đều thấp hơn nhiều so với ~200 GB/s của
M1 Pro. Với model 0.8B, mỗi token chủ yếu tốn **chi phí cố định**: dispatch kernel và đồng bộ
CPU↔GPU sau mỗi bước, cộng với các matmul nhỏ không đủ lớn để lấp đầy GPU. Vì vậy decode ở
đây chỉ bị chặn *một phần* bởi bandwidth, và cũng vì thế chi phí barrier/đồng bộ (thứ thread
count tác động trực tiếp) mới quan trọng đến vậy. Thay đổi lớn nhất trên máy tôi vì vậy không
phải "bật GPU" mà là **không dùng E-core và không chiếm hết core**.

---

## 6. Bonus  *(optional — tối đa 10 điểm)*

> Bỏ trống nếu không làm. Xem `docs/bonus/README.md`. Đừng làm hết — **một** finding sâu
> ăn điểm hơn năm bảng nông.

**Đã làm:** _<B1 build-compare / B2 sweep nào / B4 challenge nào / B5 lựa chọn nào>_

**Numbers:**

```
before:  <số>
after:   <số>
speedup: <X.Y>×
```

**Điều này nói lên gì mà deck chưa nói:**

_(để trống nếu bạn không làm phần này)_

---

## 7. Điều làm bạn ngạc nhiên nhất  *(optional)*

Continuous batching chỉ cho ~1.3× throughput chứ không phải gần 4×. Dưới load-50, server
decode ~124 tok/s tổng với 3.94 slot bận, so với ~98 tok/s khi chạy single stream. Mỗi step
mất ~32 ms. Model 0.8B quá nhỏ để bị chặn bởi bandwidth, nên chi phí theo từng sequence
vẫn chiếm phần lớn. Thêm nữa, kết quả 2-bit vs 4-bit đảo chiều giữa hai lần chạy bench.

---

## 8. Self-check trước khi push

- [x] `hardware.json` committed
- [x] `models/active.json` committed
- [x] `benchmarks/01-quickstart-results.md` committed (`make bench`)
- [x] `benchmarks/01-tuning-tg128.md` committed (`make tune`)
- [x] `benchmarks/02-server-results.md` committed (`make load-report`)
- [x] `benchmarks/02-server-batching-u50.md` hoặc `-metrics-u50.csv` committed (`make metrics`)
- [x] `benchmarks/locust-10_stats.csv` + `locust-50_stats.csv` committed (`make load-10` / `load-50`)
- [x] `benchmarks/03-integration-results.md` committed (`make pipeline`)
- [x] Mọi section **"required — replace this line"** trong các file `benchmarks/*.md`
      đã được thay bằng nhận xét của bạn
- [x] 5 screenshots trong `submission/screenshots/`
- [x] `make verify` → **exit 0**
- [ ] Repo tên đúng mẫu `K4-L3-DAY20-HoVaTen-MSSV-ModelServing` (xem `docs/SUBMISSION.md`)
- [ ] Repo GitHub ở chế độ **public**
- [ ] Đã push và paste public URL vào VinUni LMS **trước 23:59 (UTC+7) ngày làm lab**
- [x] **Không** commit `models/*.gguf`, `runtime/` hay `.env` (đã có trong `.gitignore`)

**Quan trọng:** repo phải **public** đến khi điểm được công bố. Private → grader không
xem được → 0 điểm.

---

## 9. Khai báo sử dụng AI  *(xem `docs/RULES.md` §3)*

Dùng **Claude Code** (Claude Opus 5.5) trong VS Code để chạy các lệnh `make` của lab
(setup, bench, tune, serve, smoke, load test, metrics, pipeline) và soạn bản nháp phần
nhận xét trong `benchmarks/*.md` cùng REFLECTION này dựa trên số liệu đo trên máy tôi.
Tôi đã đọc lại và hiểu các lập luận. Không có số liệu nào bị sửa tay. Screenshot do tôi tự
chụp từ terminal.
