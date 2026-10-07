# Bonus B1 - Prebuilt vs source build

Host `Darwin-arm64` · CPU `Apple M1 Pro`
Vector extensions detected: NEON
llama.cpp `b10488` both sides · `threads=4` ·
**both pinned to `ngl=0`** so this isolates the compiler ·
metric `tg128`, 3 repetitions

| Binary | Built for | tg128 (tok/s) | Relative |
|:--|--:|--:|--:|
| prebuilt release | runtime CPU dispatch | 78.8 | 1.00x |
| your source build | this CPU (`-DGGML_NATIVE=ON`) | 84.6 | 1.07x |

On this machine, the source build is **1.07x faster**.

before: 78.8 tok/s (prebuilt release)
after:  84.6 tok/s (source build, -DGGML_NATIVE=ON)
speedup: 1.07x

Same source revision, same model, same backend, same `-ngl` -- the only difference
is what the compiler was allowed to assume about the CPU.


### Separately: what GPU offload is worth on the same binary

`tg128` on the source build at `-ngl 99` instead of `-ngl 0`:

| Source build | tg128 (tok/s) | vs its own CPU run |
|:--|--:|--:|
| `-ngl 0` (CPU) | 84.6 | 1.00x |
| `-ngl 99` (offloaded to MTL0: Apple M1 Pro (12124 MiB, 12123 MiB free)) | 113.5 | 1.34x |

This number is **not** part of the B1 comparison above -- it is a different knob.
Reporting it separately is the point: a compiler flag and an accelerator are not
interchangeable explanations for a speedup.


## Your explanation

**Kết luận: không có speedup thật từ việc tự compile.** Lần `make compare-builds` này cho 1.07×
(78.8 → 84.6 tok/s, chạy với `LAB_N_THREADS=4` vì `-t 8` CPU-only bị sụp trên máy này, xem
`01-tuning-tg128-cpu.md`). Nhưng mỗi binary chỉ được chạy một lần, liền nhau. Khi tôi chạy xen kẽ
hai binary 5 vòng (`bonus/challenges/b1-interleaved.py` → `bonus-b1-interleaved.md`):

| metric | prebuilt | source build | tỉ lệ |
|:--|--:|--:|--:|
| tg128 (decode) | 79.5 ± 5.0 | 82.9 ± 6.3 | 1.04× |
| pp512 (prefill) | 369.4 ± 15.9 | 367.5 ± 17.7 | 0.99× |

Mức chênh nhỏ hơn độ lệch chuẩn giữa các vòng, và khoảng giá trị của hai binary chồng lên nhau
hoàn toàn (tg128: 73.0–86.1 so với 71.8–87.5). Vậy 1.07× ở trên chỉ là nhiễu.

**Vì sao không có khác biệt:** CPU này chỉ có **NEON** (ARMv8.5; M1 không có SVE và không có
i8mm, M2 mới có i8mm). Bản prebuilt `macos-arm64` vốn đã được build riêng cho Apple Silicon
với NEON + dot-product, nên `-DGGML_NATIVE=ON` không mở khoá thêm instruction nào. Trên x86 thì
khác: bản prebuilt phải chạy được trên CPU chỉ có AVX2, nên build native với AVX-512 mới có
chênh lệch thật. Trên Mac, "build cho CPU của bạn" và "bản phát hành" gần như là cùng một target.

**GPU offload trên cùng binary** (phần dưới report): `-ngl 0` 84.6 → `-ngl 99` 113.5 tok/s
(1.34×). Đó là một knob khác (accelerator), không phải compiler, và là speedup thật duy nhất
trong B1. Tôi dùng nó cho B3 sau khi đo lặp (xem `bonus-gpu-offload-sweep.md`).
