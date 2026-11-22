"""JSONL export of verified corrections for manual review.

This module never fine-tunes, uploads or applies a model. It only serialises
records that passed independent verification into a reviewable dataset.
"""
from __future__ import annotations

import json

from app.ai_intelligence import corrections


def export_jsonl(limit: int = 500) -> str:
    lines = []
    for item in corrections._read_all(corrections.COL_EXAMPLES, limit):
        if item.get("verification_status") != "verified":
            continue
        record = {
            "question": str(item.get("question", ""))[:4000],
            "context": str(item.get("context", ""))[:5000],
            "incorrect_behaviour": str(item.get("incorrect_behaviour", ""))[:1000],
            "expected_response": str(item.get("expected_response", ""))[:6000],
            "category": str(item.get("category", "other")),
            "verification_status": "verified",
        }
        lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines) + ("\n" if lines else "")
