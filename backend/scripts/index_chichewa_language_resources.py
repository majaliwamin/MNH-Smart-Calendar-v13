"""Index the repository's Chichewa reference lessons into CRARA's shared index.

Run after a deployment with a persistent database (or locally with MNH_DATA_DIR
pointing at a writable directory):

    python backend/scripts/index_chichewa_language_resources.py

The script is idempotent: a source is skipped when its source_id is already in
cara_document_index. It intentionally indexes only short, provenance-bearing
lesson/curriculum Markdown files that are present in this repository. Large
user-supplied PDFs (dictionaries, syllabi, guides) must be uploaded through the
normal resource/document endpoints and are not fabricated here.
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.class_rep.documents import ingest  # noqa: E402
from app.database.connection import database  # noqa: E402

REFERENCE_FILES = sorted((PROJECT_ROOT / "docs" / "crara-chichewa-lessons").glob("*.md"))
REFERENCE_FILES.append(PROJECT_ROOT / "docs" / "crara-chichewa-curriculum.md")


def _indexed_sources() -> set[str]:
    sources = set()
    with database() as connection:
        rows = connection.execute("SELECT data FROM docs WHERE col='cara_document_index'").fetchall()
    for row in rows:
        try:
            record = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        if record.get("source_id"):
            sources.add(str(record["source_id"]))
    return sources


def main() -> int:
    existing = _indexed_sources()
    indexed = 0
    skipped = 0
    failed = []
    for path in REFERENCE_FILES:
        if not path.is_file():
            failed.append((path.name, "file missing"))
            continue
        source_id = "chichewa-language-reference:" + path.name
        if source_id in existing:
            skipped += 1
            continue
        try:
            result = ingest(
                path.name,
                path.read_bytes(),
                owner_id="shared",
                source_id=source_id,
            )
            indexed += 1
            print(f"indexed {path.name}: {result['chunks']} chunks")
        except Exception as exc:  # keep going; report at the end
            failed.append((path.name, str(exc)))
    print(f"done: indexed={indexed} already_indexed={skipped} failed={len(failed)}")
    for name, reason in failed:
        print(f"FAILED {name}: {reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
