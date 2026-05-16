"""Document ingestion: loading, chunking, embedding."""

from __future__ import annotations

import uuid
from pathlib import Path

import structlog

from evograph.llm.client import llm_client

logger = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".html", ".htm"}


async def load_document(file_path: str, content: bytes | None = None) -> dict:
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    if content is None:
        with open(file_path, "rb") as f:
            content = f.read()

    if ext == ".pdf":
        text = _extract_pdf(content)
    elif ext in (".html", ".htm"):
        text = _extract_html(content)
    else:
        text = content.decode("utf-8", errors="replace")

    return {"text": text, "filename": Path(file_path).name, "extension": ext}


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _extract_html(content: bytes) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[dict[str, str | int]]:
    chunks = []
    sentences = text.replace("\n\n", "\n").split("\n")
    current_chunk = ""
    position = 0

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunk_id = str(uuid.uuid4())
            chunks.append({
                "id": chunk_id,
                "text": current_chunk.strip(),
                "position": position,
            })
            position += 1
            overlap_start = max(0, len(current_chunk) - chunk_overlap)
            current_chunk = current_chunk[overlap_start:] + "\n" + sentence
        else:
            current_chunk += "\n" + sentence

    if current_chunk.strip():
        chunks.append({
            "id": str(uuid.uuid4()),
            "text": current_chunk.strip(),
            "position": position,
        })

    return chunks


async def embed_chunks(chunks: list[dict]) -> list[dict]:
    texts = [c["text"] for c in chunks]
    batch_size = 20
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings = await llm_client.embed(batch)
        all_embeddings.extend(embeddings)

    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding

    return chunks
