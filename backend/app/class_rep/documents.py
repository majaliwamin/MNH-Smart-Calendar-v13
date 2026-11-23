"""CARA document ingestion and retrieval with Cloudflare embeddings."""
import hashlib
import csv
import xml.etree.ElementTree as ET
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

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_CHUNKS = 300
CHUNK_CHARS = 1800
OVERLAP_CHARS = 220
EMBED_MODEL_DEFAULT = "@cf/google/embeddinggemma-2"
AUDIO_TYPES = (
    (".mp3", "audio/mpeg"),
    (".wav", "audio/wav"),
    (".m4a", "audio/mp4"),
    (".aac", "audio/aac"),
    (".ogg", "audio/ogg"),
    (".opus", "audio/ogg"),
    (".flac", "audio/flac"),
    (".webm", "audio/webm"),
)


class DocumentError(RuntimeError):
    pass


def _cloudflare(payload: dict, timeout: int = 45) -> dict:
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
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode())
    except HTTPError as exc:
        raise DocumentError(f"Embedding service returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise DocumentError("Embedding service is unavailable or returned invalid data.") from exc
    if result.get("success") is False:
        raise DocumentError("Embedding service rejected the document indexing request.")
    return result.get("result") or result


def _audio_content_type(lower_filename: str) -> str | None:
    for suffix, content_type in AUDIO_TYPES:
        if lower_filename.endswith(suffix):
            return content_type
    return None


def _extract(filename: str, content: bytes) -> list[tuple[int | None, str]]:
    from app.class_rep.ocr import extract_pdf, extract_image, OCRDocumentError
    lower = filename.lower()
    audio_type = _audio_content_type(lower)
    if audio_type:
        from app.class_rep.voice import transcribe, VoiceError
        try:
            transcript = transcribe(content, audio_type)
        except VoiceError as exc:
            raise DocumentError(str(exc)) from exc
        return [(None, "Audio transcript from " + filename + ":\n" + transcript)]
    if lower.endswith(".pdf"):
        try:
            return extract_pdf(content)
        except OCRDocumentError as exc:
            raise DocumentError(str(exc)) from exc
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
    if lower.endswith(".pptx"):
        try:
            from pptx import Presentation
            presentation = Presentation(BytesIO(content))
            slides = []
            for index, slide in enumerate(presentation.slides, 1):
                parts = []
                for shape in slide.shapes:
                    if getattr(shape, "has_text_frame", False) and shape.text.strip():
                        parts.append(shape.text.strip())
                    if getattr(shape, "has_table", False):
                        for row in shape.table.rows:
                            parts.append(" | ".join(cell.text for cell in row.cells))
                if parts:
                    slides.append((index, "\\n".join(parts)))
            return slides
        except Exception as exc:
            raise DocumentError("The PowerPoint presentation could not be read.") from exc
    if lower.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            sheets = []
            for sheet in workbook.worksheets:
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    values = [str(value).strip() for value in row if value is not None and str(value).strip()]
                    if values:
                        rows.append(" | ".join(values))
                if rows:
                    sheets.append((None, "Sheet: " + sheet.title + "\\n" + "\\n".join(rows)))
            workbook.close()
            return sheets
        except Exception as exc:
            raise DocumentError("The Excel workbook could not be read.") from exc
    if lower.endswith(".csv"):
        try:
            rows = list(csv.reader(content.decode("utf-8-sig").splitlines()))
            return [(None, "\\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(cell.strip() for cell in row)))]
        except (UnicodeDecodeError, csv.Error) as exc:
            raise DocumentError("The CSV file could not be read as UTF-8.") from exc
    if lower.endswith(".svg"):
        try:
            root = ET.fromstring(content)
            parts = [value.strip() for value in root.itertext() if value.strip()]
            return [(1, "\\n".join(parts))]
        except ET.ParseError as exc:
            raise DocumentError("The SVG image is invalid or damaged.") from exc
    if lower.endswith(".txt") or lower.endswith(".md"):
        try:
            return [(None, content.decode("utf-8-sig"))]
        except UnicodeDecodeError as exc:
            raise DocumentError("Text documents must use UTF-8 encoding.") from exc
    if lower.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")):
        try:
            return [(1, extract_image(content))]
        except OCRDocumentError as exc:
            raise DocumentError(str(exc)) from exc
    raise DocumentError("This file type is not supported. Use PDF, DOCX, PPTX, XLSX, CSV, SVG, TXT, Markdown, PNG, JPG, TIFF, BMP, WEBP or audio (MP3, WAV, M4A, AAC, OGG, FLAC, WebM).")


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


def _vectors(texts: list[str], prefix: str, timeout: int = 45) -> list[list[float]]:
    clean = []
    for offset in range(0, len(texts), 64):
        batch = texts[offset:offset + 64]
        result = _cloudflare({"input": [prefix + text for text in batch], "dimensions": 256}, timeout=timeout)
        vectors = result.get("data")
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise DocumentError("Embedding service returned an unexpected vector count.")
        for item in vectors:
            vector = item.get("embedding") if isinstance(item, dict) else item
            if not isinstance(vector, list) or not vector:
                raise DocumentError("Embedding service returned an invalid vector.")
            clean.append([float(value) for value in vector])
    return clean


def ingest(filename: str, content: bytes, owner_id: str = 'shared', source_id: str | None = None) -> dict:
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
    try:
        vectors = _vectors([item["text"] for item in chunks],
                           "title: " + filename[:180] + " | text: ")
    except DocumentError:
        # Keep uploads usable without an embedding provider; search falls back to keywords.
        vectors = [[] for _ in chunks]
    doc_id = uuid.uuid4().hex
    now = int(time.time() * 1000)
    digest = hashlib.sha256(content).hexdigest()
    with database() as connection:
        for index, (item, vector) in enumerate(zip(chunks, vectors)):
            record = {
                "document_id": doc_id, "owner_id": owner_id, "title": filename[:180], "source_id": source_id,
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
             json.dumps({"title": filename[:180], "owner_id": owner_id, "source_id": source_id, "chunks": len(chunks),
                         "sha256": digest, "created_at": now}, ensure_ascii=False), now),
        )
    return {"id": doc_id, "title": filename[:180], "chunks": len(chunks), "source_id": source_id,
            "pages": len(pages), "sha256": digest}


def list_documents(owner_id: str = 'shared') -> list[dict]:
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data FROM docs WHERE col='cara_document_index' ORDER BY updated_at DESC"
        ).fetchall()
    result = []
    for row in rows:
        try:
            item = json.loads(row["data"])
            if item.get("owner_id", "shared") in ("shared", owner_id):
                result.append({"id": row["id"], "title": item.get("title"),
                               "chunks": item.get("chunks"), "created_at": item.get("created_at")})
        except (TypeError, json.JSONDecodeError):
            continue
    return result


def delete_document(doc_id: str, owner_id: str = 'shared') -> bool:
    with database() as connection:
        exists = connection.execute(
            "SELECT data FROM docs WHERE col='cara_document_index' AND id=?", (doc_id,)
        ).fetchone()
        if not exists:
            return False
        metadata = json.loads(exists["data"])
        if metadata.get("owner_id", "shared") != owner_id:
            return False
        connection.execute("DELETE FROM docs WHERE col='cara_documents' AND id LIKE ?", (doc_id + ":%",))
        connection.execute("DELETE FROM docs WHERE col='cara_document_index' AND id=?", (doc_id,))
    return True




def ensure_resource_indexed(file_id: str, filename: str) -> dict:
    """Backfill a main Resources file into CRARA's shared index, idempotently."""
    if not re.fullmatch(r"[a-f0-9]{32}", str(file_id or "")):
        raise DocumentError("The resource file identifier is invalid.")
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data FROM docs WHERE col='cara_document_index'"
        ).fetchall()
    for row in rows:
        try:
            metadata = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        if metadata.get("source_id") == file_id:
            return {"id": row["id"], "title": metadata.get("title") or filename,
                    "chunks": metadata.get("chunks", 0), "already_indexed": True}
    from pathlib import Path
    from app.config import DATA_DIR
    directory = DATA_DIR / "resource_uploads"
    for candidate in directory.glob(file_id + ".*"):
        if candidate.is_file():
            return ingest(filename or candidate.name, candidate.read_bytes(),
                          owner_id="shared", source_id=file_id)
    raise DocumentError("The original resource file is not present in persistent storage.")

def delete_source_documents(source_id: str) -> int:
    """Delete CRARA indexes linked to a main-application resource file."""
    if not source_id:
        return 0
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data FROM docs WHERE col='cara_document_index'"
        ).fetchall()
        ids = []
        for row in rows:
            try:
                metadata = json.loads(row["data"])
            except (TypeError, json.JSONDecodeError):
                continue
            if metadata.get("source_id") == source_id:
                ids.append(str(row["id"]))
        for doc_id in ids:
            connection.execute("DELETE FROM docs WHERE col='cara_documents' AND id LIKE ?", (doc_id + ":%",))
            connection.execute("DELETE FROM docs WHERE col='cara_document_index' AND id=?", (doc_id,))
    return len(ids)

def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return -1.0
    denom = math.sqrt(sum(x*x for x in left)) * math.sqrt(sum(x*x for x in right))
    return sum(x*y for x, y in zip(left, right)) / denom if denom else -1.0


def search_documents(query: str, limit: int = 5, owner_id: str = 'shared') -> list[dict]:
    query = query.strip()[:1000]
    if not query:
        return []
    # Match meaningful query terms in SQLite before loading document payloads.
    # This avoids reading/parsing the entire document collection on every chat turn.
    stop_words = {"what", "which", "when", "where", "who", "why", "how", "the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "is", "does", "did", "can", "could", "would", "should", "you", "your", "about", "please", "tell", "explain", "define", "mean", "means", "into", "have", "has", "had", "not", "all", "any", "some", "use", "used", "using", "give", "show", "me",
                  # Chichewa function words: keeping these as search terms made
                  # ordinary questions retrieve arbitrary recency-ranked chunks.
                  "ndi", "nanga", "chani", "chiyani", "chifukwa", "bwanji", "bwanj", "kodi", "bwino", "zikomo", "muli", "koma", "ndipo", "kapena", "mawu", "akuti", "tanthauzo", "zikutanthauza", "amatanthauza", "ine", "iwe", "iye", "ife", "inu", "iwo"}
    term_pattern = re.compile(r"[^\W\d_]{3,}(?:['’-][^\W\d_]{2,})*", re.UNICODE)
    terms = sorted({word.casefold().replace("’", "'") for word in term_pattern.findall(query)} - stop_words)
    if not terms:
        return []
    clauses = " OR ".join("data LIKE ?" for _ in terms)
    with database() as connection:
        rows = connection.execute(
            "SELECT data FROM docs WHERE col='cara_documents' AND (" + clauses + ") ORDER BY updated_at DESC LIMIT ?",
            tuple("%" + term + "%" for term in terms) + (max(limit * 20, 40),),
        ).fetchall()
    records = []
    for row in rows:
        try:
            record = json.loads(row["data"])
            if record.get("owner_id", "shared") in ("shared", owner_id):
                records.append(record)
        except (TypeError, json.JSONDecodeError):
            continue
    ranked = []
    for item in records:
        haystack = (item.get("title", "") + " " + item.get("text", "")).lower()
        document_terms = {word.casefold().replace("’", "'") for word in term_pattern.findall(haystack)}
        score = len(set(terms) & document_terms)
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)

    # Semantic fallback is used when keyword retrieval finds no passages.
    # This preserves fast exact-match retrieval while supporting synonyms.
    if (not ranked and os.getenv("MNH_CLASSREP_CLOUDFLARE_API_KEY", "").strip()
            and os.getenv("MNH_CLASSREP_CLOUDFLARE_ACCOUNT_ID", "").strip()):
        try:
            query_vector = _vectors([query], "query: ", timeout=12)[0]
            with database() as connection:
                vector_rows = connection.execute(
                    "SELECT data FROM docs WHERE col='cara_documents' ORDER BY updated_at DESC LIMIT 5000"
                ).fetchall()
            semantic_ranked = []
            for row in vector_rows:
                try:
                    item = json.loads(row["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if item.get("owner_id", "shared") not in ("shared", owner_id):
                    continue
                vector = item.get("embedding")
                if isinstance(vector, list) and vector:
                    score = _cosine(query_vector, vector)
                    if score > 0:
                        semantic_ranked.append((score, item))
            semantic_ranked.sort(key=lambda pair: pair[0], reverse=True)
            if semantic_ranked:
                return [{"title": item.get("title"), "page": item.get("page"),
                         "text": item.get("text", "")[:1800], "score": round(score, 4),
                         "retrieval": "semantic"}
                        for score, item in semantic_ranked[:limit]]
        except DocumentError:
            pass

    if ranked:
        return [{"title": item.get("title"), "page": item.get("page"),
                 "text": item.get("text", "")[:1800], "score": score,
                 "retrieval": "keyword"}
                for score, item in ranked[:limit]]

    return []


# A short request such as "summarise this" or "make notes from the lecture"
# contains no topic words for keyword retrieval. These turns still need the
# uploaded source, so they deliberately fall back to the newest indexed file.
SUMMARY_REQUEST_RE = re.compile(
    r"\b(?:summar(?:y|ise|ize|ising|izing)|summary\s+notes|make\s+notes|key\s+points|"
    r"main\s+points|recap|outline|overview|read\s+(?:this|it|these|the\s+"
    r"(?:notes?|document|file|upload|lecture))|what\s+(?:does|do)\s+(?:this|it|the\s+"
    r"(?:notes?|document|file|upload|lecture))\s+say|lecture\s+notes?|"
    r"uploaded\s+(?:notes?|document|file|audio|recording)|"
    r"attached\s+(?:notes?|document|file|audio|recording))\b",
    re.I,
)


def is_document_reference_request(message: str) -> bool:
    """Whether a turn asks for a read-through without naming a source topic."""
    return bool(SUMMARY_REQUEST_RE.search(str(message or "")[:1000]))


def recent_document_passages(owner_id: str = 'shared', *, document_limit: int = 1,
                             chunk_limit: int = 6, max_chars: int = 9000) -> list[dict]:
    """Return passages from the newest indexed document(s) for summary turns.

    Results stay inside the caller's document scope and reuse the existing
    ``docs`` collections; no new database field or table is introduced.
    """
    if document_limit < 1 or chunk_limit < 1:
        return []
    with database() as connection:
        rows = connection.execute(
            "SELECT id,data,updated_at FROM docs WHERE col='cara_documents' "
            "ORDER BY updated_at DESC LIMIT ?",
            (max(100, document_limit * chunk_limit * 20),),
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    used = 0
    for row in rows:
        try:
            item = json.loads(row["data"])
        except (TypeError, KeyError, json.JSONDecodeError):
            continue
        if not isinstance(item, dict) or item.get("owner_id", "shared") not in ("shared", owner_id):
            continue
        doc_id = str(item.get("document_id") or "")
        if not doc_id:
            continue
        if doc_id not in grouped:
            if len(order) >= document_limit:
                continue
            order.append(doc_id)
            grouped[doc_id] = []
        if len(grouped[doc_id]) >= chunk_limit:
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if used + len(text) > max_chars:
            text = text[:max(0, max_chars - used)]
        if not text:
            break
        used += len(text)
        grouped[doc_id].append({
            "title": item.get("title"),
            "page": item.get("page"),
            "text": text,
            "retrieval": "recent_upload",
        })
        if used >= max_chars:
            break
    passages: list[dict] = []
    for doc_id in order:
        passages.extend(reversed(grouped[doc_id]))
    return passages
