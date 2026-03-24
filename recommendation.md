# Recommendations for Production

## Storage
- Replace the letter-based flat files (`a.data`, `b.data`…) with a proper 'inverted index' using an engine like Elasticsearch or Apache Solr — handles sharding, replication, concurrent writes, and fuzzy matching out of the box.
- Move the visited URL set from SQLite into a key-value store (Redis with a Bloom filter) for O(1) membership checks at scale.
- Replace SQLite with PostgreSQL for the crawl metadata (sessions, queue) to enable concurrent writes from multiple crawler nodes without WAL contention.

## Crawler
- Implement `robots.txt` compliance and per-domain politeness delays before running against real targets.
- Move from a single-node thread pool to a 'distributed worker model' via a message queue (RabbitMQ, Kafka)  each worker pulls URLs, crawls, and pushes results independently. Scale workers horizontally on demand.
- Checkpoint crawl state so individual worker failures don't lose progress.

## Search
- Replace frequency scoring with a better algorithm and consider incorporating PageRank signals for more meaningful relevance.
- Add fuzzy matching and query expansion to handle misspellings.
- Cache hot queries in Redis with a short TTL.

## Search Quality Metrics
- Track DAU/MAU, click-through rate, and bounce rate to understand actual search value.
- Track time-to-first-result and zero-result rates to catch regressions.

## Serving
- Put Flask behind Nginx, containerize with Docker, and orchestrate with Kubernetes for auto-scaling and zero-downtime deploys.
- Add rate limiting and authentication to the admin API to prevent abuse.
