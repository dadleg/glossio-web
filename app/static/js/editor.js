let currentSegmentId = null;
let currentTmMatch = null;
let currentBibleData = null;
let segments = [];
let totalSegments = 0;

// Initialize from Config
if (window.GLOSSIO_CONFIG) {
    segments = window.GLOSSIO_CONFIG.segments || [];
    totalSegments = segments.length;
}

const targetLangCode = (window.GLOSSIO_CONFIG && window.GLOSSIO_CONFIG.targetLang) ? window.GLOSSIO_CONFIG.targetLang.toUpperCase() : "EN";
const currentUserId = window.GLOSSIO_CONFIG ? window.GLOSSIO_CONFIG.userId : null;

// getUserColor is now in socket_client.js attached to window

// --- Progress Logic ---
function updateProgress() {
    const translatedCount = document.querySelectorAll('.segment-item.translated').length;
    const percent = totalSegments > 0 ? Math.round((translatedCount / totalSegments) * 100) : 0;

    const textEl = document.getElementById('progress-text');
    if (textEl) textEl.innerText = `${translatedCount}/${totalSegments}`;

    const barEl = document.getElementById('progress-bar');
    if (barEl) {
        barEl.style.width = `${percent}%`;
        barEl.innerText = `${percent}%`;
    }
}

// --- Context Logic ---
function toggleContext() {
    const panel = document.getElementById('context-panel');
    if (panel) panel.classList.toggle('show');
}

function mergeParagraph() {
    if (!currentSegmentId) return;

    if (!confirm("This will merge all segments in this paragraph into one. Continue?")) return;

    if (window.currentParaId) {
        fetch(`/api/paragraph/${window.currentParaId}/merge`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    // Reload and jump to new segment
                    window.location.href = window.location.pathname + "?segment=" + data.new_segment_id;
                } else {
                    alert("No changes or error.");
                }
            });
    }
}

// --- Notes Logic ---
function toggleNotes() {
    const container = document.getElementById('notes-container');
    if (container) container.classList.toggle('show');
}

function loadSegment(id) {
    if (currentSegmentId && currentSegmentId !== id) {
        saveSegment(currentSegmentId);
    }

    currentSegmentId = id;

    document.querySelectorAll('.segment-item').forEach(el => el.classList.remove('active'));
    const item = document.getElementById(`seg-item-${id}`);
    if (item) {
        item.classList.add('active');
        item.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    fetch(`/api/segment/${id}`)
        .then(r => r.json())
        .then(data => {
            window.currentParaId = data.paragraph_id;

            // Source Text (Highlight Links)
            const sourceDisplay = document.getElementById('source-display');
            // Escape HTML first to prevent XSS if we are setting innerHTML
            const safeText = data.source_text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

            sourceDisplay.innerHTML = highlightRefs(safeText, data.bible_data, data.egw_data);

            document.getElementById('context-text').innerText = data.paragraph_context;
            document.getElementById('target-input').value = data.target_text || "";
            document.getElementById('note-input').value = data.note || "";

            // --- Info Panel Dynamic Visibility ---

            // TM Info
            currentTmMatch = data.tm_match;
            const tmSection = document.getElementById('section-tm');
            const tmSpan = document.getElementById('tm-match-text');

            if (data.tm_match) {
                tmSpan.innerText = `${data.tm_score}% - ${data.tm_match}`;
                tmSpan.className = data.tm_score === 100 ? "text-success" : "text-warning";
                tmSection.style.display = 'block';
            } else {
                tmSection.style.display = 'none';
            }

            // Glossary
            const glosSection = document.getElementById('section-glossary');
            const glosSpan = document.getElementById('glossary-text');

            if (data.glossary_matches && data.glossary_matches.length > 0) {
                glosSpan.innerText = data.glossary_matches.map(m => `${m[0]}->${m[1]}`).join(', ');
                glosSpan.className = "text-danger";
                glosSection.style.display = 'block';
            } else {
                glosSection.style.display = 'none';
            }

            // Links
            const linksSection = document.getElementById('section-resources');
            const linksSpan = document.getElementById('links-text');
            linksSpan.innerHTML = "";
            let hasLinks = false;

            if (data.bible_data) {
                linksSpan.innerHTML += `<a href="${data.bible_data.en}" target="_blank" class="me-2 btn btn-sm btn-outline-primary">See on BibleGateway</a>`;
                hasLinks = true;
            }

            if (data.egw_data && data.egw_data.en) {
                linksSpan.innerHTML += `<a href="${data.egw_data.en}" target="_blank" class="me-2 btn btn-sm btn-outline-info">EGW</a>`;
                hasLinks = true;
            }

            if (hasLinks) {
                linksSection.style.display = 'block';
            } else {
                linksSection.style.display = 'none';
            }

            // Last Modified Log & Color
            const logDiv = document.getElementById('last-modified-log');
            const targetInput = document.getElementById('target-input');

            if (data.last_modified_by_name) {
                // Format date nicely
                const date = new Date(data.last_modified_at);
                const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                logDiv.innerText = `Last edited by ${data.last_modified_by_name} on ${dateStr}`;

                // Color logic: Only if shared project (implied if last_modified_by_name is present and different?)
                // User request: "Color does not change solo-working". 
                // Let's assume if last_modified_by_name != current user name, or just always apply color if present?
                // "This only will happen when the project has been shared with someone."
                // We can check if we are in a shared project context, but simple heuristic:
                // If last_modified_by_name is set, use it.

                const color = getUserColor(data.last_modified_by_name);
                targetInput.style.color = color;
            } else {
                logDiv.innerText = '';
                targetInput.style.color = 'inherit';
            }
        });
}

function saveSegment(id) {
    if (!id) return;
    const target = document.getElementById('target-input').value;
    const note = document.getElementById('note-input').value;
    const statusInd = document.getElementById('status-indicator');

    if (statusInd) {
        statusInd.innerText = "Saving...";
        statusInd.className = "badge bg-warning text-dark border";
    }

    fetch(`/api/segment/${id}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_text: target, note: note })
    }).then(r => {
        if (statusInd) {
            statusInd.innerText = "Saved";
            statusInd.className = "badge bg-light text-dark border";
        }

        const item = document.getElementById(`seg-item-${id}`);
        if (item) {
            if (target.trim()) {
                item.classList.add('translated');
            } else {
                item.classList.remove('translated');
            }

            // Note indicator
            if (note.trim()) {
                item.classList.add('has-note');
            } else {
                item.classList.remove('has-note');
            }
        }
        updateProgress();

        // Emit socket event
        if (typeof emitSegmentUpdate === 'function') {
            emitSegmentUpdate(id, target, note);
        }
    });
}

const targetInput = document.getElementById('target-input');
if (targetInput) {
    targetInput.addEventListener('blur', () => {
        saveSegment(currentSegmentId);
    });

    // Typing indicator
    targetInput.addEventListener('input', () => {
        if (typeof emitTyping === 'function') {
            emitTyping(currentSegmentId);
        }
    });
}

function nextSegment() {
    const idx = segments.indexOf(currentSegmentId);
    if (idx >= 0 && idx < segments.length - 1) {
        loadSegment(segments[idx + 1]);
    }
}

function prevSegment() {
    const idx = segments.indexOf(currentSegmentId);
    if (idx > 0) {
        loadSegment(segments[idx - 1]);
    }
}

function copySource() {
    const src = document.getElementById('source-display').innerText;
    document.getElementById('target-input').value = src;
    saveSegment(currentSegmentId);
}

function useTM() {
    if (currentTmMatch) {
        document.getElementById('target-input').value = currentTmMatch;
        saveSegment(currentSegmentId);
    }
}

function requestMT() {
    const text = document.getElementById('source-display').innerText;

    // Get Key from LocalStorage
    const apiKey = localStorage.getItem('glossio_deepl_key');
    if (!apiKey) {
        alert("Please configure your DeepL API Key in Settings first.");
        // Open settings
        const modal = new bootstrap.Modal(document.getElementById('settingsModal'));
        modal.show();
        return;
    }

    // Check for overridden target lang
    const overrideLang = localStorage.getItem('glossio_target_lang');
    const finalLang = overrideLang || targetLangCode;

    const statusInd = document.getElementById('status-indicator');
    if (statusInd) {
        statusInd.innerText = "Translating...";
        statusInd.className = "badge bg-info text-dark border";
    }

    fetch('/api/translate/mt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text: text,
            target_lang: finalLang,
            api_key: apiKey
        })
    }).then(r => r.json())
        .then(data => {
            if (statusInd) {
                statusInd.innerText = "Saved";
                statusInd.className = "badge bg-light text-dark border";
            }

            if (data.translation) {
                document.getElementById('target-input').value = data.translation;
                saveSegment(currentSegmentId);
            } else {
                alert("MT Error: " + (data.error || "Unknown"));
            }
        });
}

function mergePrev() {
    if (!confirm("Merge with previous segment?")) return;
    fetch(`/api/segment/${currentSegmentId}/merge_prev`, {
        method: 'POST'
    }).then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                // Reload and jump to the merged segment (new_id is the previous segment ID)
                window.location.href = window.location.pathname + "?segment=" + data.new_id;
            } else {
                alert(data.message);
            }
        });
}

// Keyboard Shortcuts
document.addEventListener('keydown', function (e) {
    if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); nextSegment(); }
    if (e.ctrlKey && e.key === 'ArrowDown') { e.preventDefault(); nextSegment(); }
    if (e.ctrlKey && e.key === 'ArrowUp') { e.preventDefault(); prevSegment(); }
    if (e.ctrlKey && e.key === 'i') { e.preventDefault(); copySource(); }
    if (e.ctrlKey && e.key === 't') { e.preventDefault(); useTM(); }
    if (e.ctrlKey && e.key === 'j') { e.preventDefault(); mergePrev(); }
});

function performSearch() {
    const query = document.getElementById('search-query').value.trim();
    const type = document.getElementById('search-type').value;
    const resultsDiv = document.getElementById('search-results');
    const projectId = window.GLOSSIO_CONFIG ? window.GLOSSIO_CONFIG.projectId : null;

    if (!query || !projectId) return;

    // Check for Go To Segment pattern (e.g. "1.1")
    if (/^\d+\.\d+$/.test(query)) {
        fetch(`/api/segment/get_by_display_id?project_id=${projectId}&display_id=${query}`)
            .then(r => r.json())
            .then(data => {
                if (data.segment_id) {
                    loadSegment(data.segment_id);
                    // Close modal
                    const modal = bootstrap.Modal.getInstance(document.getElementById('searchModal'));
                    modal.hide();
                } else {
                    resultsDiv.innerHTML = '<div class="text-center text-danger">Segment not found</div>';
                }
            });
        return;
    }

    resultsDiv.innerHTML = '<div class="text-center">Searching...</div>';

    fetch(`/api/project/${projectId}/search?q=${encodeURIComponent(query)}&type=${type}`)
        .then(r => r.json())
        .then(data => {
            resultsDiv.innerHTML = '';
            if (data.length === 0) {
                resultsDiv.innerHTML = '<div class="text-center">No results found</div>';
                return;
            }

            data.forEach(item => {
                const el = document.createElement('a');
                el.href = '#';
                el.className = 'list-group-item list-group-item-action';
                el.innerHTML = `<b>[${item.p_idx + 1}.${item.s_idx + 1}]</b> ${item.match_text}`;
                el.onclick = (e) => {
                    e.preventDefault();
                    loadSegment(item.id);
                    // Close modal
                    const modalEl = document.getElementById('searchModal');
                    const modal = bootstrap.Modal.getInstance(modalEl);
                    modal.hide();
                };
                resultsDiv.appendChild(el);
            });
        });
}

const searchQuery = document.getElementById('search-query');
if (searchQuery) {
    searchQuery.addEventListener('keyup', function (e) {
        if (e.key === 'Enter') performSearch();
    });
}

// --- Bible Logic Refactored (Manual Selectors) ---

function initBible() {
    // Fetch languages list from Bolls (via Backend Proxy)
    fetch('/api/bible/versions')
        .then(r => r.json())
        .then(data => {
            const select = document.getElementById('bible-version-select');
            if (!select) return;
            select.innerHTML = '';

            let count = 0;
            data.forEach(langNode => {
                if (langNode.translations) {
                    langNode.translations.forEach(t => {
                        const opt = document.createElement('option');
                        opt.value = t.short_name;
                        opt.innerText = `${t.full_name} (${langNode.language})`;
                        select.appendChild(opt);
                        count++;
                    });
                }
            });

            if (count === 0) {
                select.add(new Option("No translations found", ""));
            } else {
                // Auto-select logic
                const LANG_MAP = {
                    'EN': ['English'], 'ES': ['Spanish', 'Español'], 'FR': ['French', 'Français'],
                    'DE': ['German', 'Deutsch'], 'PT': ['Portuguese', 'Português'],
                    'IT': ['Italian', 'Italiano'], 'RU': ['Russian', 'Русский'],
                    'ZH': ['Chinese', '中文']
                };
                const keywords = (LANG_MAP[targetLangCode.substring(0, 2)] || []).map(s => s.toLowerCase());
                if (keywords.length > 0) {
                    for (let i = 0; i < select.options.length; i++) {
                        if (keywords.some(k => select.options[i].text.toLowerCase().includes(k))) {
                            select.selectedIndex = i;
                            break;
                        }
                    }
                }
            }

            // Trigger Book fetch for selected version
            onVersionChange();
        })
        .catch(e => alert("Bible versions load error: " + e.message));
}

// Call on load
initBible();

function onVersionChange() {
    const version = document.getElementById('bible-version-select').value;
    if (!version) return;

    fetch(`/api/bible/books/${version}`)
        .then(r => r.json())
        .then(data => {
            const bookSelect = document.getElementById('bible-book-select');
            if (!bookSelect) return;
            bookSelect.innerHTML = '<option value="">Select Book...</option>';
            data.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b.bookid; // Int
                opt.innerText = b.name;
                bookSelect.appendChild(opt);
            });
        });
}

function fetchCustomBibleText() {
    const version = document.getElementById('bible-version-select').value;
    const book = document.getElementById('bible-book-select').value;
    const chapter = document.getElementById('bible-chapter-input').value;
    const verseInput = document.getElementById('bible-verse-input').value.trim();

    if (!version || !book || !chapter) {
        alert("Please select Version, Book and Chapter.");
        return;
    }

    const display = document.getElementById('bible-content-area');
    display.innerText = "Loading...";

    // Fetch full chapter
    fetch(`/api/bible/text/${version}/${book}/${chapter}`)
        .then(r => r.json())
        .then(data => {
            // data is Array of {verse, text, pk}
            if (!Array.isArray(data) || data.length === 0) {
                display.innerText = "No text found.";
                return;
            }

            let filtered = [];
            // Parse verse input: "1" or "2-5" or empty (all)
            if (verseInput) {
                if (verseInput.includes('-')) {
                    const parts = verseInput.split('-');
                    const start = parseInt(parts[0]);
                    const end = parseInt(parts[1]);
                    filtered = data.filter(v => v.verse >= start && v.verse <= end);
                } else {
                    const vNum = parseInt(verseInput);
                    filtered = data.filter(v => v.verse === vNum);
                }
            } else {
                filtered = data; // All
            }

            if (filtered.length === 0) {
                display.innerText = "Verses not found in chapter.";
                return;
            }

            // Format output
            let html = filtered.map(v => {
                // Strip existing HTML tags in text?
                let doc = new DOMParser().parseFromString(v.text, 'text/html');
                return `<p><sup>${v.verse}</sup> ${doc.body.textContent}</p>`;
            }).join("");

            display.innerHTML = html;
        })
        .catch(e => display.innerText = "Error: " + e.message);
}

function setBibleSelector(bookId, chapter, verse) {
    // Set values
    const bookSelect = document.getElementById('bible-book-select');
    const chInput = document.getElementById('bible-chapter-input');
    const vInput = document.getElementById('bible-verse-input');

    bookSelect.value = bookId;
    chInput.value = chapter;
    vInput.value = verse;

    // Trigger fetch
    fetchCustomBibleText();
}

function highlightRefs(text, bibleData, egwData) {
    let html = text;

    // Escape helper for regex
    const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    // Highlight EGW
    if (egwData && egwData.match && egwData.en) {
        const pattern = new RegExp(escapeRegExp(egwData.match), 'g');
        html = html.replace(pattern, `<a href="${egwData.en}" target="_blank" class="text-info text-decoration-underline fw-bold">${egwData.match}</a>`);
    }

    // Highlight Bible
    if (bibleData && bibleData.api_data && bibleData.match) {
        const { book_id, chapter, verse } = bibleData.api_data;
        const pattern = new RegExp(escapeRegExp(bibleData.match), 'g');
        html = html.replace(pattern, `<a href="#" class="text-primary text-decoration-underline fw-bold" onclick="setBibleSelector(${book_id}, ${chapter}, '${verse}'); return false;">${bibleData.match}</a>`);
    }

    return html;
}

function pasteBibleText() {
    const text = document.getElementById('bible-content-area').innerText;
    if (text && !text.startsWith("Loading") && !text.startsWith("Error")) {
        const target = document.getElementById('target-input');
        target.value = text;
        saveSegment(currentSegmentId);
    }
}

// Initial load check for query param
const urlParams = new URLSearchParams(window.location.search);
const startSeg = urlParams.get('segment');
if (startSeg) {
    loadSegment(startSeg);
    window.history.replaceState({}, document.title, window.location.pathname);
} else {
    // Requires segments to be loaded in GLOSSIO_CONFIG
    if (segments.length > 0) {
        loadSegment(segments[0]);
    }
}
updateProgress();
