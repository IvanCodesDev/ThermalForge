from dataclasses import dataclass
from typing import Literal

from app.documents.schemas import DocumentChunk


@dataclass(frozen=True, slots=True)
class TextSegment:
    text: str
    page_number: int | None = None
    section_path: tuple[str, ...] = ()
    content_type: Literal["text", "ocr"] = "text"


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        hard_end = min(start + max_chars, len(normalized))
        end = hard_end
        if hard_end < len(normalized):
            paragraph_break = normalized.rfind("\n\n", start, hard_end)
            sentence_break = normalized.rfind("。", start, hard_end)
            word_break = normalized.rfind(" ", start, hard_end)
            candidate = max(paragraph_break, sentence_break, word_break)
            if candidate > start + max_chars // 2:
                end = candidate + (1 if normalized[candidate] == "。" else 0)

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap_chars, start + 1)

    return chunks


def build_chunks(
    *,
    source_artifact_id: str,
    segments: list[TextSegment],
    max_chars: int,
    overlap_chars: int,
) -> list[DocumentChunk]:
    if max_chars <= 0 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("Chunk size must be positive and larger than overlap.")

    chunks: list[DocumentChunk] = []
    for segment in segments:
        for text in _split_text(segment.text, max_chars, overlap_chars):
            chunk_index = len(chunks)
            chunks.append(
                DocumentChunk(
                    id=f"{source_artifact_id}:chunk:{chunk_index}",
                    source_artifact_id=source_artifact_id,
                    chunk_index=chunk_index,
                    text=text,
                    page_number=segment.page_number,
                    section_path=list(segment.section_path),
                    content_type=segment.content_type,
                )
            )
    return chunks
