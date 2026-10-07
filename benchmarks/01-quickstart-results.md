# 01 - Measure: latency baseline

Model `Qwen3.5 0.8B` · host `Darwin-arm64` · llama.cpp `b10488`
Settings: `threads=8` `ngl=99` `ctx=2048`
`max_tokens=64` · warm-up discarded
Completed requests: `Q4_K_M` 10/10 · `UD-Q2_K_XL` 10/10

| Quantization | Size (GB) | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode (tok/s) |
|:--|--:|--:|--:|--:|--:|--:|
| Q4_K_M | 0.50 | 2079 | 61 / 89 | 10.2 / 10.8 | 691 / 728 / 728 | 98.0 |
| UD-Q2_K_XL | 0.39 | 2048 | 67 / 94 | 12.9 / 14.6 | 868 / 989 / 989 | 77.7 |

- **TTFT** = prefill. Short prompts keep it small; long-context RAG is where it explodes.
- **TPOT** = per-output-token decode cost, bounded by memory bandwidth. `decode tok/s = 1000 / TPOT_p50`.
- `UD-Q2_K_XL` decodes **1.26x SLOWER** than `Q4_K_M` here, despite being 0.11 GB smaller. That is a real result, not a mistake: fewer bits only buys speed when decode is limited by memory bandwidth. On a machine that is compute-limited instead — few cores, no GPU offload — the extra dequantization work of a heavily-quantized format can cost more than the bytes it saves. Say which case yours is.

## Your observation

**Tốc độ: kết quả không ổn định giữa hai lần chạy.** Lần chạy này (bảng trên) Q4_K_M decode
98.0 tok/s, UD-Q2_K_XL 77.7 tok/s, tức 2-bit **chậm hơn 1.26×** (TPOT P50 12.9 vs 10.2 ms).
Lần chạy trước đó trên cùng máy (commit `ed7f3ea`) cho kết quả ngược lại: Q2 95.7 vs Q4
79.8 tok/s (Q2 nhanh hơn 1.20×). Chênh lệch giữa hai quant (~20%) cùng cỡ với nhiễu giữa
các lần chạy, nên tôi **không** kết luận được 2-bit nhanh hơn trên máy này.

Lý do: với model 0.8B trên Metal, decode **không** bị chặn bởi bandwidth
(0.5 GB × 98 tok/s ≈ 49 GB/s, thấp hơn nhiều so với ~200 GB/s của M1 Pro). Phần lớn chi
phí mỗi token là cố định (dispatch kernel, đồng bộ CPU↔GPU). Vì thế 0.11 GB ít hơn gần
như không tiết kiệm được gì, còn format Q2_K lại cần **dequantize phức tạp hơn** — đúng như
cảnh báo của script. Kết quả còn phụ thuộc vào máy đang bận gì khác lúc đo.

**Chất lượng:** hỏi cùng một câu (temperature 0) trên cả hai server
(`make serve` ở :8080 và `serve.py --compare --port 8090`): *"Explain in 3 sentences why
LLM decode speed is limited by memory bandwidth rather than FLOPs. Then compute 17*23."*
- Q4_K_M: giải thích đúng hướng và tính **17*23 = 391 (đúng)**.
- UD-Q2_K_XL: nhầm bandwidth thành *capacity* và tính **17*23 = 381 (sai)**.

**Có đáng không?** **Không.** 2-bit không nhanh hơn một cách đáng tin cậy, chất lượng lại
kém rõ rệt, và máy có 16 GB RAM nên 0.11 GB tiết kiệm được không giải quyết vấn đề gì.
2-bit chỉ đáng khi model không vừa RAM ở 4-bit.
