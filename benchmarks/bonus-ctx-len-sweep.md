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

## Your finding (required -- replace this line)

_At what prompt length does prefill start to dominate your end-to-end latency? Did you see
the quadratic bend, or is your range still linear -- and what does that tell you about how
many retrieved chunks your RAG pipeline can afford?_
