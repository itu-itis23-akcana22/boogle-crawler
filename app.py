"""
app.py — Flask web server for the web crawler + search engine.
Entry point: python app.py → runs on localhost:3600
"""

import os
import random

from flask import Flask, request, jsonify, render_template
import database as db
import crawler
import search as search_engine
from normalize import normalize_text

app = Flask(__name__)


@app.before_request
def ensure_db():
    """Ensure database is initialized before handling requests."""
    db.init_db()


# ── Pages ───────────────────────────────────────────────────────
@app.route("/")
def search_page():
    return render_template("index.html")


@app.route("/admin")
def admin_page():
    return render_template("admin.html")


# ── API: Start Crawl ────────────────────────────────────────────
@app.route("/api/index", methods=["POST"])
def api_index():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    depth = data.get("depth", 1)
    max_urls = data.get("max_urls", 0)

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        depth = int(depth)
    except (ValueError, TypeError):
        depth = 1
    try:
        max_urls = int(max_urls)
    except (ValueError, TypeError):
        max_urls = 0

    if depth < 0:
        depth = 0
    if depth > 10:
        depth = 10
    if max_urls < 0:
        max_urls = 0

    session_id = crawler.start_crawl(url, depth, max_urls=max_urls)
    return jsonify({
        "status": "started",
        "session_id": session_id,
        "origin_url": url,
        "max_depth": depth,
        "max_urls": max_urls,
    })


# ── API: Search (PRD format) ────────────────────────────────────
@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    results = search_engine.search(query, sort_by="relevance")
    return jsonify({
        "query": query,
        "count": len(results),
        "results": results,
    })


# ── API: Search (Homework format) ───────────────────────────────
@app.route("/search")
def search_endpoint():
    query = request.args.get("query", "").strip()
    sort_by = request.args.get("sortBy", "relevance").strip()

    if not query:
        return jsonify({"error": "Query parameter 'query' is required"}), 400

    results = search_engine.search(query, sort_by=sort_by)
    return jsonify({
        "query": query,
        "sortBy": sort_by,
        "count": len(results),
        "results": results,
    })


# ── API: Status ─────────────────────────────────────────────────
@app.route("/api/status")
def api_status():
    status = crawler.get_crawler_status()
    sessions = db.get_all_sessions()
    status["sessions"] = sessions
    return jsonify(status)


# ── API: Stop Crawl ─────────────────────────────────────────────
@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.get_json(force=True)
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    try:
        session_id = int(session_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid session_id"}), 400
    stopped = crawler.stop_crawl(session_id)
    return jsonify({"stopped": stopped, "session_id": session_id})


# ── API: Autocomplete ───────────────────────────────────────────
@app.route("/api/autocomplete")
def api_autocomplete():
    prefix = normalize_text(request.args.get("q", "").strip())
    limit = 10
    if not prefix or len(prefix) < 1:
        return jsonify({"suggestions": []})

    storage_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "storage")
    first_char = prefix[0].lower()
    if not first_char.isalpha():
        first_char = '_'
    filepath = os.path.join(storage_dir, f"{first_char}.data")

    if not os.path.exists(filepath):
        return jsonify({"suggestions": []})

    matches = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                word = line.split(" ", 1)[0]
                if word.startswith(prefix) and len(word) >= 2:
                    matches.add(word)
                    if len(matches) >= limit * 3:
                        break
    except Exception:
        pass

    sorted_matches = sorted(matches, key=lambda w: (len(w), w))[:limit]
    return jsonify({"suggestions": sorted_matches})


# ── API: Clear All ─────────────────────────────────────────────
@app.route("/api/clear", methods=["POST"])
def api_clear():
    # Stop all active crawlers first
    status = crawler.get_crawler_status()
    for job in status.get("jobs", []):
        crawler.stop_crawl(job["session_id"])

    # Clear database
    db.clear_all()

    # Delete all [letter].data files in storage
    storage_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "storage")
    if os.path.exists(storage_dir):
        import glob
        for f in glob.glob(os.path.join(storage_dir, "*.data")):
            os.remove(f)

    return jsonify({"cleared": True, "message": "All data has been removed."})


# ── API: Random Word (for "I'm Feeling Lucky") ─────────────────
@app.route("/api/random-word")
def api_random_word():
    storage_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "storage")
    if not os.path.exists(storage_dir):
        return jsonify({"word": "example"})

    import glob
    data_files = glob.glob(os.path.join(storage_dir, "*.data"))
    if not data_files:
        return jsonify({"word": "example"})

    # Pick a random letter file
    chosen_file = random.choice(data_files)
    try:
        words = set()
        with open(chosen_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 5000:
                    break
                parts = line.strip().split(" ", 1)
                if parts and len(parts[0]) >= 3:
                    words.add(parts[0])
        if words:
            return jsonify({"word": random.choice(list(words))})
    except Exception:
        pass

    return jsonify({"word": "search"})


# ── Entry Point ─────────────────────────────────────────────────
if __name__ == "__main__":
    db.init_db()
    print("=" * 50)
    print("  Boogle — Web Crawler + Search Engine")
    print("  Running on http://localhost:5090")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5090, debug=False)
