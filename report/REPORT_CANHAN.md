# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Nguyễn Đình Anh Đức
**Nhóm:** G08
**Ngày:** 20/09/2026

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
- Độ tương tự cosine cao nghĩa là hai vector embedding có hướng gần nhau, cho thấy hai đoạn văn có ý nghĩa hoặc ngữ cảnh tương tự, dù chúng không nhất thiết sử dụng cùng từ ngữ

**Ví dụ có độ tương tự CAO:**
- Câu A: Con mèo đang cào cái ghế
- Câu B: Con mèo cào ghế sofa
- Tại sao tương đồng: Hai câu cùng mô tả một con mèo thực hiện hành động cào đồ nội thất

**Ví dụ có độ tương tự THẤP:**
- Câu A: Con mèo đang cào cái ghế
- Câu B: Python là một ngôn ngữ lập trình phổ biến
- Tại sao khác: Hai câu thuộc hai chủ đề và ngữ cảnh hoàn toàn khác nhau

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
- Cosine similarity tập trung vào hướng của vector, tức quan hệ ngữ nghĩa, và ít bị ảnh hưởng bởi độ lớn của vector. Euclidean distance phụ thuộc nhiều vào độ lớn nên hai văn bản có ý nghĩa tương tự vẫn có thể bị đánh giá là xa nhau nếu độ dài hoặc chuẩn vector khác nhau

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
ceil((độ_dài - overlap) / (chunk_size - overlap))
= ceil((10000 - 50) / (500 - 50))
= ceil(9950 / 450)
= ceil(22,11...)
= 23 chunks

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
ceil((10000 - 100) / (500 - 100))
= ceil(9900 / 400)
= ceil(24,75)
= 25 chunks
- Overlap lớn hơn giúp giữ lại ngữ cảnh nằm ở ranh giới giữa hai chunk và giảm nguy cơ mất thông tin liên quan khi truy xuất

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
Dùng regex `(?<=[.!?])(?:[ \t]+|\r?\n+)` để tách tại khoảng trắng hoặc xuống dòng nằm sau `.`, `!`, `?`; positive lookbehind giúp giữ dấu câu ở cuối câu trước. Hàm loại khoảng trắng thừa, trả về `[]` với văn bản rỗng và gom tối đa `max_sentences_per_chunk` câu vào mỗi chunk. Edge case chưa xử lý hoàn toàn là dấu chấm trong chữ viết tắt như `TS.`, `v.v.` và cách viết số thập phân có khoảng trắng sau dấu chấm; chúng có thể bị nhận nhầm là kết thúc câu

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
`chunk` chuẩn hóa đầu vào rồi gọi `_split` với các separator theo thứ tự `"\n\n"`, `"\n"`, `". "`, `" "`, `""`; mỗi mảnh còn dài hơn `chunk_size` tiếp tục được tách đệ quy bằng separator nhỏ hơn. Sau khi tách xuống, thuật toán gom các mảnh nhỏ liền kề trở lại cho đến sát `chunk_size` nhằm giữ ngữ cảnh và tránh tạo nhiều chunk vụn. Ba base case là: văn bản rỗng trả `[]`, mảnh đã đủ ngắn trả `[mảnh]`, và khi hết separator hoặc gặp separator rỗng thì cắt cứng theo `chunk_size`

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
Dùng store in-memory; `add_documents` chuyển từng `Document` thành record gồm nội dung, bản sao metadata, embedding và `doc_id` gốc rồi thêm vào danh sách. `search` tạo embedding cho query và gọi helper `_search_records` để tính dot product với mọi record, sắp xếp score giảm dần và trả tối đa `top_k`; kết quả không chứa vector embedding để tránh output dư thừa

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
Lọc metadata trước khi tính similarity và chọn top-k, vì lọc sau có thể làm các vị trí top-k bị tài liệu sai đối tượng chiếm hết dù vẫn còn record hợp lệ. `delete_document` loại bỏ toàn bộ record có `metadata["doc_id"]` trùng với mã tài liệu cần xóa và trả `True` khi có ít nhất một record bị xóa, ngược lại trả `False`

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
`answer` truy xuất top-k chunk, đánh số từng đoạn `[1]`, `[2]`, `[3]`, gắn nguồn lấy từ metadata rồi chèn chúng vào phần `NGỮ CẢNH` của prompt trước khi gọi `llm_fn`. Prompt yêu cầu chỉ dùng thông tin được cung cấp, trích dẫn số nguồn sau các ý chính và nói rõ không tìm thấy nếu ngữ cảnh không chứa câu trả lời. Nếu store không trả kết quả, hàm trả thông báo ngay và không gọi LLM để tránh chi phí vô ích.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.

### Kết Quả Kiểm Thử (Test Results)

```
(.venv) PS D:\.1_VinAI\Day 7\K4-L3B-Data-Foundations> pytest tests/ -v
======================================================= test session starts =======================================================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- D:\.1_VinAI\Day 7\K4-L3B-Data-Foundations\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\.1_VinAI\Day 7\K4-L3B-Data-Foundations
plugins: anyio-4.15.1
collected 42 items                                                                                                                 

tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED                                        [  2%]
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED                                                 [  4%]
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED                                          [  7%]
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED                                           [  9%]
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED                                                [ 11%]
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED                                [ 14%]
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED                                      [ 16%]
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED                                       [ 19%]
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED                                     [ 21%]
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED                                                       [ 23%]
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED                                       [ 26%]
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED                                                  [ 28%]
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED                                              [ 30%]
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED                                                        [ 33%]
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED                               [ 35%]
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED                                   [ 38%]
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED                             [ 40%]
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED                                   [ 42%]
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED                                                       [ 45%]
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED                                         [ 47%]
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED                                           [ 50%]
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED                                                 [ 52%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED                                      [ 54%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED                                        [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED                            [ 59%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED                                         [ 61%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED                                                  [ 64%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED                                                 [ 66%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED                                            [ 69%]
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED                                        [ 71%]
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED                                   [ 73%]
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED                                       [ 76%]
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED                                             [ 78%]
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED                                       [ 80%]
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED                    [ 83%]
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED                                  [ 85%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED                                 [ 88%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED                     [ 90%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED                                [ 92%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED                         [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED               [ 97%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED                   [100%]

======================================================= 42 passed in 0.08s ========================================================
```

**Số lượng bài test vượt qua (pass):** 42 / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Người mua có thể gửi yêu cầu trả hàng trong vòng 15 ngày | Khách hàng có tối đa mười lăm ngày để yêu cầu hoàn tiền sau khi giao hàng | cao | 0.4858 | Không |
| 2 | Người mua phải thanh toán trước phí vận chuyển hoàn trả | Người mua không phải thanh toán phí vận chuyển hoàn trả | thấp | 0.8686 | Không |
| 3 | Người bán phải phản hồi yêu cầu trong hai ngày | Người mua phải gửi yêu cầu trong vòng mười lăm ngày | thấp | 0.6233 | Không |
| 4 | Hãy quay video khi đóng gói sản phẩm hoàn trả | Cần ghi hình quá trình chuẩn bị kiện hàng gửi lại | cao | 0.3698 | Không |
| 5 | Shopee hoàn tiền về thẻ tín dụng trong 7–14 ngày | Python là một ngôn ngữ lập trình phổ biến. | thấp | 0.2364 | Có |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
Cặp 2: Hai câu mang ý nghĩa trái ngược do từ "không" nhưng đạt similarity 0.8686 vì gần như toàn bộ từ vựng giống nhau. Ngược lại, các câu diễn đạt cùng ý bằng từ ngữ khác nhau lại có điểm thấp hơn. Điều này cho thấy model chủ yếu đo mức độ trùng từ và bigram, chưa biểu diễn quan hệ ngữ nghĩa tốt như semantic embedding

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân của bạn trong gói `src`. **5 câu hỏi này phải trùng với các thành viên cùng nhóm** (xem `REPORT_NHOM.md`).

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Thực phẩm tươi sống và đông lạnh phải gửi yêu cầu trả hàng/hoàn tiền trong bao lâu? | `shopee-return-refund-policy-buyer#0`: thời hạn gửi yêu cầu của Người Mua, có quy định riêng cho thực phẩm tươi sống và đông lạnh. | 0.4737 | Có — evidence ở top-1 | Trong vòng 24 giờ kể từ khi đơn hàng được cập nhật giao hàng thành công. |
| 2 | Sau khi Shopee chấp nhận hoàn tiền, thẻ tín dụng hoặc ghi nợ nhận tiền trong bao lâu? | `refund-methods-and-timing#0`: bảng phương thức nhận hoàn tiền và thời gian xử lý đối với thẻ tín dụng/ghi nợ. | 0.3580 | Có — evidence ở top-1 | Từ 7 đến 14 ngày làm việc, tùy theo ngân hàng. |
| 3 | Nếu tự sắp xếp gửi hàng hoàn trả thì người mua có phải trả phí trước không? | `shopee-return-refund-policy-buyer#2`: yêu cầu và chi phí liên quan đến việc đóng gói, gửi sản phẩm hoàn trả. | 0.3602 | Có — evidence ở top-1; top-2 bổ sung thời gian hoàn phí | Có. Người mua thanh toán phí trước; Shopee hỗ trợ hoàn phí trong 3–5 ngày làm việc nếu đủ điều kiện. |
| 4 | Người mua chưa nhận được hàng thì cần cung cấp bằng chứng gì? | `return-refund-evidence#1`: trường hợp chưa nhận được hàng không cần cung cấp bằng chứng và được xử lý theo dữ liệu theo dõi đơn. | 0.4408 | Có — evidence ở top-1 | Không cần cung cấp bằng chứng; Shopee tự động xử lý dựa trên hệ thống theo dõi đơn hàng. |
| 5 | Khi đóng gói hàng hoàn trả, người mua cần quay video và gửi kèm những gì? | `shopee-return-refund-policy-buyer#2`: yêu cầu quay video/chụp ảnh khi đóng gói; chunk chứa đầy đủ danh sách nằm ở top-2 (`pack-return-parcel#1`). | 0.3740 | Liên quan một phần — evidence đầy đủ ở top-2 | Quay video quá trình đóng gói và gửi đủ hộp của nhà sản xuất, giấy tờ, phụ kiện, quà tặng đi kèm nếu có. |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 5 / 5

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
Chia theo ranh giới câu giúp giữ bằng chứng trọn vẹn hơn: chiến lược `by_sentences` đạt Hit@3 100% và 9/10, cao hơn `fixed_size` và `recursive` cùng đạt 6/10. Tuy nhiên, chiến lược này tạo chunk có độ dài không đồng đều và chunk dài nhất tới 2.492 ký tự, nên cần kết hợp thêm giới hạn kích thước hoặc fallback recursive để cân bằng giữa tính mạch lạc và độ chính xác truy xuất

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 7 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 28 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 3 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 9 / 10 |
| **Tổng phần cá nhân** | 52**/ 60** |
