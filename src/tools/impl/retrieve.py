"""
MarketMind AI - Tool: retrieve_document
Section 5.2 requirement. Strict document fetch by indexed ID.
Enforces path traversal defence and reject-unindexed policy.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("marketmind.tools.retrieve")


def retrieve_document_handler(
    args: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Retrieve full verified text and provenance of an indexed document.
    Rejects raw file paths, URLs, and non-indexed document IDs.
    """
    document_id = args.get("document_id", "").strip()
    section = args.get("section")

    # Security check: detect path traversal characters
    if any(char in document_id for char in ["/", "\\", "..", ":", "~", "\x00"]):
        return {
            "status": "error",
            "error_type": "SecurityViolation",
            "message": f"Illegal path traversal characters detected in document_id: '{document_id}'"
        }

    corpus_dir = context.get("corpus_dir")
    if not corpus_dir or not Path(corpus_dir).exists():
        corpus_dir = Path(__file__).resolve().parent.parent.parent.parent / "corpus"

    index_path = Path(corpus_dir) / "index.json"
    if not index_path.exists():
        return {
            "status": "error",
            "error_type": "CorpusUnavailable",
            "message": "Corpus index file not found."
        }

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    doc_meta = None
    for d in index_data.get("documents", []):
        if d["id"].upper() == document_id.upper():
            doc_meta = d
            break

    if not doc_meta:
        available_ids = [d["id"] for d in index_data.get("documents", [])[:8]]
        return {
            "status": "error",
            "error_type": "DocumentNotFound",
            "message": f"Document ID '{document_id}' does not exist in the verified corpus index.",
            "suggestion": f"Use search_information to locate valid IDs. Example known IDs: {available_ids}"
        }

    file_path = Path(corpus_dir) / doc_meta["file"]
    if not file_path.exists():
        return {
            "status": "error",
            "error_type": "FileCorrupted",
            "message": f"Target document file '{doc_meta['file']}' is missing on disk."
        }

    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Optional section slicing if requested
    text_content = full_text
    if section:
        section_lower = section.lower()
        parts = full_text.split("\n\n")
        matched = [p for p in parts if section_lower in p.lower()]
        if matched:
            text_content = "\n\n".join(matched)

    return {
        "status": "success",
        "document_id": doc_meta["id"],
        "title": doc_meta["title"],
        "vendor": doc_meta.get("vendor", ""),
        "source_type": doc_meta.get("source_type", ""),
        "date": doc_meta.get("date", "unknown"),
        "full_text": text_content,
        "token_estimate": len(text_content) // 4
    }
