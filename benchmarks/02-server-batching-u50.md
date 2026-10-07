# 02 - Continuous batching under load (u50)

Host `Darwin-arm64` · `--parallel 4` · 30 samples over
60s at 2.0s intervals · raw CSV: `02-server-metrics-u50.csv`

| Gauge | Peak observed |
|:--|--:|
| `n_busy_slots_per_decode` (avg/decode) | 3.94 of 4 slots (99%) |
| `requests_processing` | 4 |
| `requests_deferred` | 46 |
| `kv_cache_usage_ratio` | n/a — not exported by llama.cpp `b10488` |
| `tokens_predicted_total` (final) | 15214 |

Highest sampled value was **3.94 of 4** slots. Note this gauge is llama.cpp's *average* busy slots per decode step, so the number below is the highest average we sampled, not an instantaneous maximum batch width. A peak near 1 means
requests were served one at a time -- either the load was too light to overlap, or
they arrived too far apart. A peak approaching `--parallel` means the scheduler was
genuinely packing concurrent requests into shared decode steps.
`requests_deferred` went above zero: more requests arrived than there were slots, so some waited. That wait is the queue time in your P95.

## Your observation

**Peak batch width = 3.94 / 4 slots (99%)**, `requests_processing = 4` trong suốt 60 s,
`requests_deferred` 40–46. Continuous batching đang hoạt động: mỗi decode step phục vụ
gần 4 sequence cùng lúc.

**So với effective concurrency 39.0 của `02-server-results.md`:** hai số này **không mâu
thuẫn** vì chúng đo hai thứ khác nhau. 3.94 là số request **đang được tính toán** (bị chặn
bởi `--parallel 4`); 39.0 là số request **đang ở trong hệ thống** (đang tính + đang chờ).
39.0 − 3.94 ≈ 35 request chờ, khớp với `requests_deferred` 40–46. Để đo **utilisation**
thì tôi tin gauge của server (3.94); còn Little's Law cho biết **queue dài bao nhiêu**.

**Batching lợi bao nhiêu?** Từ CSV: trong 58.8 s, `n_decode_total` tăng 2088 → 3900
(30.8 step/s) và `tokens_predicted_total` tăng 7937 → 15214 (**~124 tok/s tổng**). Single
stream ở `make bench` là ~80 tok/s. Vậy batch 4 chỉ cho **~1.5×** throughput, không phải
gần 4×: mỗi step 4-sequence mất ~32 ms so với ~12.5 ms của 1 sequence. Điều này cho thấy
model 0.8B trên Metal **không hoàn toàn bị chặn bởi bandwidth** (0.5 GB × 80 tok/s ≈ 40 GB/s,
xa dưới ~200 GB/s của M1 Pro) — phần lớn chi phí là compute/kernel-launch theo từng
sequence, cộng thêm prefill của các prompt `long-rag` chen vào cùng step.
