// firestore-editor-bridge.js
// Bridges Firestore real-time sync with existing editor.js functions

import {
    initFirestore,
    subscribeToProject,
    lockSegment,
    unlockSegment,
    updateSegmentText,
    setPresence,
    updateCurrentSegment,
    cleanup,
    getCurrentUserId
} from './firestore-sync.js';

let currentProjectId = null;
let unsubscribe = null;

// Initialize Firestore sync and expose to global scope
window.initFirestoreSync = async function (config) {
    console.log('Initializing Firestore sync...');

    // Initialize Firebase
    initFirestore(config.firebase);

    currentProjectId = config.projectId;

    // Set initial presence
    await setPresence(currentProjectId, true);

    // Subscribe to real-time updates
    unsubscribe = subscribeToProject(currentProjectId, {
        onSegmentChange: handleSegmentChange,
        onPresenceChange: handlePresenceChange,
        onError: (error) => console.error('Firestore error:', error)
    });

    // Override editor.js save function to use Firestore
    overrideEditorFunctions();

    // Handle page unload
    window.addEventListener('beforeunload', async () => {
        await setPresence(currentProjectId, false);
        if (unsubscribe) unsubscribe();
        cleanup();
    });

    console.log('Firestore sync initialized!');
};

// Handle segment changes from Firestore
function handleSegmentChange(changeType, segmentData) {
    const segmentId = segmentData.id;
    console.log('Segment change:', changeType, segmentId, segmentData);

    const segItem = document.getElementById(`seg-item-${segmentId}`);
    if (!segItem) return;

    switch (changeType) {
        case 'modified':
            // Update sidebar item styling
            if (segmentData.target_text) {
                segItem.classList.add('translated');
            } else {
                segItem.classList.remove('translated');
            }

            if (segmentData.note) {
                segItem.classList.add('has-note');
            } else {
                segItem.classList.remove('has-note');
            }

            // Handle locking
            if (segmentData.locked_by && segmentData.locked_by !== getCurrentUserId()) {
                segItem.classList.add('locked');
                segItem.setAttribute('data-locked-by', segmentData.locked_by_name || 'Another user');

                // If this is the current segment, lock the editor
                if (window.currentSegmentId == segmentId) {
                    setEditorLockedState(true, segmentData.locked_by_name);
                }
            } else {
                segItem.classList.remove('locked');
                segItem.removeAttribute('data-locked-by');

                if (window.currentSegmentId == segmentId) {
                    setEditorLockedState(false);
                }
            }

            // If this is the current segment and someone else updated it
            if (window.currentSegmentId == segmentId && segmentData.last_modified_by !== getCurrentUserId()) {
                // Update target text if we don't have focus
                const targetInput = document.getElementById('target-input');
                if (targetInput && document.activeElement !== targetInput) {
                    targetInput.value = segmentData.target_text || '';
                }

                // Update note
                const noteInput = document.getElementById('note-input');
                if (noteInput && document.activeElement !== noteInput) {
                    noteInput.value = segmentData.note || '';
                }

                // Update last modified display
                if (segmentData.last_modified_by_name) {
                    const logDiv = document.getElementById('last-modified-log');
                    if (logDiv) {
                        const date = segmentData.last_modified_at?.toDate?.() || new Date();
                        logDiv.innerText = `Last edited by ${segmentData.last_modified_by_name}, ${date.toLocaleString()}`;
                    }
                }
            }
            break;

        case 'removed':
            // Segment was deleted (e.g., from merge)
            segItem.remove();
            break;
    }
}

// Handle presence changes
function handlePresenceChange(users) {
    console.log('Presence update:', users);

    // Update active users UI
    const container = document.getElementById('active-users-container');
    if (!container) return;

    // Filter out current user
    const otherUsers = users.filter(u => u.id !== getCurrentUserId());

    if (otherUsers.length === 0) {
        container.innerHTML = '';
        document.getElementById('collab-badge')?.style.setProperty('display', 'none');
        return;
    }

    // Show collab badge
    document.getElementById('collab-badge')?.style.setProperty('display', 'inline-block');

    // Build avatar HTML
    container.innerHTML = otherUsers.map(user => {
        const color = window.getUserColor ? window.getUserColor(user.name) : '#666';
        const initial = (user.name || '?')[0].toUpperCase();
        return `
            <div class="user-badge-wrapper">
                <span class="badge rounded-pill" style="background-color: ${color}; color: white;" 
                      title="${user.name || user.email}">
                    ${initial}
                </span>
            </div>
        `;
    }).join('');
}

// Set editor locked state
function setEditorLockedState(locked, lockedByName) {
    const targetInput = document.getElementById('target-input');
    const noteInput = document.getElementById('note-input');

    if (locked) {
        if (targetInput) {
            targetInput.disabled = true;
            targetInput.placeholder = `Locked by ${lockedByName}`;
        }
        if (noteInput) noteInput.disabled = true;
    } else {
        if (targetInput) {
            targetInput.disabled = false;
            targetInput.placeholder = 'Type translation here...';
        }
        if (noteInput) noteInput.disabled = false;
    }
}

// Override editor.js functions to use Firestore
function overrideEditorFunctions() {
    // Store original loadSegment
    const originalLoadSegment = window.loadSegment;

    // Override loadSegment to handle locking
    window.loadSegment = async function (segmentId) {
        // Unlock previous segment
        if (window.currentSegmentId && window.currentSegmentId !== segmentId) {
            try {
                await unlockSegment(currentProjectId, window.currentSegmentId);
            } catch (e) {
                console.error('Failed to unlock:', e);
            }
        }

        // Call original
        if (originalLoadSegment) {
            originalLoadSegment(segmentId);
        }

        // Lock new segment
        try {
            await lockSegment(currentProjectId, segmentId);
            await updateCurrentSegment(currentProjectId, segmentId);
        } catch (e) {
            console.error('Failed to lock segment:', e);
            if (e.message.includes('locked')) {
                window.showToast?.(`Segment is ${e.message}`);
            }
        }
    };

    // Override saveSegment to use Firestore
    const originalSaveSegment = window.saveSegment;

    window.saveSegmentToFirestore = async function () {
        const segmentId = window.currentSegmentId;
        if (!segmentId) return;

        const targetInput = document.getElementById('target-input');
        const noteInput = document.getElementById('note-input');

        if (!targetInput) return;

        const targetText = targetInput.value;
        const note = noteInput?.value || '';

        try {
            await updateSegmentText(currentProjectId, segmentId, targetText, note);

            // Update UI
            const segItem = document.getElementById(`seg-item-${segmentId}`);
            if (segItem && targetText) {
                segItem.classList.add('translated');
            }

            // Show saved indicator
            const indicator = document.getElementById('status-indicator');
            if (indicator) {
                indicator.innerText = 'Saved';
                indicator.classList.remove('bg-warning');
                indicator.classList.add('bg-light');
            }
        } catch (e) {
            console.error('Failed to save to Firestore:', e);
            // Fallback to Flask save
            if (originalSaveSegment) {
                originalSaveSegment();
            }
        }
    };

    // Add debounced auto-save on input
    let saveTimeout = null;
    const targetInput = document.getElementById('target-input');
    const noteInput = document.getElementById('note-input');

    const debouncedSave = () => {
        if (saveTimeout) clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            window.saveSegmentToFirestore?.();
        }, 1000); // Auto-save after 1 second of no typing

        // Show unsaved indicator
        const indicator = document.getElementById('status-indicator');
        if (indicator) {
            indicator.innerText = 'Saving...';
            indicator.classList.add('bg-warning');
        }
    };

    if (targetInput) {
        targetInput.addEventListener('input', debouncedSave);
    }
    if (noteInput) {
        noteInput.addEventListener('input', debouncedSave);
    }

    console.log('Editor functions overridden for Firestore');
}

// Expose functions globally
window.firestoreSync = {
    lockSegment: (segId) => lockSegment(currentProjectId, segId),
    unlockSegment: (segId) => unlockSegment(currentProjectId, segId),
    saveSegment: () => window.saveSegmentToFirestore?.(),
    setPresence: (online) => setPresence(currentProjectId, online)
};
