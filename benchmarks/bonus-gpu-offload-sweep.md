# Bonus - GPU offload sweep

Host `Darwin-arm64` · backend(s) `apple_metal` ·
llama.cpp `b10488` · `threads=4` · metric `tg128`

| -ngl | tg128 (tok/s) | vs -ngl 0 | vs best |
|:--|--:|--:|--:|
| 0 | 84.6 | 1.00x | 75% |
| 8 | 65.2 | 0.77x | 57% |
| 16 | 73.0 | 0.86x | 64% |
| 24 | 108.4 | 1.28x | 96% |
| 32 | 113.5 | 1.34x | 100% |
| 99 | 104.5 | 1.23x | 92% |

Best: `-ngl 32` at 113.5 tok/s
-- 1.34x faster than CPU-only.

Where the curve flattens tells you the model ran out of layers to move. Where it
*peaks below* full offload tells you something did not fit and the accelerator
started paying to fetch weights it could not hold.

## Your finding

**Tôi chạy sweep này hai lần** (bảng trên là lần 2; cả hai đều `LAB_N_THREADS=4`, `-r 2`):

| -ngl | lần 1 (tok/s) | lần 2 (tok/s) |
|:--|--:|--:|
| 0 | **48.4** | 84.6 |
| 8 | 57.2 | 65.2 |
| 16 | 83.7 | 73.0 |
| 24 | 106.2 | 108.4 |
| 32 | 104.8 | 113.5 |
| 99 | 109.8 | 104.5 |

**Điểm `-ngl 0` = 48.4 ở lần 1 là một outlier đơn lẻ mà tôi chưa giải thích được.** Lần 2 cho
84.6, và mọi lần đo CPU-only `-t 4` khác đều nằm trong 71.8–87.5 tok/s (5 vòng xen kẽ ở
`bonus-b1-interleaved.md`, 3 vòng bên dưới). Vì vậy con số "2.27× so với CPU" của lần 1 là
**phóng đại**. Speedup tôi dùng là con số đo lặp xen kẽ 3 vòng (`llama-bench -t 4 -n 128 -r 3`):

| vòng | `-ngl 0` (CPU) | `-ngl 99` (Metal) |
|--:|--:|--:|
| 1 | 79.0 | 111.3 |
| 2 | 84.6 | 114.8 |
| 3 | 85.3 | 115.2 |
| **mean** | **83.0** | **113.8** |

→ **1.37×**, cùng cỡ với 1.23–1.34× của lần 2 và 1.34× của `make compare-builds`.

**Full offload là tốt nhất; curve đi ngang từ `-ngl 24`.** Qwen3.5 0.8B có đúng **24 block**
(`qwen35.block_count = 24`), nên từ `-ngl 24` trở lên đã offload hết. 104–114 tok/s chỉ khác
nhau trong mức nhiễu. Không có điểm peak ở offload một phần, vì model 0.5 GB nằm gọn trong
~12 GB GPU có thể dùng, và CPU với GPU dùng **chung unified memory** (không có PCIe để chép weight).

**Offload một phần chậm hơn cả CPU-only ở lần 2** (`-ngl 8`: 65.2, `-ngl 16`: 73.0, so với 84.6).
Khi model bị chia đôi, mỗi token phải đi qua các layer trên CPU rồi sang GPU, nên mỗi bước có thêm
một điểm đồng bộ CPU↔GPU (chờ command buffer xong, chuyển activation sang backend kia). Với model
nhỏ thế này, chi phí đồng bộ đó lớn hơn phần compute mà vài layer GPU tiết kiệm được.

**Vì sao full offload chỉ nhanh hơn ~1.37×:** 113.8 tok/s × 0.5 GB ≈ 57 GB/s, chưa tới 1/3
bandwidth ~200 GB/s của M1 Pro. Decode model 0.8B bị chặn bởi **chi phí cố định mỗi token**
(dispatch kernel cho 24 layer, đồng bộ, sampling), không phải bởi bandwidth, nên GPU chỉ cắt
được phần tính toán.
