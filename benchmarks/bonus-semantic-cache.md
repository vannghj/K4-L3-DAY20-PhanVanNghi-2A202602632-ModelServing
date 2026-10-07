# Bonus B5 / C8 — Semantic cache (real embeddings, không offline)

Setup: `make serve` (:8080, Qwen3.5 0.8B Q4_K_M) + `make serve-embed` (:8081, **cùng model chat**
ở chế độ pooling, vì lab không có embedding model riêng) → `make semantic-cache`, rồi chạy lại
`semantic-cache-demo.py --threshold 0.87` và `--threshold 0.90`. 8 prompt; paraphrase thật:
#3, #6 ↔ #1 · #4 ↔ #2 · #8 ↔ #5. #7 là chủ đề mới, không được hit.

| Threshold | Hits | True hit | False hit (sai câu trả lời) | Paraphrase bị miss |
|--:|--:|--|--|--|
| 0.80 | 7/8 (88%) | #3, #6, #4, #8 | **#2, #5, #7** | — |
| 0.87 | 3/8 (38%) | #3, #6, #8 | **0** | #4 (sim 0.85) |
| 0.90 | 2/8 (25%) | #6, #8 | 0 | #3, #4 |

Một cache hit tiết kiệm toàn bộ lời gọi LLM: miss tốn ~850–2200 ms, hit tốn 0 ms.

## Raw output (threshold 0.80)

```
 #  result   sim      ms  prompt
 1  miss    0.00     808  What is goodput at SLO?
 2  HIT     0.86       0  Explain TTFT and TPOT.
 3  HIT     0.89       0  Can you define goodput@SLO?
 4  HIT     0.85       0  What does time to first token mean?
 5  HIT     0.85       0  How does PagedAttention work?
 6  HIT     0.88       0  Tell me what goodput@SLO is.
 7  HIT     0.86       0  What is prefix caching?
 8  HIT     0.85       0  Describe how PagedAttention works.

Hit rate: 7/8 = 88%   (threshold 0.8)
LLM calls saved: 7
```

## Finding

**Mean-pooled hidden state của một model chat 0.8B là một embedder rất kém.** Mọi cặp câu đều
có cosine 0.85–0.89, kể cả các câu **không liên quan**: #7 "What is prefix caching?" đạt 0.86
và hit vào câu trả lời về goodput. Ở threshold mặc định 0.80, 3/7 hit là **sai**; cache sẽ trả
câu trả lời sai cho người dùng, và còn tệ hơn là không có cache.

Khoảng phân tách giữa paraphrase thật và câu lạ chỉ ~0.01: #4 (paraphrase thật) = 0.85, còn #7
(câu lạ) = 0.86. Ở 0.87 tôi có 0 false hit nhưng mất #4; không có threshold nào vừa bắt hết
paraphrase vừa không có false hit. Hit rate 88% ở 0.80 vì thế là **con số ảo**. Hit rate trung
thực của embedder này là 38% (0.87), và vẫn quá mong manh để dùng thật.

Kết luận: semantic cache chỉ an toàn khi có **embedding model chuyên dụng** (BGE-M3,
Qwen3-Embedding) với khoảng cách lớn giữa paraphrase và câu lạ. Threshold phải được chọn theo
false-hit rate đo được trên dữ liệu thật, không theo hit rate.

## Chẩn đoán theo yêu cầu C8

- **False hit:** #7 *"What is prefix caching?"*, một chủ đề mới, có similarity **0.86** và hit vào
  câu trả lời đã cache (ở threshold 0.80). #2 *"Explain TTFT and TPOT."* (0.86) và #5 *"How does
  PagedAttention work?"* (0.85) cũng là false hit: lúc đó cache chưa có câu nào cùng chủ đề.
- **False miss:** #4 *"What does time to first token mean?"* là paraphrase thật của #2 nhưng
  chỉ đạt **0.85**, và bị miss ở threshold 0.87.
- **Không threshold nào sửa được cả hai:** muốn #4 hit thì threshold phải ≤ 0.85, nhưng khi đó
  #7 (0.86) chắc chắn hit sai. Muốn chặn #7 thì threshold phải > 0.86, và khi đó #4 bị miss. Câu
  lạ lại có điểm **cao hơn** paraphrase thật, nên mọi threshold đều sai ít nhất một trường hợp.

**Vì sao decoder là encoder kém:** model chat được train để dự đoán **token kế tiếp**. Hidden
state của nó mã hoá "câu này sẽ tiếp tục thế nào", tức chủ yếu là định dạng câu hỏi (*"What
is…?"*, *"Explain…"*) và ngôn ngữ, chứ không phải nghĩa của cả câu. Mean-pooling qua mọi token
lại làm loãng thêm, vì các token chung (what, is, the, ?) chiếm phần lớn vector. Kết quả là mọi
câu hỏi tiếng Anh ngắn đều dồn vào một vùng hẹp (0.85–0.89). Embedding model chuyên dụng
(Qwen3-Embedding, BGE-M3, EmbeddingGemma) được train bằng **contrastive learning**: kéo các cặp
paraphrase lại gần nhau và đẩy các cặp khác nghĩa ra xa. Vì thế khoảng cách giữa "cùng nghĩa" và
"khác nghĩa" rộng, và threshold mới có ý nghĩa.

**Rủi ro bảo mật:** một semantic cache (hoặc prefix/KV cache) dùng chung giữa nhiều người dùng
là một **timing side channel**. Hit trả về trong 0 ms còn miss mất ~1 s, nên kẻ tấn công có thể
dò xem người khác đã hỏi một câu gần giống hay chưa. Hệ thống production phải **salt/partition
cache theo tenant**. Ngoài ra, false hit như #7 còn trả nhầm câu trả lời của người này cho người
khác, tức là rò rỉ dữ liệu trực tiếp.
