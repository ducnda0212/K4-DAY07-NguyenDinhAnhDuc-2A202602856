# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** G08
**Thành viên:** Nguyễn Đình Anh Đức, Lê Thanh Trường, Hoàng Văn Dương
**Ngày:** 20/09/2026

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Chính sách Trả hàng / Hoàn tiền của Shopee Việt Nam.

Nhóm chọn chủ đề này vì đây là một miền dữ liệu có tính thực tế cao, nhiều câu hỏi người dùng cần câu trả lời chính xác theo điều kiện, thời hạn, phí vận chuyển và bằng chứng. Tài liệu cũng phù hợp để kiểm thử RAG vì có nhiều đoạn chính sách dài, bảng thời gian hoàn tiền, nhiều đối tượng áp dụng như `buyer`, `seller`, `both`, và nhiều thông tin dễ bị mất nếu chunking không tốt.

### Danh sách tài liệu (Data Inventory)

Corpus chính của nhóm nằm trong `data/shopee-return-refund`, gồm 14 file Markdown được crawl từ Shopee Help Center. Các tài liệu đều có frontmatter metadata gồm `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience`, `category`, `language`, `license_or_permission`.

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Shopee article 188931 | https://help.shopee.vn/portal/4/article/188931 | 2026-09-20 / not-stated | 6,298 | buyer, return-refund-policy, vi |
| 2 | Shopee article 189473 | https://help.shopee.vn/portal/4/article/189473 | 2026-09-20 / not-stated | 3,869 | buyer, return-refund-policy, vi |
| 3 | Shopee article 189477 | https://help.shopee.vn/portal/4/article/189477 | 2026-09-20 / not-stated | 5,903 | buyer, return-shipping-fee, vi |
| 4 | Shopee article 190242 | https://help.shopee.vn/portal/4/article/190242 | 2026-09-20 / not-stated | 8,084 | buyer, return-refund-policy, vi |
| 5 | Shopee article 195504 | https://help.shopee.vn/portal/4/article/195504 | 2026-09-20 / not-stated | 18,726 | buyer, return-refund-policy, vi |
| 6 | Shopee article 77243 | https://help.shopee.vn/portal/4/article/77243 | 2026-09-20 / not-stated | 83,370 | both, terms-of-service, vi |
| 7 | Shopee article 77245 | https://help.shopee.vn/portal/4/article/77245 | 2026-09-20 / not-stated | 77,839 | buyer, return-refund-policy, vi |
| 8 | Shopee article 77251 | https://help.shopee.vn/portal/4/article/77251 | 2026-09-20 / not-stated | 19,598 | buyer, return-refund-policy, vi |
| 9 | Shopee article 77262 | https://help.shopee.vn/portal/4/article/77262 | 2026-09-20 / not-stated | 33,723 | buyer, return-refund-policy, vi |
| 10 | Shopee article 77265 | https://help.shopee.vn/portal/4/article/77265 | 2026-09-20 / not-stated | 4,812 | buyer, return-refund-policy, vi |
| 11 | Shopee article 77484 | https://help.shopee.vn/portal/4/article/77484 | 2026-09-20 / not-stated | 22,984 | buyer, return-refund-policy, vi |
| 12 | Shopee article 79233 | https://help.shopee.vn/portal/4/article/79233 | 2026-09-20 / not-stated | 2,499 | buyer, return-request-guide, vi |
| 13 | Shopee article 79467 | https://help.shopee.vn/portal/4/article/79467 | 2026-09-20 / not-stated | 3,430 | buyer, return-refund-policy, vi |
| 14 | Shopee article 79508 | https://help.shopee.vn/portal/4/article/79508 | 2026-09-20 / not-stated | 3,608 | buyer, return-refund-policy, vi |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Corpus chỉ chứa nguồn công khai từ Shopee Help Center, không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` trong metadata.
- [x] Dữ liệu đã được lưu thành Markdown kèm frontmatter để dễ trace nguồn và lọc metadata.
- [x] Nội dung crawl còn có nhiều đoạn nhiễu từ trang web, vì vậy cần làm sạch và chọn chunking phù hợp với văn bản chính sách.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | string | `shopee-article-77251` | Định danh tài liệu, dùng để trace nguồn, xóa document và đối chiếu gold doc. |
| `title` | string | `Shopee article 77251` | Giữ ngữ cảnh khi chunk ngắn hoặc khi nhiều chính sách có nội dung gần nhau. |
| `source_url` | string | `https://help.shopee.vn/portal/4/article/77251` | Cho phép kiểm chứng nguồn công khai sau khi agent trả lời. |
| `retrieved_at` | date string | `2026-09-20` | Biết thời điểm crawl, quan trọng vì chính sách thương mại điện tử có thể thay đổi. |
| `document_version` | string | `not-stated` | Ghi nhận phiên bản/ngày hiệu lực nếu nguồn có công bố. |
| `audience` | string | `buyer`, `seller`, `both` | Lọc theo đối tượng để tránh lấy nhầm chính sách của người mua/người bán. |
| `category` | string | `return-refund-policy` | Lọc theo nhóm nghiệp vụ như phí hoàn trả, hướng dẫn gửi yêu cầu, điều khoản dịch vụ. |
| `language` | string | `vi` | Hỗ trợ chọn embedder/tokenizer phù hợp với tiếng Việt. |
| `license_or_permission` | string | `public-source` | Ghi nhận quyền sử dụng nguồn dữ liệu công khai cho bài lab. |

---

## 2. Thiết kế chiến lược (Strategy Design) - Nhóm (15 điểm)

### Phân tích đường cơ sở (Baseline Analysis)

Nhóm dùng 5 câu hỏi đánh giá thống nhất và tính điểm theo `docs/SCORING.md`: mỗi câu tối đa 2 điểm, top-3 có chunk chứa evidence thì được tính hit. Benchmark hiện tại dùng `LexicalHashEmbedder` để chạy offline ổn định; benchmark của Trường dùng `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

| Chiến lược | Corpus / Embedder | Số chunk | Độ dài TB | Hit@1 | Hit@3 | MRR | Điểm |
|-----------|-------------------|----------|-----------|-------|-------|-----|------|
| `fixed_size` | Đức, lexical-hash | 90 | 481.2 | 60% | 60% | 0.600 | 6/10 |
| `by_sentences` | Đức, lexical-hash | 71 | 549.1 | 80% | 100% | 0.900 | 9/10 |
| `recursive` | Đức, lexical-hash | 96 | 405.4 | 60% | 60% | 0.600 | 6/10 |
| `HeadingChunker` | Trường, multilingual MiniLM | 561 | chưa ghi | 60% | 80% | 0.700 | 7/10 |
| `fixed_size` | Corpus hiện tại, lexical-hash | 659 | 496.2 | 20% | 60% | 0.400 | 4/10 |
| `by_sentences` | Corpus hiện tại, lexical-hash | 630 | 464.5 | 80% | 80% | 0.800 | 8/10 |
| `recursive` | Corpus hiện tại, lexical-hash | 767 | 380.8 | 40% | 40% | 0.400 | 4/10 |
| `policy_structure` | Corpus hiện tại, lexical-hash | 1,273 | 284.2 | 80% | 100% | 0.867 | 9/10 |

Nhận xét chính: chunk theo câu và chunk theo cấu trúc chính sách đều tốt hơn fixed-size/recursive mặc định. Fixed-size dễ cắt ngang một điều kiện hoặc dòng bảng; recursive mặc định giữ giới hạn độ dài tốt nhưng có thể tạo các đoạn không đủ ngữ cảnh khi văn bản crawl có nhiều dòng rời. Với dữ liệu chính sách Shopee, chunk cần đủ ngắn để không lẫn nhiều điều kiện, nhưng vẫn phải giữ tiêu đề tài liệu để biết đoạn đó thuộc chính sách nào.

### Chiến lược của từng thành viên

**Thành viên 1 - Lê Thanh Trường**
- **Loại chiến lược:** custom `HeadingChunker(max_section_size=800)`.
- **Mô tả & lý do chọn:** Chiến lược ưu tiên giữ các mục chính sách theo heading/mục số, vì văn bản Shopee thường có cấu trúc điều khoản như `1.2`, `7.1`, `8.1`. Kết quả đạt `Hit@1 = 60%`, `Hit@3 = 80%`, `MRR = 0.700`, `lab_score = 7/10` với embedding multilingual MiniLM. Điểm yếu là Q2 không tìm được mốc `24/11/2025`, và Q5 chỉ đưa evidence lên hạng 2.

**Thành viên 2 - Nguyễn Đình Anh Đức**
- **Loại chiến lược:** so sánh `fixed_size`, `by_sentences`, `recursive`.
- **Mô tả & lý do chọn:** Đức benchmark các chiến lược mặc định bằng lexical-hash offline. Kết quả tốt nhất là `by_sentences` với `71 chunks`, `avg_len = 549.1`, `Hit@1 = 80%`, `Hit@3 = 100%`, `MRR = 0.900`, `lab_score = 9/10`. Điều này cho thấy với chính sách dạng FAQ, đơn vị câu thường chứa đủ ý trả lời hơn là cắt theo ký tự.

**Thành viên 3 - [bổ sung tên]**
- **Loại chiến lược:** custom `PolicyStructureChunker(chunk_size=450, max_sentences=2)`.
- **Mô tả & lý do chọn:** Chiến lược này là hybrid: tách theo câu để giữ đơn vị ngữ nghĩa, dùng recursive fallback khi câu/bảng quá dài, giới hạn mỗi chunk tối đa 450 ký tự, và lặp lại tiêu đề tài liệu trong từng chunk. Trên corpus hiện tại, chiến lược đạt `Hit@1 = 80%`, `Hit@3 = 100%`, `MRR = 0.867`, `lab_score = 9/10`. Đổi lại số chunk tăng lên 1,273 nên chi phí embedding/lưu trữ cao hơn.

### So sánh giữa các thành viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Lê Thanh Trường | `HeadingChunker` + multilingual MiniLM | 7/10 | Giữ được cấu trúc mục/điều khoản, có semantic embedding thật. | Miss Q2, Q5 không ở top-1; phụ thuộc heading sạch. |
| Nguyễn Đình Anh Đức | `by_sentences` | 9/10 | Gọn, ít chunk, giữ câu đầy đủ, Hit@3 100% trên benchmark của Đức. | Có thể tạo chunk rất dài nếu văn bản/bảng ít dấu câu. |
| [bổ sung tên] | `PolicyStructureChunker` | 9/10 | Hit@3 100%, xử lý tốt câu ngắn + bảng/đoạn dài, chunk có tiêu đề nguồn. | Nhiều chunk hơn, tăng chi phí index và embedding. |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**

Với dữ liệu Shopee hiện tại, nhóm chọn `PolicyStructureChunker(chunk_size=450, max_sentences=2)` làm cấu hình khuyến nghị. Lý do là nó đạt `9/10`, đưa cả 5 câu hỏi có evidence vào top-3, đồng thời tránh nhược điểm của `by_sentences` là có chunk dài tới 3,659 ký tự khi gặp bảng hoặc đoạn crawl thiếu dấu câu. Chiến lược này phù hợp với chính sách thương mại điện tử vì mỗi câu/điều kiện thường ngắn, nhiều thông tin quan trọng là số liệu như `24 giờ`, `7 - 14 ngày`, `3 - 5 ngày`, `48 giờ`.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) - Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | Thực phẩm tươi sống và đông lạnh phải gửi yêu cầu trả hàng/hoàn tiền trong bao lâu? | Trong vòng 24 giờ kể từ khi đơn hàng được cập nhật giao hàng thành công. | `shopee-article-77251`, marker `24 giờ` |
| 2 | Sau khi Shopee chấp nhận hoàn tiền, thẻ tín dụng hoặc ghi nợ nhận tiền trong bao lâu? | Từ 7 đến 14 ngày làm việc, tùy theo ngân hàng. | `shopee-article-189473`, marker `7 - 14 ngày làm việc` |
| 3 | Nếu tự sắp xếp gửi hàng hoàn trả thì người mua có phải trả phí trước không? | Có. Người mua trả phí trước; Shopee hỗ trợ hoàn phí trong 3-5 ngày làm việc nếu đủ điều kiện. | `shopee-article-77251`, marker `Tự sắp xếp` / `thanh toán trước` |
| 4 | Người mua chưa nhận được hàng thì cần cung cấp bằng chứng gì? | Không cần cung cấp bằng chứng; Shopee xử lý dựa trên hệ thống theo dõi đơn hàng. | `shopee-article-79467`, marker `không cần cung cấp bất kỳ bằng chứng nào` |
| 5 | Khi đóng gói hàng hoàn trả, người mua cần quay video và gửi kèm những gì? | Quay video đóng gói và gửi đủ hộp, giấy tờ, phụ kiện, quà tặng đi kèm nếu có. | `shopee-article-79508`, marker `quay video quá trình đóng gói` |

### Tổng hợp chất lượng truy xuất của nhóm

Kết quả dưới đây lấy theo chiến lược tốt nhất trên corpus hiện tại: `PolicyStructureChunker`.

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | Thực phẩm tươi sống/đông lạnh gửi yêu cầu trong bao lâu? | `policy_structure` | Có, hạng 1 | Chunk chứa rõ `24 giờ`. |
| 2 | Thẻ tín dụng/ghi nợ nhận tiền hoàn trong bao lâu? | `policy_structure` | Có, hạng 3 | Có evidence nhưng chưa lên top-1 vì chunk khác cùng tài liệu nói chung về hoàn tiền. |
| 3 | Tự sắp xếp gửi hàng hoàn trả có phải trả phí trước không? | `policy_structure` | Có, hạng 1 | Chunk chứa điều kiện thanh toán trước và hoàn phí. |
| 4 | Chưa nhận được hàng cần cung cấp bằng chứng gì? | `policy_structure` | Có, hạng 1 | Câu hỏi khớp trực tiếp với nội dung evidence. |
| 5 | Đóng gói hàng hoàn trả cần quay video/gửi kèm gì? | `policy_structure` | Có, hạng 1 | Chiến lược lặp title giúp chunk ngắn vẫn giữ đúng ngữ cảnh đóng gói. |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**

Metadata filter hữu ích về mặt thiết kế vì giúp giới hạn không gian tìm kiếm theo `audience` hoặc `category` trước khi tính similarity. Tuy nhiên trong corpus hiện tại, phần lớn tài liệu có `audience=buyer`, chỉ có một số ít `both`, nên filter `audience=buyer` không làm thay đổi top-3 ở Q1. Với bộ dữ liệu cân bằng hơn giữa `buyer` và `seller`, filter sẽ quan trọng hơn, đặc biệt ở các câu hỏi dễ nhầm giữa chi phí của Người Mua và trách nhiệm của Người Bán.

---

## 4. Thuyết trình (Demo) & Bài học nhóm - Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
- Mock embedding chỉ dùng để kiểm thử pipeline, không phản ánh chất lượng retrieval thật; benchmark cần ít nhất dùng lexical-hash hoặc embedding model thật.
- Chunking theo câu tốt hơn fixed-size vì chính sách Shopee chứa nhiều câu ngắn có số liệu quan trọng, nhưng cần fallback khi gặp bảng/đoạn crawl dài.
- `PolicyStructureChunker` đạt kết quả tốt vì mỗi chunk vừa ngắn vừa có title nguồn, giúp truy xuất đúng cả câu hỏi số liệu, điều kiện và hướng dẫn đóng gói.

**Bài học rút ra khi so sánh trong nhóm:**

Cùng một bộ tài liệu nhưng chiến lược chunking làm thay đổi mạnh chất lượng truy xuất: fixed-size trên corpus hiện tại chỉ đạt 4/10, trong khi `policy_structure` đạt 9/10. Nhóm cũng thấy rằng điểm tốt không chỉ phụ thuộc số chunk; quan trọng hơn là chunk có giữ đúng đơn vị trả lời không và có đủ ngữ cảnh nguồn không.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**

Nhóm sẽ làm sạch dữ liệu crawl kỹ hơn, đặc biệt là menu/footer và các bảng bị chuyển thành dòng text rời. Ngoài ra nên gắn metadata chi tiết hơn, ví dụ `audience=seller` cho tài liệu người bán, `category=refund-timing`, `category=packing-guide`, và thêm chunking riêng cho bảng: mỗi chunk giữ header bảng + một nhóm dòng để không mất quan hệ giữa cột và giá trị.

---

## Tự đánh giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 9 / 10 |
| Thiết kế chiến lược (Strategy Design) | 14 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 9 / 10 |
| Thuyết trình (Demo) | 4 / 5 |
| **Tổng phần nhóm** | **36 / 40** |
