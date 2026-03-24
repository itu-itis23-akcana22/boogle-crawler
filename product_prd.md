# Product Requirements Document: Web Crawler + Search Engine

## Overview

Build a web crawler and search engine that runs entirely on localhost. The system exposes two core operations — **indexing** (crawling) and **searching** — plus a dashboard to monitor system state. Everything should be written in Python 3.11+.

## Core Requirements

### `index(origin, k)`

Given a starting URL and a depth `k`, crawl the web recursively up to `k` hops from the origin. Never crawl the same URL twice. The system should handle large crawls on a single machine, which means it needs to manage its own load — implement some form of back pressure (e.g. a bounded queue, a max worker count, or a rate limit) so the crawler doesn't overwhelm itself or the target.

### `search(query)`

Given a search string, return all relevant pages as a list of triples: `(relevant_url, origin_url, depth)`. Search must work while the indexer is still running, returning results from whatever has been indexed so far. Relevancy can be a simple heuristic — keyword frequency, title matching, or similar.

---

## Technical Constraints

- Use Python's standard library for the core crawl and parse logic — specifically `urllib` for HTTP and `html.parser` for parsing. Do not use Scrapy, BeautifulSoup, or similar libraries that do the heavy lifting out of the box.
- Flask (or equivalent minimal framework) is acceptable as the HTTP server layer only.
- Use SQLite for storage. No external databases or services.
- The entire application must start with a single command and run on `localhost`.
- `requirements.txt` should contain only what's absolutely necessary (ideally just `flask`).

## Dashboard / UI

Build a simple web UI (single HTML page is fine) that lets a user:

- Start a crawl by entering a URL and depth
- Run a search and see results
- Monitor system state in real time: Crawler Jobs, URLs processed, queue depth, whether back pressure is active

Auto-refresh the status panel every few seconds without requiring a page reload.

## API Endpoints

- `POST /api/index` — accepts `{ url, depth }`, starts crawling in the background, returns immediately
- `GET /api/search?q=<query>` — returns matching triples with title and relevancy score
- `GET /api/status` — returns current crawler state (processed count, queue depth, throttling status, active sessions)

## Persistence

If the crawler jobs are interrupted and restarted, it should be able to resume from where it left off rather than starting over. This means persisting both the visited set and the pending queue to SQLite.

