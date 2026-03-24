"""
crawler.py — BFS web crawler with back pressure, threading, and SQLite persistence.
Uses urllib for HTTP requests and html.parser for parsing (via parser.py).
"""

import threading
import time
import os
import ssl
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter

import database as db
from parser import parse_html
from normalize import tokenize as _tokenize

# ── Configuration ──────────────────────────────────────────────
MAX_WORKERS = 5
MAX_QUEUE_SIZE = 500
REQUEST_DELAY = 0.35  # seconds between requests per worker
REQUEST_TIMEOUT = 12  # seconds
MAX_PAGE_SIZE = 2 * 1024 * 1024  # 2 MB
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# ── Data file path ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "storage")

# ── Global state ────────────────────────────────────────────────
_crawlers = {}  # session_id -> CrawlJob
_lock = threading.Lock()


class CrawlJob:
    """Manages a single crawl session with BFS traversal."""

    def __init__(self, session_id, origin_url, max_depth, max_urls=0):
        self.session_id = session_id
        self.origin_url = origin_url
        self.max_depth = max_depth
        self.max_urls = max_urls  # 0 = unlimited
        self.visited = set()
        self.running = True
        self.throttling = False
        self.pages_crawled = 0
        self._lock = threading.Lock()

    def reached_max_urls(self):
        """Check if we've hit the max URL limit."""
        if self.max_urls <= 0:
            return False
        with self._lock:
            return self.pages_crawled >= self.max_urls

    def mark_visited(self, url):
        with self._lock:
            self.visited.add(url)

    def is_visited(self, url):
        with self._lock:
            return url in self.visited


def _fetch_url(url):
    """Fetch a URL using urllib. Returns (content_str, final_url) or raises."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })
    response = urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx)

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "text/xml" not in content_type:
        raise ValueError(f"Non-HTML content type: {content_type}")

    data = response.read(MAX_PAGE_SIZE)
    encoding = "utf-8"
    # Try to detect encoding from Content-Type header
    ct = response.headers.get("Content-Type", "")
    if "charset=" in ct:
        encoding = ct.split("charset=")[-1].strip()

    try:
        content = data.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError):
        content = data.decode("utf-8", errors="replace")

    return content, response.url


def _write_to_pdata(url, origin_url, depth, text):
    """Append word frequency entries to data/storage/[letter].data files."""
    words = _tokenize(text)
    if not words:
        return

    freq = Counter(words)
    os.makedirs(DATA_DIR, exist_ok=True)

    # Group words by first letter
    letter_lines = {}
    for word, count in freq.items():
        first_char = word[0].lower() if word else '_'
        if not first_char.isalpha():
            first_char = '_'
        if first_char not in letter_lines:
            letter_lines[first_char] = []
        letter_lines[first_char].append(f"{word} {url} {origin_url} {depth} {count}\n")

    # Write each group to its corresponding [letter].data file
    for letter, lines in letter_lines.items():
        filepath = os.path.join(DATA_DIR, f"{letter}.data")
        with open(filepath, "a", encoding="utf-8") as f:
            f.writelines(lines)


def _crawl_worker(job, url, origin_url, depth):
    """Crawl a single URL: fetch, parse, save, enqueue children."""
    if job.is_visited(url) or db.is_visited(url):
        return []

    try:
        time.sleep(REQUEST_DELAY)  # Rate limiting
        content, final_url = _fetch_url(url)
    except Exception as e:
        return []

    # Mark visited
    job.mark_visited(url)
    if final_url != url:
        job.mark_visited(final_url)

    # Parse
    result = parse_html(content, base_url=final_url)
    title = result["title"] or ""
    body_text = result["body_text"] or ""
    links = result["links"]

    # Save to database
    db.save_page(url, origin_url, depth, title, body_text)
    db.increment_session_pages(job.session_id)

    # Write to inverted index file
    full_text = title + " " + body_text
    _write_to_pdata(url, origin_url, depth, full_text)

    with job._lock:
        job.pages_crawled += 1

    # Check max URL limit
    if job.reached_max_urls():
        return []

    # Collect child URLs (only if we haven't hit max depth)
    child_entries = []
    if depth < job.max_depth:
        for link in links:
            if not job.is_visited(link) and not db.is_visited(link):
                child_entries.append((link, origin_url, depth + 1))

    return child_entries


def _run_crawl(job):
    """Main crawl loop for a session. Uses a thread pool with back pressure."""
    try:
        # Load visited set from existing pages
        all_pages = db.get_all_pages()
        for page in all_pages:
            job.mark_visited(page["url"])

        # Check for pending queue items (resumability)
        pending = db.pop_from_queue(job.session_id, limit=MAX_QUEUE_SIZE)
        queue = [(p["url"], p["origin_url"], p["depth"]) for p in pending]

        # If queue is empty, seed with origin URL
        if not queue and not job.is_visited(job.origin_url):
            queue.append((job.origin_url, job.origin_url, 0))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while queue and job.running and not job.reached_max_urls():
                # Back pressure: cap the queue
                if len(queue) > MAX_QUEUE_SIZE:
                    job.throttling = True
                    # Persist overflow to database for later
                    overflow = queue[MAX_QUEUE_SIZE:]
                    queue = queue[:MAX_QUEUE_SIZE]
                    db.add_to_queue_bulk(overflow, job.session_id)
                else:
                    job.throttling = False

                # Submit batch
                batch = queue[:MAX_WORKERS]
                queue = queue[MAX_WORKERS:]

                futures = []
                for url, origin, depth in batch:
                    if job.is_visited(url) or db.is_visited(url):
                        continue
                    f = executor.submit(_crawl_worker, job, url, origin, depth)
                    futures.append(f)

                # Collect results
                for f in futures:
                    if not job.running:
                        break
                    try:
                        children = f.result(timeout=REQUEST_TIMEOUT + 5)
                        queue.extend(children)
                    except Exception:
                        pass

                # Check for more pending items in DB if queue is empty
                if not queue:
                    pending = db.pop_from_queue(job.session_id, limit=MAX_QUEUE_SIZE)
                    queue = [(p["url"], p["origin_url"], p["depth"]) for p in pending]

        # Persist any remaining queue items
        if queue:
            db.add_to_queue_bulk(queue, job.session_id)

        if job.running:
            db.update_session_status(job.session_id, "done")
        else:
            db.update_session_status(job.session_id, "stopped")
    except Exception as e:
        db.update_session_status(job.session_id, "error")
    finally:
        job.running = False
        with _lock:
            if job.session_id in _crawlers:
                del _crawlers[job.session_id]


def start_crawl(origin_url, max_depth, max_urls=0):
    """Start a new crawl session in the background. Returns session_id."""
    db.init_db()
    session_id = db.create_session(origin_url, max_depth)
    job = CrawlJob(session_id, origin_url, max_depth, max_urls=max_urls)

    with _lock:
        _crawlers[session_id] = job

    thread = threading.Thread(target=_run_crawl, args=(job,), daemon=True)
    thread.start()

    return session_id


def stop_crawl(session_id):
    """Stop a running crawl by session_id. Returns True if stopped."""
    with _lock:
        job = _crawlers.get(session_id)
    if job and job.running:
        job.running = False
        return True
    return False


def get_crawler_status():
    """Get global crawler status for the status API."""
    with _lock:
        active_jobs = []
        for sid, job in _crawlers.items():
            active_jobs.append({
                "session_id": sid,
                "origin_url": job.origin_url,
                "max_depth": job.max_depth,
                "max_urls": job.max_urls,
                "pages_crawled": job.pages_crawled,
                "throttling": job.throttling,
                "running": job.running,
            })

    return {
        "active_crawlers": len(active_jobs),
        "jobs": active_jobs,
        "total_pages_indexed": db.get_total_pages(),
        "queue_depth": db.get_queue_depth(),
    }
