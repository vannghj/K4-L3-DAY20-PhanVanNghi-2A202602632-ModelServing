# Bonus C2 - KV cache quantization

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · llama.cpp `b10488` · `ngl=99`
`--ctx-size 32768` · `--parallel 1` · `-fa on` for every row · temperature 0 ·
speed = median of 3 runs on a 4993-token prompt

| KV type (K+V) | KV cache (MiB) | RSS (MB) | Prefill ~4k tok (tok/s) | Decode (tok/s) | Eval (/10) |
|:--|--:|--:|--:|--:|--:|
| f16 | 384.00 | 1048 | 1844 | 79.2 | 9 |
| q8_0 | 204.00 | 896 | 1652 | 57.9 | 9 |
| q4_0 | 108.00 | 801 | 1684 | 58.8 | 9 |

Eval = 4 arithmetic + 3 JSON extraction + 3 needle-in-a-~4k-token-context, auto-graded.

Failures:
- `f16`: arith `Compute 37*24.` -> `80`
- `q8_0`: arith `Compute 37*24.` -> `80`
- `q4_0`: arith `Compute 37*24.` -> `86`

KV cache lines from the server log:

```
f16:
    0.01.113.317 I llama_kv_cache: size =  384.00 MiB ( 32768 cells,   6 layers,  1/1 seqs), K (f16):  192.00 MiB, V (f16):  192.00 MiB
    0.01.114.860 I llama_memory_recurrent: size =   19.27 MiB (     1 cells,  24 layers,  1 seqs  0 rs_seq), R (f32):    1.27 MiB, S (f32):   18.00 MiB
q8_0:
    0.00.876.812 I llama_kv_cache: size =  204.00 MiB ( 32768 cells,   6 layers,  1/1 seqs), K (q8_0):  102.00 MiB, V (q8_0):  102.00 MiB
    0.00.878.785 I llama_memory_recurrent: size =   19.27 MiB (     1 cells,  24 layers,  1 seqs  0 rs_seq), R (f32):    1.27 MiB, S (f32):   18.00 MiB
q4_0:
    0.00.801.279 I llama_kv_cache: size =  108.00 MiB ( 32768 cells,   6 layers,  1/1 seqs), K (q4_0):   54.00 MiB, V (q4_0):   54.00 MiB
    0.00.802.811 I llama_memory_recurrent: size =   19.27 MiB (     1 cells,  24 layers,  1 seqs  0 rs_seq), R (f32):    1.27 MiB, S (f32):   18.00 MiB
```

## Your explanation

**Thiết lập:** cùng model Q4_K_M, cùng server (`--ctx-size 32768`, `--parallel 1`, `-fa on` cho
cả ba hàng để so sánh công bằng, vì quantize V cần flash attention). Chỉ đổi `-ctk/-ctv`.

**Bộ nhớ: tiết kiệm đúng như lý thuyết, nhưng nhỏ hơn kỳ vọng.** KV cache 384 → 204 MiB (q8_0,
−47%) → 108 MiB (q4_0, −72%); RSS 1048 → 896 → 801 MB. Điểm bất ngờ là log cho thấy KV cache
chỉ có **6 layer** (`32768 cells, 6 layers`): Qwen3.5 là kiến trúc **hybrid**, chỉ 1/4 số layer
(`full_attention_interval = 4`) là attention có KV cache; 18 layer còn lại là recurrent với state
**cố định 19.27 MiB**, không lớn lên theo context. Kiến trúc này đã làm phần lớn việc mà "FP8 KV
cache" trong deck nhắm tới: với một model dense 24 layer, KV f16 ở 32k context sẽ là ~1.5 GB thay
vì 384 MiB.

**Bộ nhớ theo `--ctx-size`** (chỉ khởi động server, không chạy eval; RSS đo sau khi load):

| KV type | ctx | KV cache (MiB) | recurrent state (MiB) | RSS (MB) |
|:--|--:|--:|--:|--:|
| f16 | 4096 | 48.00 | 19.27 | 697 |
| f16 | 16384 | 192.00 | 19.27 | 859 |
| f16 | 32768 | 384.00 | 19.27 | 1052 |
| f16 | 65536 | 768.00 | 19.27 | 1437 |
| q8_0 | 4096 | 25.50 | 19.27 | 694 |
| q8_0 | 16384 | 102.00 | 19.27 | 771 |
| q8_0 | 32768 | 204.00 | 19.27 | 874 |
| q8_0 | 65536 | 408.00 | 19.27 | 1078 |

KV cache tăng **tuyến tính** theo context (f16: 48 → 768 MiB khi ctx tăng 16×, tức 12 KiB/token
cho 6 layer attention), còn recurrent state đứng yên ở **19.27 MiB** ở mọi kích thước. RSS tăng
theo đúng phần KV: 697 → 1437 MB (f16), 694 → 1078 MB (q8_0). Ở 64k context, q8_0 tiết kiệm
360 MiB KV / 359 MB RSS.

**Latency: quantize KV làm decode chậm hơn 27%.** Decode 79.2 → 57.9 (q8_0) / 58.8 (q4_0) tok/s;
prefill gần như không đổi (1844 → 1652 / 1684 tok/s). Kết quả này **lặp lại được**: lần chạy C2
đầu tiên (trước khi sửa phần đọc log) cho decode 76.4 / 55.9 / 57.2 tok/s, cũng chậm hơn ~27%. Ở mỗi bước decode, kernel flash attention
trên Metal phải **dequantize toàn bộ K/V** (~5k token × 6 layer) trước khi tính attention. Như các
phần trước đã cho thấy, model 0.8B này **không bị chặn bởi bandwidth**, nên số byte đọc ít hơn
không bù được phần tính toán dequantize thêm. Kiểu đánh đổi này chỉ có lợi khi decode thật sự
memory-bound: model lớn, context dài, nhiều slot song song.

**Chất lượng: không đổi trên eval này.** Cả ba đạt 9/10: tìm đúng cả 3 needle trong context ~5k
token (ở vị trí 15%, 50%, 85%), đúng cả 3 câu trích xuất JSON. Câu sai duy nhất (37×24 = 888) sai ở
**cả f16**, nên đó là giới hạn của model 0.8B chứ không phải do KV cache. q4_0 cho đáp án sai khác
(86 thay vì 80), dấu hiệu nhiễu lượng tử hoá có làm thay đổi output, nhưng eval 10 prompt chưa đủ
để thấy chất lượng giảm có ý nghĩa.

**Tôi sẽ triển khai gì:** trên máy này **giữ f16**. KV chỉ 384 MiB ở 32k context trong 16 GB RAM,
nên tiết kiệm 280 MiB không đáng để mất 27% tốc độ decode. Tôi chỉ bật q8_0 khi bộ nhớ là ràng
buộc thật, ví dụ `--parallel 8` × 32k context (KV ~3 GB ở f16) hoặc khi dùng model dense lớn hơn.
