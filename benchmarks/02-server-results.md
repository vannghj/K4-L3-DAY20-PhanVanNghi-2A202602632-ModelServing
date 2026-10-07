# 02 - Serve: load test + saturation reading

Host `Darwin-arm64` · llama.cpp `b10488` ·
`--parallel 4` · `ctx=2048` · `threads=8` ·
`ngl=99`

| Users | Reqs | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 10 | 140 | 2.37 | 3100 | 4900 | 5600 | 7.6 | 0.0% |
| 50 | 137 | 2.34 | 19000 | 22000 | 35000 | 39.1 | 0.0% |

*Effective concurrency = RPS x average latency (Little's Law) -- how many requests were
really in flight, regardless of how many users locust simulated. It counts queued requests
too, so the occupancy/slot ratio can legitimately exceed 1.0; it is occupancy, not
utilisation. For true slot utilisation use the server's own gauges (`make metrics`).*

## What these two runs say

| Going from 10 to 50 users | |
|:--|--:|
| Offered load | 5x |
| Throughput actually delivered | **0.99x** (20% of linear) |
| P95 latency | **4.49x** |
| Effective concurrency at 50 users | 39.1 vs `--parallel 4` slots (occupancy/slot ratio 9.78) |

**Saturated.** Throughput delivered only 0.99x for 5x the offered load, and effective concurrency (39.1) is at or above all 4 decode slots. Saturation sets in somewhere at or below 50 users; the load you added beyond that point became queue time rather than throughput.

Throughput moved 0.99x while P95 moved 4.49x. That gap is the goodput argument: past saturation you buy throughput by spending latency, and if your SLO is a P95 target then the requests you added are no longer being served within it. (This lab does not fix an SLO number for you -- pick one in your write-up and state how much goodput you keep at it.)

## Your reading

**Server đã bão hoà ngay từ 10 users.** Bằng chứng:
- RPS gần như không đổi: **2.37 → 2.34 (0.99×)** cho 5× offered load. Trần
  throughput của máy này với `--parallel 4` là **~2.3 req/s**.
- P95 phồng **4900 → 22000 ms (4.49×)**, P50 3100 → 19000 ms.
- Effective concurrency (Little's Law, L = λ·W): **7.6** ở 10 users và **39.1** ở 50 users,
  trong khi chỉ có **4 slot**. Ngay ở 10 users đã có request phải xếp hàng.

**Phần latency tăng thêm là queue time, không phải compute time.** Ở 50 users chỉ 4 request
được xử lý cùng lúc (`requests_processing = 4`), còn `requests_deferred` dao động 40–46
(`02-server-batching-u50.md`), cùng cỡ với 39.1 − 4 ≈ 35 request đang chờ theo Little's Law.
Service time của một request khi 4 slot đều bận ≈ 4 / 2.34 ≈ 1.7 s. Latency trung bình
là 16.7 s, nên ≈ 15.0 s (**~90%**) là thời gian **chờ slot**.

**Goodput@SLO:** chọn SLO là P95 ≤ 6 s. Ở 10 users P95 = 4.9 s → gần như toàn bộ
2.37 RPS là goodput. Ở 50 users P95 = 22 s → goodput ≈ 0, dù throughput vẫn là
2.34 RPS.

**Knob đổi trước:** thử `--parallel` 4 → 8 (kèm tăng `LAB_N_CTX` vì ctx bị chia cho các slot),
vì slot là thứ đang cạn (3.94/4). Nhưng tôi kỳ vọng lợi ích giảm dần: batch 4 chỉ cho
~1.3× throughput so với single stream (xem file batching). Thứ thật sự bảo vệ goodput là
**admission control** (giới hạn hàng đợi, trả 429): phần cứng có trần ~2.3 RPS, nên cách duy nhất
giữ P95 trong SLO khi quá tải là **không nhận** request chắc chắn sẽ vi phạm SLO.
