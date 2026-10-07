# Bonus - GPU offload sweep

Host `Darwin-arm64` · backend(s) `apple_metal` ·
llama.cpp `b10488` · `threads=4` · metric `tg128`

| -ngl | tg128 (tok/s) | vs -ngl 0 | vs best |
|:--|--:|--:|--:|
| 0 | 48.4 | 1.00x | 44% |
| 8 | 57.2 | 1.18x | 52% |
| 16 | 83.7 | 1.73x | 76% |
| 24 | 106.2 | 2.19x | 97% |
| 32 | 104.8 | 2.17x | 95% |
| 99 | 109.8 | 2.27x | 100% |

Best: `-ngl 99` at 109.8 tok/s
-- 2.27x faster than CPU-only.

Where the curve flattens tells you the model ran out of layers to move. Where it
*peaks below* full offload tells you something did not fit and the accelerator
started paying to fetch weights it could not hold.

## Your finding

**Full offload là tốt nhất, và curve đi ngang từ `-ngl 24`.** Qwen3.5 0.8B có đúng **24 block**
(`qwen35.block_count = 24` trong log), nên từ `-ngl 24` trở lên đã offload hết: 106.2 / 104.8 /
109.8 tok/s chỉ khác nhau trong mức nhiễu. Không có điểm peak ở offload một phần, vì toàn bộ model
(0.5 GB) nằm gọn trong ~12 GB GPU có thể dùng, và trên Apple Silicon CPU với GPU dùng **chung
unified memory**: không có PCIe, nên offload không tốn chi phí chép weight qua bus.

**Lưu ý về điểm `-ngl 0` = 48.4 tok/s:** đây là một **outlier** (lần chạy đầu của sweep, máy còn
lạnh). Các lần đo khác cùng `-t 4` CPU-only cho 79–86 tok/s. Tôi đo lại xen kẽ 3 vòng bằng
`llama-bench -t 4 -n 128 -r 3`:

| vòng | `-ngl 0` (CPU) | `-ngl 99` (Metal) |
|--:|--:|--:|
| 1 | 79.0 | 111.3 |
| 2 | 84.6 | 114.8 |
| 3 | 85.3 | 115.2 |
| **mean** | **83.0** | **113.8** |

Speedup thật của offload là **1.37×**, không phải 2.27× như bảng sweep. Lý do speedup nhỏ (so với
kỳ vọng "GPU nhanh hơn nhiều lần"): ở 113.8 tok/s × 0.5 GB ≈ 57 GB/s, chưa tới 1/3 bandwidth
~200 GB/s của M1 Pro. Decode của model 0.8B bị chặn bởi **chi phí cố định mỗi token** (dispatch
kernel cho 24 layer, đồng bộ CPU↔GPU, sampling), không phải bởi bandwidth hay FLOPs, nên GPU chỉ
giảm được phần tính toán. Curve tăng mạnh nhất từ 8 → 24 layer: mỗi layer chuyển sang GPU bớt
được một đoạn matmul trên CPU.
