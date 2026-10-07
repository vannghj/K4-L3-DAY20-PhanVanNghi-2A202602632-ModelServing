# 01 - Tune: thread-count sweep

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · host `Darwin-arm64` · llama.cpp `b10488`
CPU: **8 physical · 8 logical** cores · `ngl=99` · metric `tg128`

| threads (-t) | tg128 (tok/s) | vs best |
|:--|--:|--:|
| 1 | 113.3 | 99% |
| 4 | 114.7 | 100% |
| 8 | 103.1 | 90% |
| 16 | 88.9 | 78% |

**Best**: `-t 4` at 114.7 tok/s
**Slowest tested**: `-t 16` at 88.9 tok/s (1.29x spread)
**Against the physical-core default** (`-t 8`, 103.1 tok/s): 1.11x

Use this in your run:

```bash
LAB_N_THREADS=4 make bench
```

## Your explanation

Run này dùng `ngl=99`: **toàn bộ layer chạy trên GPU qua Metal**. Curve gần như **phẳng**:
`-t 1` = 113.3, `-t 4` = 114.7 tok/s (chênh 1%), rồi **giảm** ở `-t 8` (103.1, −10%) và
`-t 16` (88.9, −22%). Knee ở `-t 4`, không phải ở 8 physical core như deck kỳ vọng.

Lý do: khi offload hết lên GPU, CPU thread không còn làm matmul nữa — chúng chỉ dựng graph,
submit command buffer cho Metal, sampling và tokenize. Phần đó gần như đơn luồng, nên thêm
thread không thêm throughput. Thêm thread còn có hại: các worker thread spin-wait chờ GPU
xong mỗi bước, chiếm core mà thread điều phối Metal cần, và ở `-t 8` chắc chắn có thread
nằm trên 2 E-core (M1 Pro = 6 P-core + 2 E-core). `-t 16` = oversubscription (16 thread / 8
core) nên OS phải context-switch liên tục → chậm nhất.

Kết luận: trên Apple Silicon với Metal, thread count **không phải knob quan trọng** (1.11×
so với mặc định `-t 8`). Để thấy hiệu ứng thread thật, tôi chạy thêm bản CPU-only
(`LAB_N_GPU_LAYERS=0 make tune` → `01-tuning-tg128-cpu.md`), và ở đó khác biệt là 7.7×.
