# Bonus B1 follow-up - interleaved prebuilt vs source build

`Qwen3.5-0.8B-Q4_K_M.gguf` · CPU only (`-ngl 0`) · `-t 4` · 5 rounds,
binaries alternated each round, each point = llama-bench `-r 3` average

| metric | prebuilt mean ± sd | prebuilt range | source mean ± sd | source range | source / prebuilt |
|:--|--:|--:|--:|--:|--:|
| pp512 | 369.4 ± 15.9 | 350.3–387.6 | 367.5 ± 17.7 | 346.0–389.9 | 0.99x |
| tg128 | 79.5 ± 5.0 | 73.0–86.1 | 82.9 ± 6.3 | 71.8–87.5 | 1.04x |

| round | prebuilt pp512 | source pp512 | prebuilt tg128 | source tg128 |
|--:|--:|--:|--:|--:|
| 1 | 375.2 | 346.0 | 73.0 | 85.7 |
| 2 | 350.3 | 353.7 | 79.1 | 71.8 |
| 3 | 378.4 | 389.9 | 76.9 | 85.9 |
| 4 | 355.3 | 371.2 | 82.4 | 83.5 |
| 5 | 387.6 | 376.6 | 86.1 | 87.5 |
