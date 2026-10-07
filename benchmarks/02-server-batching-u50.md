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

**Peak batch width = 3.94 / 4 slots**, `requests_processing = 4`, `requests_deferred`
40–46. Continuous batching đang hoạt động: mỗi decode step phục vụ gần 4 sequence cùng lúc.

**So với effective concurrency 39.1 của `02-server-results.md`:** hai số này **không mâu
thuẫn** vì chúng đo hai thứ khác nhau. 3.94 là số request **đang được tính toán** (bị chặn bởi
`--parallel 4`); 39.1 là số request **đang ở trong hệ thống** (đang tính + đang chờ).
Phần chênh ≈ 35 request đang chờ, cùng cỡ với `requests_deferred` 40–46. Để đo
**utilisation** tôi tin gauge của server; Little's Law cho biết **hàng đợi dài bao nhiêu**.

**Batching lợi bao nhiêu?** Từ CSV: trong 58.8 s server chạy 30.8 decode step/s và sinh
**~124 tok/s tổng**. Single stream ở `make bench` là ~98 tok/s. Vậy batch 4 chỉ cho
**~1.3×**, không phải gần 4×: mỗi step mất ~32 ms so với ~10 ms cho 1 sequence.
Model 0.8B trên Metal không bị chặn bởi bandwidth (0.5 GB × 98 tok/s ≈ 49 GB/s, thấp hơn nhiều so
với ~200 GB/s), nên chi phí theo từng sequence vẫn lớn; thêm vào đó, prefill của các prompt
`long-rag` cũng chen vào cùng step.

> Ghi chú: metrics này được ghi trong lần chạy `make load-50` đầu tiên (cùng server,
> `--parallel 4`). Ở lần chạy lại load-50 để chụp screenshot, `make metrics` không được chạy
> lại, nên `locust-50_stats.csv` và file này đến từ hai lần chạy load-50 khác nhau.
