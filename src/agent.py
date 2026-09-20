from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        results = self.store.search(question, top_k=top_k)
        if not results:
            return "Không tìm thấy thông tin phù hợp trong kho kiến thức."

        context_blocks: list[str] = []
        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})
            source = (
                metadata.get("source_url")
                or metadata.get("source")
                or metadata.get("doc_id")
                or result.get("id")
                or "không rõ nguồn"
            )
            context_blocks.append(
                f"[{index}] Nguồn: {source}\nNội dung: {result['content']}"
            )

        context = "\n\n".join(context_blocks)
        prompt = f"""Bạn là trợ lý trả lời câu hỏi dựa trên kho kiến thức được cung cấp.

Quy tắc:
- Chỉ sử dụng thông tin trong phần NGỮ CẢNH; không suy đoán hoặc bổ sung kiến thức bên ngoài.
- Trích dẫn nguồn bằng số tương ứng như [1], [2] sau mỗi thông tin chính.
- Nếu ngữ cảnh không chứa câu trả lời, hãy nói rõ: "Không tìm thấy thông tin trong ngữ cảnh được cung cấp."

NGỮ CẢNH:
{context}

CÂU HỎI:
{question}

TRẢ LỜI:"""
        return self.llm_fn(prompt)
