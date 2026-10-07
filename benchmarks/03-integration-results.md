# 03 - Integrate: RAG pipeline run

Host `Darwin-arm64` · llama.cpp `b10488` ·
retrieval backend: **keyword overlap** · 3 queries

| Query | Contexts retrieved | embed (ms) | retrieve (ms) | llm (ms) | total (ms) |
|:--|--:|--:|--:|--:|--:|
| Why is goodput more useful than raw throughp... | goodput, paged, radix | 0.0 | 0.0 | 2206.4 | 2206.4 |
| What problem does PagedAttention actually so... | paged, radix, disagg | 0.0 | 0.0 | 889.8 | 889.9 |
| When does splitting prefill and decode help?... | disagg, radix, batching | 0.0 | 0.0 | 2188.4 | 2188.4 |

Mean per stage (ms): embed **0.0** · retrieve **0.0** ·
llm **1761.5** · total **1761.6**
Dominant stage: **llm** (100% of total)

## Answers returned

**Why is goodput more useful than raw throughput?**

> Based on the context provided, **Goodput** is more useful than raw throughput because it specifically accounts for **SLOs (Service Level Objectives)**.

While raw throughput measures the total requests per second (requests/sec) that pass through a system, Goodput filters out requests that do not meet the targets. This means Goodput only counts requests that met the **TTFT** (Total Time to First Fa

**What problem does PagedAttention actually solve?**

> PagedAttention solves the problem of **internal fragmentation in GPU memory** caused by storing Key-Value (KV) cache entries in non-contiguous pages.

By storing the KV cache in non-contiguous pages, the model can remove this internal fragmentation, which is particularly beneficial for large models where GPU memory is a significant bottleneck.

**When does splitting prefill and decode help?**

> Based on the provided context, splitting prefill and decode helps when **prefill is compute-bound and decode is memory-bandwidth-bound**.

The reasoning is as follows:
1.  **Prefill** is described as "compute-bound," meaning it requires significant processing power.
2.  **Decode** is described as "memory-bandwidth-bound," meaning it requires significant data transfer speed.
3.  By splitting these 


## Which N16-N19 pieces are real

| Day | Piece | Real hay stub |
|---|---|---|
| N16 Cloud/IaC | không có — chạy local trên laptop | **stub** (không dùng) |
| N17 Data pipeline | không có — `TOY_DOCS` hard-code 6 câu | **stub** |
| N18 Lakehouse | không có — Python list trong memory | **stub** |
| N19 Vector + features | keyword overlap thay cho vector search, không có embedding server | **stub** |
| N20 Serving | `llama-server` (Qwen3.5 0.8B Q4_K_M, Metal) | **real** |

**Dominant stage:** llm = **100%** (1761.5 / 1761.6 ms). embed = 0.0 ms vì không có embedding
server (fallback keyword), retrieve = 0.0 ms vì chỉ so khớp từ trên 6 doc. Đúng kỳ vọng —
với stub thì retrieval gần như miễn phí.

Trong llm, **decode chiếm phần lớn chứ không phải prefill**: server timings cho thấy prefill
99–475 ms (113–151 token) còn decode 759–2064 ms (67–144 token). Query 2 nhanh nhất (890 ms)
đơn giản vì model trả lời ngắn nhất (67 token).

**Để giảm latency 2×:** tấn công vào **số token output** — giới hạn `max_tokens` (đang là 200)
và yêu cầu trả lời ngắn trong system prompt; decode ~11–14 ms/token nên cắt 140 → 70 token
tiết kiệm ~1 s. Prompt caching cho system prompt dùng chung chỉ giúp phần prefill (~100 ms),
nên không đủ để đạt 2×. Nếu dùng retrieval thật với context dài hơn thì prefill mới thành
vấn đề.
