# Boogle — Web Crawler & Search Engine

A simple web crawler and search engine built with Python, Flask and SQLite. Crawl websites to a configurable depth, index page content into letter-based files, and search through the index with relevance scoring. Built as an educational project.

**GitHub Repository:** [itu-itis23-akcana22/boogle-crawler](https://github.com/itu-itis23-akcana22/boogle-crawler) 

---

## How It Works

### Crawler

1. A crawl job is started with an origin URL, a max depth, and an optional URL cap.
2. A background thread begins **BFS traversal** of the origin URL using a thread pool (5 workers).
3. Each page is fetched with realistic browser headers (Chrome 122 User-Agent), parsed to extract visible text and links.
4. Extracted words are **tokenized and normalized** (Turkish characters mapped to ASCII equivalents, numbers and short words stripped).
5. Words are appended to **letter-based index files** — `a.data` for words starting with 'a', `b.data` for 'b', etc. — in the format:
   ```
   word  url  origin_url  depth  frequency
   ```
6. The crawled page URL, title, and body text are also stored in **SQLite** for deduplication and title lookups.
7. Back pressure is applied when the in-memory queue exceeds 500 URLs — overflow is persisted to SQLite and reloaded when the queue drains.

### Search Engine

1. The user query is normalized (Turkish chars, lowercase, tokenized).
2. For each query word, only the matching `[letter].data` file is opened and scanned — no full-index scan needed.
3. Each hit is scored: `score = (frequency × 10) + 1000 − (depth × 5)`. Scores are summed across all query words per URL.
4. Results are sorted by total score descending and returned with pagination (30 per page).

---

## Features

- **BFS crawling** up to configurable depth with 5 concurrent workers
- **Max URLs cap** — stop a crawl after N pages
- **Stop button** — halt any active crawl mid-run
- **Letter-based inverted index** (`a.data` … `z.data`) matching the PRD storage spec
- **Turkish character normalization** — searches for "ö" match "o" in the index
- **Autocomplete** — reads only the matching letter file, cached client-side
- **Relevance scoring** with origin depth weighting
- **Real-time admin dashboard** — start crawls, monitor queue/pages/throttle, view history
- **Pagination** — 30 results per page for search and session history
- **Clear All** — stops crawlers, truncates database (with VACUUM), and deletes all data files

---

## Requirements

- Python 3.11+

## Setup & Run

```bash
pip install -r requirements.txt
python app.py
```

Server starts on **http://localhost:5090**.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Search page |
| `/admin` | GET | Admin dashboard (crawl jobs, status, history) |
| `/api/index` | POST | Start a crawl — `{"url": "...", "depth": 2, "max_urls": 100}` |
| `/api/stop` | POST | Stop a crawl — `{"session_id": 1}` |
| `/api/status` | GET | System status (pages indexed, queue depth, active crawlers) |
| `/search?query=word&sortBy=relevance` | GET | Search the index |
| `/api/autocomplete?q=prefix` | GET | Autocomplete suggestions from index |
| `/api/random-word` | GET | Pick a random indexed word (for "I'm feeling lucky") |
| `/api/clear` | POST | Stop all crawlers, wipe database and all data files |

### Example: Start a Crawl

```bash
curl -X POST http://localhost:5090/api/index \
  -H "Content-Type: application/json" \
  -d '{"url": "https://books.toscrape.com", "depth": 2, "max_urls": 200}'
```

### Example: Search

```bash
curl "http://localhost:5090/search?query=python&sortBy=relevance"
```

---

## Project Structure

```
├── app.py              # Flask server + all API routes
├── crawler.py          # BFS crawler — threading, back pressure, rate limiting
├── database.py         # SQLite layer — pages, queue, sessions
├── parser.py           # HTML parser (stdlib html.parser) — links, title, body text
├── search.py           # Search engine — letter-file lookup, relevance scoring
├── normalize.py        # Turkish char normalization + tokenization
├── requirements.txt
├── data/
│   ├── storage/
│   │   ├── a.data      # Words starting with 'a': word url origin depth freq
│   │   ├── b.data
│   │   └── ... (one file per letter)
│   └── crawler.db      # SQLite — pages visited, URL queue, crawl sessions
├── templates/
│   ├── index.html      # Search page
│   └── admin.html      # Admin / crawler dashboard
└── static/
    ├── style.css
    ├── app.js           # Search UI — autocomplete, pagination, lucky button
    └── admin.js         # Admin UI — crawl form, stop button, session history
```

---

## Data Format — `data/storage/[letter].data`

Each line in a letter file represents one word occurrence on one page:

```
word url origin_url depth frequency
```

Example (`b.data`):
```
book https://books.toscrape.com/catalogue/page-2.html https://books.toscrape.com 1 12
books https://books.toscrape.com/ https://books.toscrape.com 0 3
```

---

## Known Limitations

- Single machine only — no distributed crawling
- Simple relevance scoring — frequency-based, no TF-IDF or PageRank
- No `robots.txt` compliance
- SSL verification disabled (educational project)
- Max depth capped at 10
- In-memory visited set can grow large for very deep crawls
