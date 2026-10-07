# Bonus - Context-length sweep (prefill cost)

Host `Darwin-arm64` · llama.cpp `b10488` ·
`threads=8` `ngl=99` · RAM 16.0 GB

| Prompt tokens | Prefill (tok/s) | TTFT contribution (ms) | vs linear scaling |
|:--|--:|--:|--:|
| 256 | 1304.8 | 196.2 | 1.00x |
| 1024 | 1398.0 | 732.5 | 0.93x |
| 2048 | 1722.1 | 1189.2 | 0.76x |
| 4096 | 1916.2 | 2137.5 | 0.68x |
| 8192 | 1752.3 | 4674.9 | 0.74x |

At 8192 tokens, prefill costs **4675 ms**, which is
**0.74x** linear scaling -- so on this hardware, over this range, prefill is
still growing **roughly linearly**, not quadratically.

That is the correct finding, not a failed experiment. Attention is O(N^2), but it is only
one term: the per-layer linear projections and MLP are O(N), and on a 2B-class model at
short prompts they dominate. The quadratic term only overtakes them once N gets large
enough. Your prefill cost is currently bounded by throughput, not by sequence length.

To find where it *does* bend, extend the grid:

```bash
.venv/bin/python bonus/sweeps/ctx-len-sweep.py --grid 1024,4096,8192,16384,32768
```

Watch the "vs linear" column: the first row that climbs meaningfully above 1.0 is where
attention starts to matter on your machine. Report that crossover point.

Either way, this is the number to remember when someone proposes stuffing more retrieved
context into a RAG prompt "because the context window allows it". Prefill is paid in full,
on every request, before the first token appears.

## Your explanation

**Prefill throughput tăng rồi mới giảm.** 1304.8 tok/s ở 256 token → 1916.2 tok/s ở 4096 token,
rồi giảm còn 1752.3 tok/s ở 8192. Prompt ngắn **không lấp đầy GPU**: matmul của prefill chỉ đủ
lớn để dùng hết compute khi batch token đủ dài, nên tok/s tăng theo độ dài prompt. Sau 4096,
phần attention O(n²) (mỗi token mới phải nhìn lại toàn bộ token trước nó) bắt đầu lộ ra, nên
throughput giảm. Đó là điểm bắt đầu của chỗ uốn bậc hai. Trong khoảng đã đo, TTFT vẫn gần
tuyến tính (0.74× so với linear vì GPU được dùng hiệu quả hơn).

**Khi nào prefill chiếm ưu thế:** TTFT 196 ms ở 256 token → 1189 ms ở 2048 → **4675 ms ở 8192**.
Pipeline ở `03-integration-results.md` chỉ có 113–151 token prompt (prefill ~100–475 ms) và
decode ~0.8–2 s. Từ ~2–4k token context trở lên, prefill sẽ **lớn hơn cả decode**.

**RAG gánh được bao nhiêu chunk:** với budget TTFT ≈ 1 s, tối đa ~2000 token context, tức
khoảng 6 chunk × 300 token. Ở 8192 token, chỉ riêng TTFT đã ~4.7 s. Đây là lý do top-k nhỏ,
rerank, và prefix/KV caching cho system prompt quan trọng với RAG.
