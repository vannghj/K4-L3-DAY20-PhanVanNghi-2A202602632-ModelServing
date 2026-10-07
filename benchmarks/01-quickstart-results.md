# 01 - Measure: latency baseline

Model `Qwen3.5 0.8B` · host `Darwin-arm64` · llama.cpp `b10488`
Settings: `threads=8` `ngl=99` `ctx=2048`
`max_tokens=64` · warm-up discarded
Completed requests: `Q4_K_M` 10/10 · `UD-Q2_K_XL` 10/10

| Quantization | Size (GB) | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode (tok/s) |
|:--|--:|--:|--:|--:|--:|--:|
| Q4_K_M | 0.50 | 2088 | 62 / 259 | 12.5 / 15.8 | 848 / 956 / 956 | 79.8 |
| UD-Q2_K_XL | 0.39 | 2031 | 60 / 74 | 10.4 / 11.1 | 722 / 773 / 773 | 95.7 |

- **TTFT** = prefill. Short prompts keep it small; long-context RAG is where it explodes.
- **TPOT** = per-output-token decode cost, bounded by memory bandwidth. `decode tok/s = 1000 / TPOT_p50`.
- `UD-Q2_K_XL` decodes **1.20x faster** than `Q4_K_M` here, for 0.11 GB less on disk.

## Your observation

**Tốc độ:** UD-Q2_K_XL decode 95.7 tok/s so với 79.8 tok/s của Q4_K_M → **nhanh hơn 1.20×**
(TPOT P50 10.4 ms vs 12.5 ms), file nhỏ hơn 0.11 GB (0.39 vs 0.50 GB, −22%). Tỉ lệ speedup
gần đúng với tỉ lệ kích thước: decode bị chặn bởi việc đọc toàn bộ weight cho mỗi token,
nên ít byte hơn → ít thời gian hơn. TTFT P50 gần như bằng nhau (62 vs 60 ms) vì prompt
ngắn; TTFT P95 = 259 ms của Q4 là một outlier đơn lẻ (10 mẫu → P95 ≈ mẫu lớn nhất).

**Chất lượng:** tôi hỏi cùng một câu (temperature 0) trên cả hai server
(`make serve` ở :8080 và `serve.py --compare --port 8090`): *"Explain in 3 sentences why
LLM decode speed is limited by memory bandwidth rather than FLOPs. Then compute 17*23."*
- Q4_K_M: giải thích đúng hướng (bandwidth của bộ nhớ là nút cổ chai) và tính **17*23 = 391 (đúng)**.
- UD-Q2_K_XL: nhầm bandwidth thành *capacity* ("internal state exceeds the available memory
  capacity") và tính **17*23 = 381 (sai)**.

**Có đáng không?** Với model 0.8B thì **không**. 20% tốc độ đổi lấy lỗi số học và lỗi khái
niệm là quá đắt; model 0.8B vốn đã ít "dư thừa" để chịu thêm nhiễu lượng tử hoá 2-bit.
Hơn nữa máy có 16 GB RAM nên 0.11 GB tiết kiệm được không giải quyết vấn đề gì. 2-bit chỉ
đáng khi model **không vừa** RAM ở 4-bit (vd model 7B+ trên máy 8 GB).
