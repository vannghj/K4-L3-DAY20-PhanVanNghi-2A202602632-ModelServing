# 02 - Serve: load test + saturation reading

Host `Darwin-arm64` · llama.cpp `b10488` ·
`--parallel 4` · `ctx=2048` · `threads=8` ·
`ngl=99`

| Users | Reqs | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 10 | 123 | 2.17 | 3500 | 5200 | 5500 | 7.9 | 0.0% |
| 50 | 131 | 2.23 | 21000 | 23000 | 24000 | 39.0 | 0.0% |

*Effective concurrency = RPS x average latency (Little's Law) -- how many requests were
really in flight, regardless of how many users locust simulated. It counts queued requests
too, so the occupancy/slot ratio can legitimately exceed 1.0; it is occupancy, not
utilisation. For true slot utilisation use the server's own gauges (`make metrics`).*

## What these two runs say

| Going from 10 to 50 users | |
|:--|--:|
| Offered load | 5x |
| Throughput actually delivered | **1.03x** (21% of linear) |
| P95 latency | **4.42x** |
| Effective concurrency at 50 users | 39.0 vs `--parallel 4` slots (occupancy/slot ratio 9.75) |

**Saturated.** Throughput delivered only 1.03x for 5x the offered load, and effective concurrency (39.0) is at or above all 4 decode slots. Saturation sets in somewhere at or below 50 users; the load you added beyond that point became queue time rather than throughput.

Throughput moved 1.03x while P95 moved 4.42x. That gap is the goodput argument: past saturation you buy throughput by spending latency, and if your SLO is a P95 target then the requests you added are no longer being served within it. (This lab does not fix an SLO number for you -- pick one in your write-up and state how much goodput you keep at it.)

## Your reading

**Server đã bão hoà ngay từ 10 users.** Bằng chứng:
- RPS gần như không đổi: **2.17 → 2.23 (1.03×)** cho 5× offered load. Trần throughput của
  máy này với `--parallel 4` là **~2.2 req/s**.
- P95 phồng **5200 → 23000 ms (4.42×)**, P50 3500 → 21000 ms.
- Effective concurrency (Little's Law, L = λ·W): **7.9** ở 10 users và **39.0** ở 50 users,
  trong khi chỉ có **4 slot**. Ngay ở 10 users đã có ~4 request phải xếp hàng.

**Phần latency tăng thêm là queue time, không phải compute time.** Ở 50 users chỉ 4 request
được xử lý cùng lúc (`requests_processing = 4`), còn `requests_deferred` dao động 40–46
(`02-server-batching-u50.md`), khớp với 39 − 4 ≈ 35 request đang chờ theo Little's Law.
Service time của một request trong batch 4 slot ≈ 4 / 2.23 ≈ 1.8 s; queue time ≈ 35 / 2.23
≈ 15.7 s. Vậy ~85% của P50 = 21 s là thời gian **chờ slot**.

**Goodput@SLO:** chọn SLO là P95 ≤ 6 s. Ở 10 users P95 = 5.2 s → gần như toàn bộ 2.17 RPS là
goodput. Ở 50 users P95 = 23 s → goodput ≈ 0, dù throughput vẫn là 2.23 RPS.

**Knob đổi trước:** `--parallel` (4 → 8, kèm tăng `LAB_N_CTX` vì ctx 2048 bị chia cho các
slot). Lý do: `n_busy_slots_per_decode` đạt 3.94/4 → **slot là thứ đang cạn**, và mỗi decode
step đọc weight một lần cho cả batch, nên batch rộng hơn sẽ khấu hao lần đọc đó cho nhiều
token hơn. Sau đó thêm **admission control** (giới hạn hàng đợi, trả 429) để bảo vệ P95:
phần cứng có trần, nên cách duy nhất giữ goodput khi quá tải là **không nhận** request sẽ
vi phạm SLO.
