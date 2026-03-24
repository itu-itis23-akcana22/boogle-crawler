/**
 * admin.js — Admin page logic
 * Crawl form submission (with max_urls), stop button, and auto-refreshing status.
 */

// ── Crawl Form ──────────────────────────────────────────────
document.getElementById("crawlForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const url = document.getElementById("crawlUrl").value.trim();
    const depth = parseInt(document.getElementById("crawlDepth").value, 10) || 2;
    const maxUrls =
        parseInt(document.getElementById("crawlMaxUrls").value, 10) || 0;
    const btn = document.getElementById("crawlBtn");
    const msg = document.getElementById("crawlMessage");

    if (!url) return;

    btn.textContent = "Starting…";
    btn.disabled = true;

    try {
        const res = await fetch("/api/index", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, depth, max_urls: maxUrls }),
        });
        const data = await res.json();

        if (res.ok) {
            msg.className = "message success";
            let info = `Crawl started — Session #${data.session_id} · ${data.origin_url} (depth ${data.max_depth}`;
            if (data.max_urls > 0) info += `, max ${data.max_urls} URLs`;
            info += ")";
            msg.textContent = info;
        } else {
            msg.className = "message error";
            msg.textContent = data.error || "Unknown error";
        }
        msg.style.display = "block";
    } catch (err) {
        msg.className = "message error";
        msg.textContent = `Network error: ${err.message}`;
        msg.style.display = "block";
    } finally {
        btn.textContent = "Start Crawl";
        btn.disabled = false;
    }

    fetchStatus();
});

// ── Stop Crawler ────────────────────────────────────────────
async function stopCrawler(sessionId) {
    try {
        const res = await fetch("/api/stop", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
        });
        const data = await res.json();
        if (data.stopped) {
            fetchStatus();
        }
    } catch (e) {
        /* ignore */
    }
}

// ── Status Refresh ──────────────────────────────────────────
async function fetchStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();

        document.getElementById("totalPages").textContent =
            data.total_pages_indexed || 0;
        document.getElementById("queueDepth").textContent =
            data.queue_depth || 0;
        document.getElementById("activeCrawlers").textContent =
            data.active_crawlers || 0;

        const anyThrottling = (data.jobs || []).some((j) => j.throttling);
        const throttleEl = document.getElementById("throttleStatus");
        throttleEl.textContent = anyThrottling ? "Yes" : "No";
        throttleEl.style.color = anyThrottling ? "#d97706" : "";

        // Global status
        const dot = document.getElementById("statusDot");
        const label = document.getElementById("statusLabel");
        if (data.active_crawlers > 0) {
            dot.classList.add("active");
            label.textContent = `Crawling (${data.total_pages_indexed} pages)`;
        } else {
            dot.classList.remove("active");
            label.textContent = `Idle · ${data.total_pages_indexed} pages`;
        }

        // Active jobs (with stop buttons)
        const jobsEl = document.getElementById("activeJobs");
        if (data.jobs && data.jobs.length > 0) {
            jobsEl.innerHTML = data.jobs
                .map(
                    (j) => `
                <div class="job-row">
                    <span class="job-url">${esc(j.origin_url)}</span>
                    <div class="job-details">
                        <span>Depth ${j.max_depth}</span>
                        <span>${j.pages_crawled} pages${j.max_urls > 0 ? " / " + j.max_urls + " max" : ""}</span>
                        <span>${j.throttling ? "⚠ Throttled" : ""}</span>
                    </div>
                    <button class="btn-stop" onclick="stopCrawler(${j.session_id})">Stop</button>
                    <span class="badge badge-running">Running</span>
                </div>
            `
                )
                .join("");
        } else {
            jobsEl.innerHTML = '<p class="empty-text">No active jobs</p>';
        }

        // Session history
        renderSessionHistory(data.sessions);
    } catch (e) {
        /* ignore */
    }
}

let currentHistoryPage = 1;
const historyPerPage = 10;

function renderSessionHistory(sessions) {
    const historyEl = document.getElementById("sessionHistory");
    if (!sessions || sessions.length === 0) {
        historyEl.innerHTML = '<p class="empty-text">No sessions yet</p>';
        return;
    }

    const totalPages = Math.ceil(sessions.length / historyPerPage);
    if (currentHistoryPage > totalPages && totalPages > 0) currentHistoryPage = totalPages;

    const start = (currentHistoryPage - 1) * historyPerPage;
    const end = start + historyPerPage;
    const items = sessions.slice(start, end);

    let html = items.map(s => `
        <div class="job-row">
            <span class="job-url">${esc(s.origin_url)}</span>
            <div class="job-details">
                <span>Depth ${s.max_depth}</span>
                <span>${s.pages_crawled} pages</span>
                <span>${s.created_at}</span>
            </div>
            <span class="badge badge-${s.status}">${s.status}</span>
        </div>
    `).join("");

    if (totalPages > 1) {
        html += `
            <div class="pagination">
                <button class="btn btn-small" onclick="changeHistoryPage(-1)" ${currentHistoryPage === 1 ? 'disabled' : ''}>Previous</button>
                <span>Page ${currentHistoryPage} of ${totalPages}</span>
                <button class="btn btn-small" onclick="changeHistoryPage(1)" ${currentHistoryPage === totalPages ? 'disabled' : ''}>Next</button>
            </div>
        `;
    }

    historyEl.innerHTML = html;
}

window.changeHistoryPage = function (delta) {
    currentHistoryPage += delta;
    fetchStatus();
};

function esc(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

// ── Clear All ───────────────────────────────────────────────
document.getElementById("clearAllBtn").addEventListener("click", async () => {
    if (!confirm("Are you sure? This will stop all crawlers, delete all indexed data, and remove the inverted index file. This cannot be undone.")) {
        return;
    }

    const btn = document.getElementById("clearAllBtn");
    const msg = document.getElementById("clearMessage");
    btn.textContent = "Clearing…";
    btn.disabled = true;

    try {
        const res = await fetch("/api/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        const data = await res.json();

        if (data.cleared) {
            msg.className = "message success";
            msg.textContent = "All data has been cleared successfully.";
        } else {
            msg.className = "message error";
            msg.textContent = "Failed to clear data.";
        }
        msg.style.display = "block";
    } catch (err) {
        msg.className = "message error";
        msg.textContent = `Error: ${err.message}`;
        msg.style.display = "block";
    } finally {
        btn.textContent = "Clear All Data";
        btn.disabled = false;
    }

    fetchStatus();
});

fetchStatus();
setInterval(fetchStatus, 3000);
