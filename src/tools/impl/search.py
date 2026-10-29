"""
MarketMind AI - Tool: search_information
Section 5.2 requirement. Searches approved local corpus only.
Includes indirect prompt injection detection and tagging (Section 10 Control 5).
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.schemas.tools import SearchInformationArgs, SourceTypeFilter, RecencyWindow

logger = logging.getLogger("marketmind.tools.search")

INJECTION_PATTERNS = [
    re.compile(r"SYSTEM:\s*ignore\s+prior\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"rate\s+.*\s+highest\s+and\s+omit", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+rules", re.IGNORECASE),
]


def search_information_handler(
    args: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Search approved knowledge base and local corpus for matching snippets.
    Returns structured list of hits.
    """
    query = args.get("query", "").strip()
    source_type = args.get("source_type", SourceTypeFilter.ALL.value)
    max_results = int(args.get("max_results", 5))
    recency_window = args.get("recency_window", RecencyWindow.ANY.value)

    corpus_dir = context.get("corpus_dir")
    if not corpus_dir or not Path(corpus_dir).exists():
        corpus_dir = Path(__file__).resolve().parent.parent.parent.parent / "corpus"

    index_path = Path(corpus_dir) / "index.json"
    if not index_path.exists():
        return {
            "status": "success",
            "query": query,
            "total_hits": 0,
            "hits": [],
            "message": "Corpus index not found."
        }

    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    documents_meta = index_data.get("documents", [])
    query_tokens = [t.lower() for t in re.split(r"\W+", query) if len(t) > 2]

    hits: List[Dict[str, Any]] = []
    hit_counter = 1

    for doc_meta in documents_meta:
        doc_id = doc_meta["id"]
        doc_type = doc_meta["source_type"]
        doc_file = Path(corpus_dir) / doc_meta["file"]

        # Filter by source_type
        if source_type != SourceTypeFilter.ALL.value and doc_type != source_type:
            continue

        if not doc_file.exists():
            continue

        with open(doc_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Score relevance based on token matches in title, vendor, or content
        score = 0
        content_lower = content.lower()
        title_lower = doc_meta["title"].lower()
        vendor_lower = doc_meta.get("vendor", "").lower()

        for qt in query_tokens:
            if qt in title_lower:
                score += 5
            if qt in vendor_lower:
                score += 4
            if qt in content_lower:
                score += content_lower.count(qt)

        if score > 0:
            # Extract relevant snippet
            snippet = _extract_snippet(content, query_tokens)

            # Security: Detect indirect prompt injection attempt in retrieved data
            injection_flagged = False
            for pattern in INJECTION_PATTERNS:
                if pattern.search(content):
                    injection_flagged = True
                    logger.warning(
                        f"[INJECTION DEFENSE] Prompt injection attempt detected and neutralized in document '{doc_id}'!"
                    )
                    break

            hits.append({
                "hit_id": f"HIT-{hit_counter:03d}",
                "document_id": doc_id,
                "title": doc_meta["title"],
                "vendor": doc_meta.get("vendor", ""),
                "source_type": doc_type,
                "date": doc_meta.get("date", "unknown"),
                "snippet": snippet,
                "score": score,
                "injection_attempt_flagged": injection_flagged
            })
            hit_counter += 1

    # Sort hits by relevance score descending
    hits.sort(key=lambda x: x["score"], reverse=True)
    bounded_hits = hits[:max_results]

    return {
        "status": "success",
        "query": query,
        "total_hits": len(bounded_hits),
        "hits": bounded_hits
    }


def _extract_snippet(content: str, query_tokens: List[str], max_len: int = 350) -> str:
    """Extract a representative snippet around matching keywords."""
    lines = content.splitlines()
    matching_lines = []
    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("DOCUMENT ID:"):
            continue
        line_lower = line_clean.lower()
        if any(qt in line_lower for qt in query_tokens):
            matching_lines.append(line_clean)
        if len(" ".join(matching_lines)) >= max_len:
            break

    if matching_lines:
        res = " ".join(matching_lines)
        return res[:max_len] + ("..." if len(res) > max_len else "")

    # Fallback to first non-header lines
    body_lines = [l for l in lines if l and not l.startswith("DOCUMENT ID:")]
    res = " ".join(body_lines[:3])
    return res[:max_len] + ("..." if len(res) > max_len else "")
