"""
search.py — Search engine that reads the inverted index (data/storage/p.data)
and scores results using the formula:
    score = (frequency × 10) + 1000 (exact match bonus) − (depth × 5)
"""

import os
from collections import defaultdict

import database as db
from normalize import normalize_text

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "storage")


def _load_pdata_entries(query_word):
    """Load all entries from [letter].data that match the query word exactly.

    p.data format: word url origin depth frequency
    Returns list of dicts.
    """
    entries = []

    query_lower = normalize_text(query_word).strip()
    if not query_lower:
        return entries

    # Determine which letter file to read
    first_char = query_lower[0].lower()
    if not first_char.isalpha():
        first_char = '_'
    filepath = os.path.join(DATA_DIR, f"{first_char}.data")

    if not os.path.exists(filepath):
        return entries

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 4)  # word url origin depth frequency
            if len(parts) < 5:
                continue
            word, url, origin, depth_str, freq_str = parts
            if word.lower() == query_lower:
                try:
                    entries.append({
                        "word": word,
                        "url": url,
                        "origin": origin,
                        "depth": int(depth_str),
                        "frequency": int(freq_str),
                    })
                except ValueError:
                    continue
    return entries


def _get_page_title(url):
    """Look up page title from database."""
    try:
        conn = db._get_conn()
        row = conn.execute("SELECT title FROM pages WHERE url = ?", (url,)).fetchone()
        return row["title"] if row else ""
    except Exception:
        return ""


def search(query, sort_by="relevance"):
    """Search the inverted index for the given query.

    Scoring formula: score = (frequency × 10) + 1000 (exact match bonus) − (depth × 5)

    Args:
        query: search string (can be multiple words)
        sort_by: 'relevance' (default) sorts by score descending

    Returns:
        list of result dicts sorted by relevance
    """
    words = normalize_text(query).split()
    if not words:
        return []

    # Aggregate scores per URL across all query words
    url_scores = defaultdict(lambda: {
        "url": "",
        "origin": "",
        "depth": 0,
        "total_score": 0,
        "title": "",
        "frequencies": {},
    })

    for word in words:
        entries = _load_pdata_entries(word)
        for entry in entries:
            url = entry["url"]
            freq = entry["frequency"]
            depth = entry["depth"]

            # Scoring formula: (frequency × 10) + 1000 (exact match bonus) − (depth × 5)
            score = (freq * 10) + 1000 - (depth * 5)

            if url not in url_scores or url_scores[url]["url"] == "":
                url_scores[url]["url"] = url
                url_scores[url]["origin"] = entry["origin"]
                url_scores[url]["depth"] = depth

            url_scores[url]["total_score"] += score
            url_scores[url]["frequencies"][word] = freq

    # Build results list
    results = []
    for url, data in url_scores.items():
        title = _get_page_title(url)
        results.append({
            "url": data["url"],
            "origin_url": data["origin"],
            "depth": data["depth"],
            "title": title,
            "relevance_score": data["total_score"],
            "frequencies": data["frequencies"],
        })

    # Sort by relevance score (descending)
    if sort_by == "relevance":
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return results
