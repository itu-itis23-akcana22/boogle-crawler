/**
 * app.js — Search page logic
 * Autocomplete on typing (not auto-search), search on button click/Enter,
 * "I'm Feeling Lucky", status indicator.
 */

const searchInput = document.getElementById("searchInput");
const clearBtn = document.getElementById("clearBtn");
const searchBtn = document.getElementById("searchBtn");
const resultsArea = document.getElementById("resultsArea");
const searchHero = document.getElementById("searchHero");
const luckyBtn = document.getElementById("luckyBtn");
const dropdown = document.getElementById("autocompleteDropdown");
const wrapper = document.querySelector(".search-bar-wrapper");

let debounceTimer = null;
let activeIndex = -1;
let suggestions = [];
let autocompleteCache = {};
let lastRequestedPrefix = "";

// ── Autocomplete on typing ─────────────────────────────────
searchInput.addEventListener("input", () => {
    const q = searchInput.value.trim();
    clearBtn.classList.toggle("visible", q.length > 0);

    clearTimeout(debounceTimer);

    if (q.length < 1) {
        closeDropdown();
        return;
    }

    debounceTimer = setTimeout(() => {
        fetchAutocomplete(q);
    }, 280);
});

async function fetchAutocomplete(prefix) {
    if (autocompleteCache[prefix]) {
        suggestions = autocompleteCache[prefix];
        activeIndex = -1;
        if (document.activeElement === searchInput) {
            renderDropdown(suggestions);
        }
        return;
    }

    if (prefix === lastRequestedPrefix) return;
    lastRequestedPrefix = prefix;

    try {
        const res = await fetch(`/api/autocomplete?q=${encodeURIComponent(prefix)}`);
        const data = await res.json();
        suggestions = data.suggestions || [];
        autocompleteCache[prefix] = suggestions;
        activeIndex = -1;
        // Only show if the input is still focused
        if (document.activeElement === searchInput) {
            renderDropdown(suggestions);
        }
    } catch (e) {
        closeDropdown();
    }
}

function renderDropdown(items) {
    if (!items.length) {
        closeDropdown();
        return;
    }

    dropdown.innerHTML = items
        .map(
            (word, i) =>
                `<div class="autocomplete-item" data-index="${i}">${esc(word)}</div>`
        )
        .join("");

    dropdown.classList.add("open");
    wrapper.classList.add("dropdown-open");

    // Click handlers
    dropdown.querySelectorAll(".autocomplete-item").forEach((el) => {
        el.addEventListener("mousedown", (e) => {
            e.preventDefault();
            searchInput.value = el.textContent;
            closeDropdown();
            performSearch(el.textContent);
        });
    });
}

function closeDropdown() {
    dropdown.classList.remove("open");
    wrapper.classList.remove("dropdown-open");
    dropdown.innerHTML = "";
    suggestions = [];
    activeIndex = -1;
}

// ── Keyboard navigation in autocomplete ─────────────────────
searchInput.addEventListener("keydown", (e) => {
    const items = dropdown.querySelectorAll(".autocomplete-item");

    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!items.length) return;
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
        updateActiveItem(items);
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!items.length) return;
        activeIndex = Math.max(activeIndex - 1, 0);
        updateActiveItem(items);
    } else if (e.key === "Enter") {
        e.preventDefault();
        if (activeIndex >= 0 && items[activeIndex]) {
            searchInput.value = items[activeIndex].textContent;
            closeDropdown();
        }
        performSearch(searchInput.value.trim());
    } else if (e.key === "Escape") {
        closeDropdown();
    }
});

function updateActiveItem(items) {
    items.forEach((el, i) => {
        el.classList.toggle("active", i === activeIndex);
    });
    if (activeIndex >= 0 && items[activeIndex]) {
        searchInput.value = items[activeIndex].textContent;
    }
}

// ── Close dropdown on blur / click-away ────────────────────
searchInput.addEventListener("blur", () => {
    // Small delay so mousedown on dropdown items fires first
    setTimeout(closeDropdown, 200);
});

searchInput.addEventListener("focus", () => {
    const q = searchInput.value.trim();
    if (q.length >= 1) {
        fetchAutocomplete(q);
    }
});

// Close dropdown when clicking anywhere outside the search bar
document.addEventListener("click", (e) => {
    if (!wrapper.contains(e.target)) {
        closeDropdown();
    }
});

// ── Search Button ───────────────────────────────────────────
searchBtn.addEventListener("click", () => {
    closeDropdown();
    const q = searchInput.value.trim();
    if (q) performSearch(q);
});

// ── Clear button ────────────────────────────────────────────
clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    clearBtn.classList.remove("visible");
    resultsArea.innerHTML = "";
    searchHero.classList.remove("has-results");
    closeDropdown();
    searchInput.focus();
});

let currentSearchData = null;
let currentSearchPage = 1;
const ITEMS_PER_PAGE = 30;

// ── Search function ─────────────────────────────────────────
async function performSearch(query) {
    if (!query) return;
    searchInput.blur();
    closeDropdown();
    resultsArea.innerHTML = '<p class="results-loading">Searching…</p>';
    searchHero.classList.add("has-results");

    try {
        const res = await fetch(
            `/search?query=${encodeURIComponent(query)}&sortBy=relevance`
        );
        currentSearchData = await res.json();
        currentSearchPage = 1;
        renderSearchResults();
    } catch (err) {
        resultsArea.innerHTML = `<p class="results-empty">Error: ${err.message}</p>`;
    }
}

function renderSearchResults() {
    if (!currentSearchData || !currentSearchData.results || currentSearchData.results.length === 0) {
        resultsArea.innerHTML = '<p class="results-empty">No results found.</p>';
        return;
    }

    const totalResults = currentSearchData.results.length;
    const totalPages = Math.ceil(totalResults / ITEMS_PER_PAGE);
    if (currentSearchPage > totalPages && totalPages > 0) currentSearchPage = totalPages;

    const start = (currentSearchPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const items = currentSearchData.results.slice(start, end);

    let html = `<p class="results-count">Page ${currentSearchPage} of ${totalPages} — ${currentSearchData.count} result${currentSearchData.count !== 1 ? "s" : ""} for "${esc(currentSearchData.query)}"</p>`;

    items.forEach((r, i) => {
        const title = r.title || "Untitled";
        const freqParts = r.frequencies ? Object.entries(r.frequencies).map(([w, f]) => `${w}:${f}`).join(", ") : "";
        html += `
            <div class="result-item" style="animation-delay:${(i % ITEMS_PER_PAGE) * 20}ms">
                <div class="result-url-line">${esc(r.url)}</div>
                <a class="result-title-link" href="${esc(r.url)}" target="_blank">${esc(title)}</a>
                <div class="result-meta">
                    <span>Origin: ${esc(r.origin_url)}</span>
                    <span>Depth: ${r.depth}</span>
                    <span>Freq: ${freqParts}</span>
                    <span class="result-score">Score: ${r.relevance_score}</span>
                </div>
            </div>
        `;
    });

    if (totalPages > 1) {
        html += `
            <div class="pagination">
                <button class="btn btn-small" onclick="changeSearchPage(-1)" ${currentSearchPage === 1 ? 'disabled' : ''}>Previous</button>
                <span>Page ${currentSearchPage} of ${totalPages}</span>
                <button class="btn btn-small" onclick="changeSearchPage(1)" ${currentSearchPage === totalPages ? 'disabled' : ''}>Next</button>
            </div>
        `;
    }

    resultsArea.innerHTML = html;
}

window.changeSearchPage = function (delta) {
    currentSearchPage += delta;
    renderSearchResults();
    window.scrollTo({ top: 0, behavior: "smooth" });
};

// ── I'm Feeling Lucky ──────────────────────────────────────
luckyBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/api/random-word");
        const data = await res.json();
        if (data.word) {
            searchInput.value = data.word;
            clearBtn.classList.add("visible");
            closeDropdown();
            performSearch(data.word);
        }
    } catch (err) {
        const fallback = [
            "book", "page", "home", "click", "read", "price", "star", "review",
        ];
        const word = fallback[Math.floor(Math.random() * fallback.length)];
        searchInput.value = word;
        clearBtn.classList.add("visible");
        closeDropdown();
        performSearch(word);
    }
});

// ── Status Indicator ────────────────────────────────────────
async function fetchStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const dot = document.getElementById("statusDot");
        const label = document.getElementById("statusLabel");

        if (data.active_crawlers > 0) {
            dot.classList.add("active");
            label.textContent = `Crawling (${data.total_pages_indexed} pages)`;
        } else {
            dot.classList.remove("active");
            label.textContent = `Idle · ${data.total_pages_indexed} pages`;
        }
    } catch (e) {
        /* ignore */
    }
}

fetchStatus();
setInterval(fetchStatus, 3000);

// ── Escape HTML ─────────────────────────────────────────────
function esc(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}
