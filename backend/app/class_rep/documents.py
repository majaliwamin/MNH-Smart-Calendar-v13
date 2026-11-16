"""CARA document ingestion and retrieval with Cloudflare embeddings."""
import hashlib
import json
import math
import os
import re
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pypdf import PdfReader
from docx import Document
from io import BytesIO
from app.database.connection import database

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CHUNKS = 300
CHUNK_CHARS = 1800
OVERLAP_CHARS = 220
EMBED_MODEL_DEFAULT = "@cf/google/embeddinggemma-2"


class DocumentError(RuntimeError):
    pass


def _cloudflare(payload: dict) -> dict:
    account = os.getenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "").strip()
    key = os.getenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "").strip()
    model = os.getenv("MNH_CLASSREP_CLOUDFLARE_EMBEDDING_MODEL", EMBED_MODEL_DEFAULT).strip()
    if not account or not key:
        raise DocumentError("Cloudflare credentials are required for semantic document indexing.")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    request = Request(url, data=json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode())
    except HTTPError as exc:
        raise DocumentError(f"Embedding service returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise DocumentError("Embedding service is unavailable or returned invalid data.") from exc
    if result.get("success") is False:
        raise DocumentError("Embedding service rejected the document indexing request.")
    return result.get("result") or result


def _extract(filename: str, content: bytes) -> list[tuple[int | None, str]]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(content))
            return [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
        except Exception as exc:
            raise DocumentError("The PDF could not be read. It may be encrypted or damaged.") from exc
    if lower.endswith(".docx"):
        try:
            doc = Document(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    paragraphs.append(" | ".join(cell.text for cell in row.cells))
            return [(None, "\n".join(paragraphs))]
        except Exception as exc:
            raise DocumentError("The Word document could not be read.") from exc
    if lower.endswith(".txt") or lower.endswith(".md"):
        try:
            return [(None, content.decode("utf-8-sig"))]
        except UnicodeDecodeError as exc:
            raise DocumentError("Text documents must use UTF-8 encoding.") from exc
    raise DocumentError("Supported document formats are PDF, DOCX, TXT and Markdown.")


def _split(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(clean) and len(chunks) < MAX_CHUNKS:
        end = min(len(clean), start + CHUNK_CHARS)
        if end < len(clean):
            boundary = clean.rfind(" ", start + CHUNK_CHARS // 2, end)
            if boundary > start:
                end = boundary
        part = clean[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(clean):
            break
        start = max(start + 1, end - OVERLAP_CHARS)
    return chunks


def _vectors(texts: list[str], prefix: str) -> list[list[float]]:
    clean = []
    for offset in range(0, len(texts), 64):
        batch = texts[offset:offset + 64]
        result = _cloudflare({"input": [prefix + text for text in batch], "dimensions": 256})
        vectors = result.get("data")
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise DocumentError("Embedding service returned an unexpected vector count.")
        for item in vectors:
            vector = item.get("embedding") if isinstance(item, dict) else item
            if not isinstance(vector, list) or not vector:
                raise DocumentError("Embedding service returned an invalid vector.")
            clean.append([float(value) for value in vector])
    return clean


def ingest(filename: str, content: bytes) -> dict:
    if len(content) > MAX_FILE_BYTES:
        raise DocumentError("Files must be 10 MB or smaller.")
    pages = _extract(filename, content)
    chunks = []
    for page, text in pages:
        for chunk in _split(text):
            chunks.append({"page": page, "text": chunk})
            if len(chunks) >= MAX_CHUNKS:
                break
        if len(chunks) >= MAX_CHUNKS:
            break
    if not chunks:
        raise DocumentError("No readable text was found in this document.")
    vectors = _vectors([item["text"] for item in chunks],
                       "title: " + filename[:180] + " | text: ")
    doc_id = uuid.uuid4().hex
    now = int(time.time() * 1000)
    digest = hashlib.sha256(content).hexdigest()
    with database() as connection:
        for index, (item, vector) in enumerate(zip(chunks, vectors)):
            record = {
                "document_id": doc_id, "title": filename[:180],
                "page": item["page"], "text": item["text"],
                "embedding": vector, "sha256": digest,
                "created_at": now,
            }
            connection.execute(
                "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
                ("cara_documents", doc_id + ":" + str(index),
                 json.dumps(record, ensure_ascii=False), now),
            )
        connection.execute(
            "INSERT INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)",
            ("cara_document_index", doc_id,
             json.dumps({"title": filename[:180], "chunks": len(chunks),
                         "sha256": digest, "created_at": now}, ensure_ascii=False), now),
        )
    return {"id": doc_id, "title": filename[:180], "chunks": len(chunks),
            "pages": len(pages), "sha256": digest}


def list_documents() -> list[dict]:
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data FROM docs WHERE col='cara_document_index' ORDER BY updated_at DESC"
        ).fetchall()
    result = []
    for row in rows:
        try:
            item = json.loads(row["data"])
            result.append({"id": row["id"], "title": item.get("title"),
                           "chunks": item.get("chunks"), "created_at": item.get("created_at")})
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def delete_document(doc_id: str) -> bool:
    with database() as connection:
        exists = connection.execute(
            "SELECT 1 FROM docs WHERE col='cara_document_index' AND id=?", (doc_id,)
        ).fetchone()
        if not exists:
            return False
        connection.execute("DELETE FROM docs WHERE col='cara_documents' AND id LIKE ?", (doc_id + ":%",))
        connection.execute("DELETE FROM docs WHERE col='cara_document_index' AND id=?", (doc_id,))
    return True


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return -1.0
    denom = math.sqrt(sum(x*x for x in left)) * math.sqrt(sum(x*x for x in right))
    return sum(x*y for x, y in zip(left, right)) / denom if denom else -1.0


def search_documents(query: str, limit: int = 5) -> list[dict]:
    query = query.strip()[:1000]
    if not query:
        return []
    with database() as connection:
        rows = connection.execute(
            "SELECT data FROM docs WHERE col='cara_documents' ORDER BY updated_at DESC LIMIT 1200"
        ).fetchall()
    records = []
    for row in rows:
        try:
            records.append(json.loads(row["data"]))
        except (TypeError, json.JSONDecodeError):
            continue
    if not records:
        return []
    try:
        query_vector = _vectors([query], "task: search result | query: ")[0]
        ranked = [( _cosine(query_vector, item.get("embedding", [])), item) for item in records]
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [{"title": item.get("title"), "page": item.get("page"),
                 "text": item.get("text", "")[:1800], "score": round(score, 4)}
                for score, item in ranked[:limit] if score > 0]
    except DocumentError:
        # Explicitly labelled keyword fallback when the embedding service is unavailable.
        terms = {word.lower() for word in re.findall(r"[\w-]{3,}", query)}
        ranked = []
        for item in records:
            text = item.get("text", "")
            haystack = (item.get("title", "") + " " + text).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [{"title": item.get("title"), "page": item.get("page"),
                 "text": item.get("text", "")[:1800], "score": score,
                 "retrieval": "keyword-fallback"}
                for score, item in ranked[:limit]]
