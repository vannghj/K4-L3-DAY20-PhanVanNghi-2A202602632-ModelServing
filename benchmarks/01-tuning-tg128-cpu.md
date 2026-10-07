# 01 - Tune: thread-count sweep

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · host `Darwin-arm64` · llama.cpp `b10488`
CPU: **8 physical · 8 logical** cores · `ngl=0` · metric `tg128`

| threads (-t) | tg128 (tok/s) | vs best |
|:--|--:|--:|
| 1 | 38.4 | 43% |
| 4 | 89.9 | 100% |
| 8 | 11.7 | 13% |
| 16 | 0.0 | 0% |

**Best**: `-t 4` at 89.9 tok/s
**Slowest tested**: `-t 8` at 11.7 tok/s (7.72x spread)
**Against the physical-core default** (`-t 8`, 11.7 tok/s): 7.72x

Use this in your run:

```bash
LAB_N_THREADS=4 make bench
```

## Your explanation

> **Ghi chú về cách chạy:** file này sinh ra bởi `LAB_N_GPU_LAYERS=0 make tune` (CPU-only),
> rồi đổi tên thành `01-tuning-tg128-cpu.md` để không ghi đè bản Metal. Điểm `-t 16` ghi
> **0.0 vì tôi đã kill tay**: `llama-bench -t 16 -ngl 0` chạy **hơn 9 phút** (CPU ~550%)
> mà không xong 2 lần × 128 token, trong khi `-t 4` chỉ mất vài giây. Đó không phải
> số đo throughput mà là bằng chứng của một sự sụp đổ hiệu năng (xem bên dưới).

**Curve:** `-t 1` 38.4 → `-t 4` **89.9** (best) → `-t 8` **11.7** tok/s → `-t 16` không
hoàn thành. Knee ở **4 thread**, và vượt qua đó hiệu năng **sụp đổ**, không chỉ đi ngang.

**Vì sao 1 → 4 tăng nhưng dưới tuyến tính (2.34× cho 4× thread):** decode đọc ~0.5 GB weight
cho mỗi token. Một core đơn không kéo đủ bandwidth; 4 P-core kéo được nhiều hơn nhưng bắt
đầu đụng giới hạn bandwidth mà cụm CPU lấy được từ bộ nhớ (89.9 tok/s × 0.5 GB ≈ 45 GB/s).

**Vì sao 8 thread chậm 7.7× so với 4 (khác kỳ vọng "peak ở physical core count"):**
ggml chia mỗi matmul đều cho N thread rồi **đồng bộ ở barrier sau mỗi op** — hàng trăm
barrier cho mỗi token. Với `-t 8` trên M1 Pro (6P + 2E):
1. Hai thread chắc chắn rơi vào **E-core** (chậm hơn nhiều) → mỗi op phải chờ thread chậm nhất.
2. Dùng **hết cả 8 core** nên bất kỳ process nào khác (VS Code, macOS daemon) chiếm một core
   là có một thread bị deschedule → 7 thread còn lại spin-wait ở barrier cho tới khi nó
   được chạy lại. Mỗi lần trễ như vậy nhân với hàng trăm barrier/token.
3. `-t 16` là trường hợp cực đoan của (2): luôn có 8 thread không được chạy, barrier gần
   như không bao giờ đủ người → chạy hơn 9 phút không xong.

Bài học: số thread tối ưu là **số P-core còn rảnh**, không phải số core logic. Default
`-t 8` của lab là lựa chọn tệ nhất có thể trên máy này.
