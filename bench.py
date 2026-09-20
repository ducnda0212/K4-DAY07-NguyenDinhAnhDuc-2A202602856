from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from src.chunking import FixedSizeChunker, RecursiveChunker, SentenceChunker
from src.embeddings import GeminiEmbedder, LocalEmbedder, MockEmbedder, OpenAIEmbedder
from src.models import Document
from src.store import EmbeddingStore


DATA_DIR = Path("data/shopee-return-refund")
TEXT_REPORT = Path("ket_qua_benchmark.txt")
JSON_REPORT = Path("benchmark_results.json")
CACHE_FILE = Path(".cache/benchmark_embeddings.json")


@dataclass(frozen=True)
class BenchmarkQuery:
    question: str
    gold_answer: str
    gold_doc_ids: tuple[str, ...]
    evidence_phrases: tuple[str, ...]
    metadata_filter: dict[str, str] | None = None


QUERIES = [
    BenchmarkQuery(
        question="Thực phẩm tươi sống và đông lạnh phải gửi yêu cầu trả hàng/hoàn tiền trong bao lâu?",
        gold_answer="Trong vòng 24 giờ kể từ khi đơn hàng được cập nhật giao hàng thành công.",
        gold_doc_ids=("general-return-refund-rules", "shopee-return-refund-policy-buyer"),
        evidence_phrases=("trong vòng 24 giờ", "thực phẩm tươi sống và đông lạnh"),
        metadata_filter={"audience": "buyer"},
    ),
    BenchmarkQuery(
        question="Sau khi Shopee chấp nhận hoàn tiền, thẻ tín dụng hoặc ghi nợ nhận tiền trong bao lâu?",
        gold_answer="Từ 7 đến 14 ngày làm việc, tùy theo ngân hàng.",
        gold_doc_ids=("refund-methods-and-timing",),
        evidence_phrases=("7 - 14 ngày làm việc",),
    ),
    BenchmarkQuery(
        question="Nếu tự sắp xếp gửi hàng hoàn trả thì người mua có phải trả phí trước không?",
        gold_answer="Có. Người mua trả phí trước; Shopee hỗ trợ hoàn phí trong 3-5 ngày làm việc nếu đủ điều kiện.",
        gold_doc_ids=("return-shipping-and-fees", "shopee-return-refund-policy-buyer"),
        evidence_phrases=("cần thanh toán trước",),
    ),
    BenchmarkQuery(
        question="Người mua chưa nhận được hàng thì cần cung cấp bằng chứng gì?",
        gold_answer="Không cần cung cấp bằng chứng; Shopee xử lý dựa trên hệ thống theo dõi đơn hàng.",
        gold_doc_ids=("return-refund-evidence",),
        evidence_phrases=("không cần cung cấp bất kỳ bằng chứng nào",),
    ),
    BenchmarkQuery(
        question="Khi đóng gói hàng hoàn trả, người mua cần quay video và gửi kèm những gì?",
        gold_answer="Quay video đóng gói và gửi đủ hộp, giấy tờ, phụ kiện, quà tặng đi kèm nếu có.",
        gold_doc_ids=("pack-return-parcel",),
        evidence_phrases=("quay video quá trình đóng gói", "phụ kiện", "quà tặng"),
    ),
]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    return " ".join(text.split())


class LexicalHashEmbedder:
    """Offline lexical baseline using normalized word and word-bigram features."""

    def __init__(self, dim: int = 4096) -> None:
        self.dim = dim
        self._backend_name = f"lexical-hash-{dim}"

    def __call__(self, text: str) -> list[float]:
        words = re.findall(r"\w+", normalize_text(text), flags=re.UNICODE)
        features = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        counts = Counter(features)
        vector = [0.0] * self.dim
        for token, count in counts.items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dim
            vector[index] += 1.0 + math.log(count)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class CachedEmbedder:
    def __init__(self, embedder: Callable[[str], list[float]], path: Path, enabled: bool = True) -> None:
        self.embedder = embedder
        self.path = path
        self.enabled = enabled
        self._backend_name = getattr(embedder, "_backend_name", embedder.__class__.__name__)
        self.cache: dict[str, list[float]] = {}
        if enabled and path.exists():
            try:
                self.cache = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    def __call__(self, text: str) -> list[float]:
        if not self.enabled:
            return self.embedder(text)
        cache_key = hashlib.sha256(f"{self._backend_name}\0{text}".encode("utf-8")).hexdigest()
        if cache_key not in self.cache:
            self.cache[cache_key] = self.embedder(text)
        return self.cache[cache_key]

    def save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.cache), encoding="utf-8")


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8").replace("\u00a0", " ")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, flags=re.DOTALL)
    if not match:
        return {"doc_id": path.stem, "source": str(path)}, raw.strip()

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip('"\'')
    metadata["doc_id"] = metadata.get("doc_id") or path.stem
    metadata["source"] = str(path)
    return metadata, match.group(2).strip()


def make_embedder(provider: str) -> CachedEmbedder:
    if provider == "local":
        backend = LocalEmbedder()
    elif provider == "openai":
        backend = OpenAIEmbedder()
    elif provider == "gemini":
        backend = GeminiEmbedder()
    elif provider == "mock":
        backend = MockEmbedder()
    else:
        backend = LexicalHashEmbedder()
    return CachedEmbedder(backend, CACHE_FILE, enabled=provider in {"local", "openai", "gemini"})


def build_strategies(chunk_size: int, overlap: int, sentences: int) -> dict[str, object]:
    return {
        "fixed_size": FixedSizeChunker(chunk_size=chunk_size, overlap=overlap),
        "by_sentences": SentenceChunker(max_sentences_per_chunk=sentences),
        "recursive": RecursiveChunker(chunk_size=chunk_size),
    }


def contains_evidence(content: str, phrases: tuple[str, ...]) -> bool:
    normalized = normalize_text(content)
    return all(normalize_text(phrase) in normalized for phrase in phrases)


def load_chunk_documents(chunker: object) -> tuple[list[Document], dict[str, float]]:
    documents: list[Document] = []
    lengths: list[int] = []
    source_count = 0
    for path in sorted(DATA_DIR.glob("*.md")):
        metadata, content = parse_frontmatter(path)
        source_count += 1
        for index, chunk in enumerate(chunker.chunk(content)):
            lengths.append(len(chunk))
            documents.append(
                Document(
                    id=f"{metadata['doc_id']}#{index}",
                    content=chunk,
                    metadata={**metadata, "chunk_index": index},
                )
            )
    stats = {
        "documents": source_count,
        "chunks": len(documents),
        "avg_length": sum(lengths) / len(lengths) if lengths else 0.0,
        "min_length": min(lengths, default=0),
        "max_length": max(lengths, default=0),
    }
    return documents, stats


def evaluate_query(store: EmbeddingStore, item: BenchmarkQuery, top_k: int = 3) -> dict:
    results = store.search(item.question, top_k=top_k)
    gold_rank = next(
        (rank for rank, result in enumerate(results, 1) if result["metadata"].get("doc_id") in item.gold_doc_ids),
        None,
    )
    evidence_ranks = [
        rank
        for rank, result in enumerate(results, 1)
        if result["metadata"].get("doc_id") in item.gold_doc_ids
        and contains_evidence(result["content"], item.evidence_phrases)
    ]
    evidence_rank = evidence_ranks[0] if evidence_ranks else None
    score = 2 if evidence_rank == 1 else 1 if evidence_rank in (2, 3) else 0

    filtered_results = None
    if item.metadata_filter:
        filtered_results = store.search_with_filter(
            item.question, top_k=top_k, metadata_filter=item.metadata_filter
        )

    return {
        "question": item.question,
        "gold_answer": item.gold_answer,
        "gold_doc_ids": list(item.gold_doc_ids),
        "gold_doc_rank": gold_rank,
        "evidence_rank": evidence_rank,
        "hit_at_1": evidence_rank == 1,
        "hit_at_3": evidence_rank is not None,
        "reciprocal_rank": 1.0 / evidence_rank if evidence_rank else 0.0,
        "score": score,
        "metadata_filter": item.metadata_filter,
        "filter_changed_top3": (
            [result["id"] for result in filtered_results] != [result["id"] for result in results]
            if filtered_results is not None
            else None
        ),
        "results": [serialize_result(result, item) for result in results],
        "filtered_results": (
            [serialize_result(result, item) for result in filtered_results]
            if filtered_results is not None
            else None
        ),
    }


def serialize_result(result: dict, item: BenchmarkQuery) -> dict:
    preview = " ".join(result["content"].split())[:180]
    return {
        "id": result["id"],
        "doc_id": result["metadata"].get("doc_id"),
        "chunk_index": result["metadata"].get("chunk_index"),
        "score": round(result["score"], 6),
        "contains_evidence": contains_evidence(result["content"], item.evidence_phrases),
        "preview": preview,
    }


def summarize(evaluations: list[dict]) -> dict[str, float]:
    count = len(evaluations) or 1
    return {
        "hit_at_1": sum(item["hit_at_1"] for item in evaluations) / count,
        "hit_at_3": sum(item["hit_at_3"] for item in evaluations) / count,
        "mrr": sum(item["reciprocal_rank"] for item in evaluations) / count,
        "lab_score": sum(item["score"] for item in evaluations),
        "max_lab_score": 2 * len(evaluations),
    }


def render_report(payload: dict) -> str:
    lines = [
        "BENCHMARK CHUNKING - SHOPEE RETURN/REFUND",
        f"Embedding: {payload['embedding_backend']}",
        f"Corpus: {payload['data_dir']}",
        f"Cau hinh: chunk_size={payload['config']['chunk_size']}, "
        f"overlap={payload['config']['overlap']}, sentences={payload['config']['sentences']}",
        "",
        "BANG TONG HOP",
        "strategy       chunks  avg_len  min/max       Hit@1  Hit@3   MRR   lab_score",
    ]
    for name, result in payload["strategies"].items():
        stats, metrics = result["chunk_stats"], result["metrics"]
        lines.append(
            f"{name:14} {stats['chunks']:6.0f}  {stats['avg_length']:7.1f}  "
            f"{stats['min_length']:3.0f}/{stats['max_length']:<7.0f} "
            f"{metrics['hit_at_1']:.0%}  {metrics['hit_at_3']:.0%}  "
            f"{metrics['mrr']:.3f}  {metrics['lab_score']:.0f}/{metrics['max_lab_score']:.0f}"
        )

    for name, result in payload["strategies"].items():
        lines.extend(["", f"=== {name} ==="])
        for index, evaluation in enumerate(result["queries"], 1):
            lines.append(
                f"Q{index}: score={evaluation['score']}/2, "
                f"gold_doc_rank={evaluation['gold_doc_rank'] or '-'}, "
                f"evidence_rank={evaluation['evidence_rank'] or '-'}"
            )
            lines.append(f"  {evaluation['question']}")
            lines.append(f"  Gold: {evaluation['gold_answer']}")
            for rank, hit in enumerate(evaluation["results"], 1):
                evidence = " EVIDENCE" if hit["contains_evidence"] else ""
                lines.append(
                    f"  {rank}. {hit['doc_id']}#{hit['chunk_index']} "
                    f"score={hit['score']:.4f}{evidence} | {hit['preview']}"
                )
            if evaluation["filtered_results"] is not None:
                filtered_ids = ", ".join(hit["id"] for hit in evaluation["filtered_results"])
                lines.append(
                    f"  Filter {evaluation['metadata_filter']} changed_top3="
                    f"{evaluation['filter_changed_top3']}: {filtered_ids}"
                )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare the three default chunking strategies.")
    parser.add_argument("--provider", choices=("lexical", "local", "openai", "gemini", "mock"), default="lexical")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--sentences", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not DATA_DIR.exists():
        raise SystemExit(f"Khong tim thay corpus: {DATA_DIR}")
    if args.overlap >= args.chunk_size:
        raise SystemExit("overlap phai nho hon chunk_size")

    load_dotenv(override=False)
    embedder = make_embedder(args.provider)
    payload = {
        "embedding_backend": embedder._backend_name,
        "data_dir": str(DATA_DIR),
        "config": vars(args),
        "strategies": {},
    }

    for name, chunker in build_strategies(args.chunk_size, args.overlap, args.sentences).items():
        documents, chunk_stats = load_chunk_documents(chunker)
        store = EmbeddingStore(collection_name=f"benchmark_{name}", embedding_fn=embedder)
        store.add_documents(documents)
        evaluations = [evaluate_query(store, item) for item in QUERIES]
        payload["strategies"][name] = {
            "chunk_stats": chunk_stats,
            "metrics": summarize(evaluations),
            "queries": evaluations,
        }

    embedder.save()
    report = render_report(payload)
    TEXT_REPORT.write_text(report, encoding="utf-8")
    JSON_REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report, end="")
    print(f"Da luu: {TEXT_REPORT} va {JSON_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
