let currentSegmentId = null;
let currentTmMatch = null;
let currentBibleData = null;

let segments = [];
let totalSegments = 0;
let aiJobPollInterval = null;

// Initialize from Config
if (window.GLOSSIO_CONFIG) {
    segments = window.GLOSSIO_CONFIG.segments || [];
    totalSegments = segments.length;
}

const targetLangCode = (window.GLOSSIO_CONFIG && window.GLOSSIO_CONFIG.targetLang) ? window.GLOSSIO_CONFIG.targetLang.toUpperCase() : "EN";
const currentUserId = window.GLOSSIO_CONFIG ? window.GLOSSIO_CONFIG.userId : null;

// App-native confirmation modal helper
function showConfirm(message, onConfirm) {
    const modalEl = document.getElementById('confirmModal');
    const msgEl = document.getElementById('confirmModalMessage');
    const btnEl = document.getElementById('confirmModalBtn');

    if (!modalEl || !msgEl || !btnEl) {
        // Fallback to browser confirm if modal not available
        if (confirm(message)) {
            onConfirm();
        }
        return;
    }

    msgEl.textContent = message;

    // Remove old event listener and add new one
    const newBtn = btnEl.cloneNode(true);
    btnEl.parentNode.replaceChild(newBtn, btnEl);

    newBtn.addEventListener('click', () => {
        bootstrap.Modal.getInstance(modalEl).hide();
        onConfirm();
    });

    new bootstrap.Modal(modalEl).show();
}

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

    if (window.currentParaId) {
        const btn = document.getElementById('merge-paragraph-btn');
        const originalHtml = btn.innerHTML;

        showConfirm("Merge all segments in this paragraph into one?", () => {
            btn.disabled = true;
            btn.innerHTML = "(Merging...)";

            fetch(`/api/paragraph/${window.currentParaId}/merge`, { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                    if (data.status === 'success') {
                        updateUIAfterParagraphMerge(data);
                    } else {
                        alert("No changes or error.");
                    }
                }).catch(err => {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                    console.error("Merge error:", err);
                });
        });
    }
}

// --- Notes Logic ---
function toggleNotes() {
    const container = document.getElementById('notes-container');
    if (container) container.classList.toggle('show');
}

function loadSegment(id) {
    // Unlock previous if exists
    if (currentSegmentId && currentSegmentId !== id) {
        saveSegment(currentSegmentId);
        if (typeof emitUnlockSegment === 'function') {
            emitUnlockSegment(currentSegmentId);
        }
    }

    currentSegmentId = id;

    // Remember last segment position in localStorage
    const projectId = window.GLOSSIO_CONFIG ? window.GLOSSIO_CONFIG.projectId : null;
    if (projectId) {
        localStorage.setItem(`glossio_last_segment_${projectId}`, id);
    }

    document.querySelectorAll('.segment-item').forEach(el => el.classList.remove('active'));
    const item = document.getElementById(`seg-item-${id}`);
    if (item) {
        item.classList.add('active');
        item.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // Lock new segment
    if (typeof emitLockSegment === 'function') {
        emitLockSegment(id);
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

            // Check lock status from API
            if (data.locked_by_user_id && data.locked_by_user_id !== currentUserId) {
                setEditorLocked(true, data.locked_by_name);
            } else {
                setEditorLocked(false);
            }

            // Disable merge button if it's already a full paragraph (only one segment)
            // Disable merge button if it's already a full paragraph (source matches context)
            const mergeBtn = document.getElementById('merge-paragraph-btn');
            if (mergeBtn) {
                // Robust check: Compare length/content of segment source vs paragraph context
                const fullText = (data.paragraph_context || "").trim();
                const segText = (data.source_text || "").trim();

                // If the current segment text matches the full paragraph text, it's already merged/full
                // We use length check as a quick proxy, but full equality is safer
                if (fullText === segText) {
                    mergeBtn.disabled = true;
                    mergeBtn.style.opacity = '0.5';
                    mergeBtn.title = "Already a full paragraph";
                } else {
                    mergeBtn.disabled = false;
                    mergeBtn.style.opacity = '1';
                    mergeBtn.title = "Merge full paragraph";
                }
            }

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
            const linksSpan = document.getElementById('links-info');
            if (linksSpan) linksSpan.innerHTML = "";
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
                const dateStr = date.toLocaleDateString() + ', ' + date.toLocaleTimeString();
                logDiv.innerText = `Last edited by ${data.last_modified_by_name}, ${dateStr}`;
                logDiv.style.display = 'block'; // Ensure it's visible

                // Color logic: Only if shared project (implied if last_modified_by_name is present and different?)
                // User request: "Color does not change solo-working". 
                // Let's assume if last_modified_by_name != current user name, or just always apply color if present?
                // "This only will happen when the project has been shared with someone."
                // We can check if we are in a shared project context, but simple heuristic:
                // If last_modified_by_name is set, use it.

                // const color = getUserColor(data.last_modified_by_name);
                // targetInput.style.color = color;
            } else {
                logDiv.innerText = '';
                // targetInput.style.color = 'inherit';
            }

            // --- AI Suggestion ---
            if (window.GLOSSIO_CONFIG.enableAiFeatures) {
                const aiContainer = document.getElementById('ai-suggestion-container');
                aiContainer.innerHTML = '';
                aiContainer.style.display = 'none';

                if (data.ai_suggestion && (data.ai_suggestion.status === 'pending' || data.ai_suggestion.status === 'edited')) {
                    renderAISuggestion(data.ai_suggestion);
                }
            }
        });
}

function renderAISuggestion(suggestion) {
    const aiContainer = document.getElementById('ai-suggestion-container');
    aiContainer.style.display = 'block';

    // Calculate time nicely
    const timeDisplay = suggestion.translation_time_ms ? `${suggestion.translation_time_ms}ms` : '';

    aiContainer.innerHTML = `
        <div class="ai-suggestion-card">
            <div class="ai-suggestion-badge">AI Suggestion</div>
            <div class="mb-2" style="font-style: italic; color: #495057;">${suggestion.suggested_text}</div>
            <div class="text-muted" style="font-size: 0.75rem;">
                <i data-lucide="clock" style="width:12px;"></i> ${timeDisplay}
            </div>
            <div class="ai-suggestion-actions">
                <button class="btn btn-sm btn-outline-danger" onclick="rejectSuggestion(${suggestion.id})">Reject</button>
                <button class="btn btn-sm btn-outline-primary" onclick="acceptSuggestion(${suggestion.id}, true)">Edit</button>
                <button class="btn btn-sm btn-primary" onclick="acceptSuggestion(${suggestion.id}, false)">Accept</button>
            </div>
        </div>
    `;

    if (window.lucide) lucide.createIcons({ root: aiContainer });
}

function acceptSuggestion(suggestionId, editMode) {
    // If edit mode, just copy to textarea and let user save manually
    // For now we treat 'Edit' as 'Copy to editor'
    // 'Accept' means copy to editor AND mark as accepted in DB

    const suggestionText = document.querySelector('.ai-suggestion-card div[style*="font-style: italic"]').innerText;
    document.getElementById('target-input').value = suggestionText;

    fetch(`/api/segment/${currentSegmentId}/suggestion/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suggestion_id: suggestionId })
    }).then(r => r.json())
        .then(data => {
            saveSegment(currentSegmentId);
            document.getElementById('ai-suggestion-container').style.display = 'none';
            if (!editMode) {
                // If just accept, maybe auto move next?
                // nextSegment(); 
            } else {
                document.getElementById('target-input').focus();
            }
        });
}

function rejectSuggestion(suggestionId) {
    fetch(`/api/segment/${currentSegmentId}/suggestion/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suggestion_id: suggestionId })
    }).then(r => r.json())
        .then(data => {
            document.getElementById('ai-suggestion-container').style.display = 'none';
        });
}

function startBatchTranslation() {
    const projectId = window.GLOSSIO_CONFIG.projectId;

    showConfirm("Start AI translation for all untranslated segments? This happens in the background.", () => {
        fetch(`/api/project/${projectId}/translate-all`, {
            method: 'POST'
        }).then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    // Start polling
                    pollJobStatus();
                } else if (data.status === 'no_work') {
                    alert("Nothing to translate!");
                } else {
                    alert("Error: " + (data.error || data.message));
                }
            }).catch(e => alert("Error starting translation: " + e));
    });
}

function pollJobStatus() {
    if (aiJobPollInterval) clearInterval(aiJobPollInterval);

    const statusDiv = document.getElementById('ai-job-status');
    const bar = document.getElementById('ai-job-bar');
    const count = document.getElementById('ai-job-count');
    const eta = document.getElementById('ai-job-eta');
    const projectId = window.GLOSSIO_CONFIG.projectId;

    statusDiv.style.display = 'block';

    aiJobPollInterval = setInterval(() => {
        fetch(`/api/project/${projectId}/translation-job`)
            .then(r => r.json())
            .then(job => {
                if (job.status === 'none' || job.status === 'completed' || job.status === 'failed') {
                    clearInterval(aiJobPollInterval);
                    if (job.status === 'completed') {
                        bar.style.width = '100%';
                        bar.className = 'progress-bar bg-success';
                        eta.innerText = 'Done!';
                        setTimeout(() => { statusDiv.style.display = 'none'; }, 3000);
                        // Reload current segment to see changes if any
                        loadSegment(currentSegmentId);
                        updateProgress();
                    } else if (job.status === 'failed') {
                        bar.className = 'progress-bar bg-danger';
                        eta.innerText = 'Failed';
                        alert("Translation job failed: " + job.error);
                    }
                    return;
                }

                // Running
                const pct = Math.round(job.progress);
                bar.style.width = `${pct}%`;
                count.innerText = `${job.completed}/${job.total} segments`;

                if (job.remaining_seconds) {
                    const min = Math.floor(job.remaining_seconds / 60);
                    const sec = Math.floor(job.remaining_seconds % 60);
                    eta.innerText = `~${min}m ${sec}s left`;
                } else {
                    eta.innerText = 'Calculating...';
                }
            });
    }, 2000); // Check every 2s
}

// Check for running jobs on load
document.addEventListener('DOMContentLoaded', () => {
    // existing Init code...
    if (window.GLOSSIO_CONFIG.enableAiFeatures) {
        fetch(`/api/project/${window.GLOSSIO_CONFIG.projectId}/translation-job`)
            .then(r => r.json())
            .then(job => {
                if (job.status === 'running' || job.status === 'pending') {
                    pollJobStatus();
                }
            });
    }
});

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

    // Typing indicator & Real-time Sync
    let typingTimeout;
    targetInput.addEventListener('input', () => {
        // Emit typing indicator
        if (typeof emitTyping === 'function') {
            emitTyping(currentSegmentId);
        }

        // Emit real-time update (Debounced)
        if (typingTimeout) clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
            if (typeof emitSegmentUpdate === 'function') {
                const target = document.getElementById('target-input').value;
                const note = document.getElementById('note-input').value;
                emitSegmentUpdate(currentSegmentId, target, note);
            }
        }, 300); // 300ms debounce
    });
}

function nextSegment() {
    const idx = segments.indexOf(currentSegmentId);
    if (idx >= 0 && idx < segments.length - 1) {
        loadSegment(segments[idx + 1]);
    } else {
        // Fallback: Try to find next ID from DOM if segments array is out of sync
        const currentEl = document.getElementById(`seg-item-${currentSegmentId}`);
        if (currentEl && currentEl.nextElementSibling) {
            const nextId = currentEl.nextElementSibling.id.replace('seg-item-', '');
            if (nextId) loadSegment(parseInt(nextId));
        }
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
    showConfirm("Merge with previous segment?", () => {
        fetch(`/api/segment/${currentSegmentId}/merge_prev`, {
            method: 'POST'
        }).then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    updateUIAfterSegmentMerge(data);
                } else {
                    alert(data.message);
                }
            });
    });
}

// Helper function to update UI after segment merge
function updateUIAfterSegmentMerge(data) {
    const mergedSeg = data.merged_segment;
    const deletedId = data.deleted_segment_id;

    // Remove deleted segment from DOM
    const deletedItem = document.getElementById(`seg-item-${deletedId}`);
    if (deletedItem) {
        deletedItem.remove();
    }

    // Update segments array
    const deletedIdx = segments.indexOf(deletedId);
    if (deletedIdx > -1) {
        segments.splice(deletedIdx, 1);
    }

    // Update merged segment display in sidebar
    const mergedItem = document.getElementById(`seg-item-${mergedSeg.id}`);
    if (mergedItem) {
        // Update the preview text
        const previewText = mergedSeg.source_text.length > 50
            ? mergedSeg.source_text.substring(0, 50) + "..."
            : mergedSeg.source_text;
        mergedItem.innerHTML = `<b>${mergedSeg.p_idx + 1}.${mergedSeg.s_idx + 1}</b>: ${previewText}`;

        // Update translated/note classes
        if (mergedSeg.target_text && mergedSeg.target_text.trim()) {
            mergedItem.classList.add('translated');
        }
        if (mergedSeg.note && mergedSeg.note.trim()) {
            mergedItem.classList.add('has-note');
        }
    }

    // Load the merged segment
    loadSegment(mergedSeg.id);

    // Update progress
    updateProgress();

    // Broadcast merge event to other users via WebSocket
    if (typeof emitSegmentMerged === 'function') {
        emitSegmentMerged(data.project_id, deletedId, mergedSeg.id);
    }
}

// Helper function to update UI after paragraph merge
function updateUIAfterParagraphMerge(data) {
    const mergedSeg = data.merged_segment;
    const deletedIds = data.deleted_segment_ids;

    // Remove all deleted segments from DOM
    deletedIds.forEach(id => {
        const item = document.getElementById(`seg-item-${id}`);
        if (item) {
            item.remove();
        }

        // Remove from segments array
        const idx = segments.indexOf(id);
        if (idx > -1) {
            segments.splice(idx, 1);
        }
    });

    // Update merged segment display in sidebar
    const mergedItem = document.getElementById(`seg-item-${mergedSeg.id}`);
    if (mergedItem) {
        // Update the preview text
        const previewText = mergedSeg.source_text.length > 50
            ? mergedSeg.source_text.substring(0, 50) + "..."
            : mergedSeg.source_text;
        mergedItem.innerHTML = `<b>${mergedSeg.p_idx + 1}.${mergedSeg.s_idx + 1}</b>: ${previewText}`;

        // Update translated/note classes
        if (mergedSeg.target_text && mergedSeg.target_text.trim()) {
            mergedItem.classList.add('translated');
        }
        if (mergedSeg.note && mergedSeg.note.trim()) {
            mergedItem.classList.add('has-note');
        }
    }

    // Update total segments count
    totalSegments = segments.length;

    // Load the merged segment
    loadSegment(mergedSeg.id);

    // Update progress
    updateProgress();

    // Broadcast merge event to other users via WebSocket
    if (typeof emitParagraphMerged === 'function') {
        emitParagraphMerged(data.project_id, deletedIds, mergedSeg.id);
    }
}


// Keyboard Shortcuts
document.addEventListener('keydown', function (e) {
    if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); nextSegment(); }
    if (e.ctrlKey && e.key === 'ArrowDown') { e.preventDefault(); nextSegment(); }
    if (e.ctrlKey && e.key === 'ArrowUp') { e.preventDefault(); prevSegment(); }
    if (e.ctrlKey && (e.key === 'b' || e.key === 'B')) { e.preventDefault(); prevSegment(); } // Added Ctrl+B
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
                // Prioritize Reina-Valera 1960 if available (User Request v1.1.6)
                let rvrIndex = -1;
                for (let i = 0; i < select.options.length; i++) {
                    // Check short name (value) or text
                    const val = select.options[i].value.toUpperCase();
                    const txt = select.options[i].text.toUpperCase();
                    if (val === 'RVR1960' || val === 'RVR60' || txt.includes('REINA-VALERA 1960')) {
                        rvrIndex = i;
                        break;
                    }
                }

                if (rvrIndex >= 0) {
                    select.selectedIndex = rvrIndex;
                } else {
                    // Fallback to Language Map
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
            // Parse verse input: "1" or "2-5" or "7, 12" or "7-12, 15"
            if (verseInput) {
                const validVerses = new Set();
                const parts = verseInput.split(',');

                parts.forEach(part => {
                    part = part.trim();
                    if (part.includes('-')) {
                        const rangeParts = part.split('-');
                        const start = parseInt(rangeParts[0]);
                        const end = parseInt(rangeParts[1]);
                        if (!isNaN(start) && !isNaN(end)) {
                            for (let i = start; i <= end; i++) {
                                validVerses.add(i);
                            }
                        }
                    } else {
                        const vNum = parseInt(part);
                        if (!isNaN(vNum)) {
                            validVerses.add(vNum);
                        }
                    }
                });

                if (validVerses.size > 0) {
                    filtered = data.filter(v => validVerses.has(v.verse));
                } else {
                    filtered = data; // Fallback to all if parsing failed
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
    const bibleArea = document.getElementById('bible-content-area');
    const text = bibleArea.innerText;
    if (text && !text.startsWith("Loading") && !text.startsWith("Error")) {
        const target = document.getElementById('target-input');

        // Append reference if possible
        const version = document.getElementById('bible-version-select').value;
        const bookSelect = document.getElementById('bible-book-select');
        const bookName = bookSelect.options[bookSelect.selectedIndex].text;
        const chapter = document.getElementById('bible-chapter-input').value;
        const verse = document.getElementById('bible-verse-input').value;

        const reference = ` (${version} ${bookName} ${chapter}:${verse})`;
        const textToPaste = text + reference;

        if (target.value && target.value.trim().length > 0) {
            target.value = target.value.trim() + "\n" + textToPaste;
        } else {
            target.value = textToPaste;
        }

        saveSegment(currentSegmentId);
    }
}

// Initial load check: URL param > localStorage > first segment
// Wrap in a small delay to ensure segments array from GLOSSIO_CONFIG is populated
// and the environment is stable before loading the first/saved segment.
setTimeout(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const startSeg = urlParams.get('segment');
    const projectId = window.GLOSSIO_CONFIG ? window.GLOSSIO_CONFIG.projectId : null;
    const savedSegment = projectId ? localStorage.getItem(`glossio_last_segment_${projectId}`) : null;

    console.log('[Init] Project ID:', projectId);
    console.log('[Init] Saved Segment:', savedSegment);
    console.log('[Init] URL Segment:', startSeg);

    if (startSeg) {
        loadSegment(startSeg);
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (savedSegment && segments.includes(parseInt(savedSegment))) {
        // Restore last position from localStorage
        loadSegment(parseInt(savedSegment));
        console.log('[Init] Restored to last segment:', savedSegment);
    } else {
        // Requires segments to be loaded in GLOSSIO_CONFIG
        if (segments.length > 0) {
            loadSegment(segments[0]);
        }
    }
    updateProgress();
}, 200); // 200ms buffer for stability


// --- Feature: Quick Translate (v1.1.6) ---
document.addEventListener('DOMContentLoaded', () => {
    const sourceDisplay = document.getElementById('source-display');
    if (!sourceDisplay) return;

    // Create tooltip button
    const tooltipBtn = document.createElement('button');
    tooltipBtn.id = 'quick-translate-btn';
    tooltipBtn.className = 'btn btn-sm btn-primary position-absolute shadow-sm';
    tooltipBtn.style.display = 'none';
    tooltipBtn.style.zIndex = '1000';
    tooltipBtn.style.borderRadius = '20px';
    tooltipBtn.style.padding = '2px 8px';
    tooltipBtn.innerHTML = '<i data-lucide="globe" style="width:16px;height:16px;"></i>';
    tooltipBtn.title = 'Translate Selection';
    document.body.appendChild(tooltipBtn);

    // Show tooltip on selection
    sourceDisplay.addEventListener('mouseup', (e) => {
        setTimeout(() => {
            const selection = window.getSelection();
            const text = selection.toString().trim();

            if (text.length > 0 && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                // Check if selection is inside source display
                if (!sourceDisplay.contains(range.commonAncestorContainer)) return;

                const rect = range.getBoundingClientRect();

                tooltipBtn.style.top = `${rect.bottom + window.scrollY + 5}px`;
                tooltipBtn.style.left = `${rect.left + window.scrollX + (rect.width / 2) - 15}px`;
                tooltipBtn.style.display = 'block';

                // Re-render icon
                if (window.lucide) lucide.createIcons({ root: tooltipBtn });

                // Clear previous listener to avoid multiples
                tooltipBtn.onclick = null;
                tooltipBtn.onclick = (evt) => {
                    evt.stopPropagation();
                    evt.preventDefault();
                    quickTranslate(text, tooltipBtn);
                };
            } else {
                tooltipBtn.style.display = 'none';
            }
        }, 10);
    });

    // Hide on outside click
    document.addEventListener('mousedown', (e) => {
        if (e.target !== tooltipBtn && !tooltipBtn.contains(e.target)) {
            tooltipBtn.style.display = 'none';
        }
    });
});

function quickTranslate(text, btn) {
    // Get Key from LocalStorage
    const apiKey = localStorage.getItem('glossio_deepl_key');
    if (!apiKey) {
        alert("Please configure your DeepL API Key in Settings first.");
        return;
    }

    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

    // Check overridden lang
    const overrideLang = localStorage.getItem('glossio_target_lang');
    const finalLang = overrideLang || targetLangCode;

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
            if (data.translation) {
                // Append translation to target input
                const targetInput = document.getElementById('target-input');
                const sep = (targetInput.value && !targetInput.value.endsWith(' ')) ? ' ' : '';
                targetInput.value += sep + data.translation;

                // Trigger save/sync
                saveSegment(currentSegmentId);

                // Hide button
                btn.style.display = 'none';

                // Deselect
                window.getSelection().removeAllRanges();
            } else {
                alert("MT Error: " + (data.error || "Unknown"));
            }
        }).catch(err => {
            alert("Translation failed: " + err);
        }).finally(() => {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            if (window.lucide) lucide.createIcons({ root: btn });
        });
}
