// socket_client.js

let socket;
let activeUsers = {};

// Shared color generator
window.getUserColor = function (name) {
    if (!name) return '#000000';
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + "00000".substring(0, 6 - c.length) + c;
};

function initSocket(projectId) {
    socket = io();

    socket.on('connect', () => {
        console.log('Connected to socket server');
        socket.emit('join', { project_id: projectId });
    });

    socket.on('user_joined', (data) => {
        console.log('User joined:', data);
        activeUsers[data.user_id] = data;
        updateActiveUsersUI();
        showToast(`${data.name} joined`);
    });

    socket.on('current_users', (users) => {
        console.log('Current users:', users);
        users.forEach(u => {
            activeUsers[u.user_id] = u;
        });
        updateActiveUsersUI();
    });

    socket.on('user_left', (data) => {
        console.log('User left:', data);
        delete activeUsers[data.user_id];
        updateActiveUsersUI();
    });

    socket.on('segment_locked', (data) => {
        console.log('Segment locked:', data);
        // Update Log
        const logDiv = document.getElementById('last-modified-log');
        if (logDiv && data.last_modified_by_name) {
            const date = new Date(data.last_modified_at);
            const dateStr = date.toLocaleDateString() + ', ' + date.toLocaleTimeString();
            logDiv.innerText = `Last edited by ${data.last_modified_by_name}, ${dateStr}`;
            logDiv.style.display = 'block';
        }
        // Update UI
        const segItem = document.getElementById(`seg-item-${data.segment_id}`);
        if (segItem) {
            segItem.classList.add('locked');
            // Add badge if not present? Or just rely on activeUsersUI?
            // The requirement says: "Therefore the badge is also visible on the segment area, next to the segment."
            // We can add a data attribute or update the UI helper
            segItem.setAttribute('data-locked-by', data.user_name);
            updateSegmentLockUI(data.segment_id, data.user_name);
        }

        // If current segment, disable inputs
        if (window.currentSegmentId === data.segment_id) {
            setEditorLocked(true, data.user_name);
        }

        // Update user's current segment in activeUsers
        if (activeUsers[data.user_id]) {
            activeUsers[data.user_id].current_segment_id = data.segment_id;
            updateActiveUsersUI();
        }
    });

    socket.on('segment_unlocked', (data) => {
        console.log('Segment unlocked:', data);
        const segItem = document.getElementById(`seg-item-${data.segment_id}`);
        if (segItem) {
            segItem.classList.remove('locked');
            segItem.removeAttribute('data-locked-by');
            updateSegmentLockUI(data.segment_id, null);
        }

        if (window.currentSegmentId === data.segment_id) {
            setEditorLocked(false);
        }

        // Clear user's current segment? We don't know who unlocked it easily here without more data,
        // but we can iterate activeUsers to find who had it.
        // Or just wait for next lock.
        // For now, let's clear it if we find it.
        Object.values(activeUsers).forEach(u => {
            if (u.current_segment_id === data.segment_id) {
                u.current_segment_id = null;
            }
        });
        updateActiveUsersUI();
    });

    // Heartbeat
    setInterval(() => {
        if (socket && socket.connected) {
            socket.emit('heartbeat', { project_id: window.GLOSSIO_CONFIG.projectId });
        }
    }, 60000); // 1 min
}

function updateSegmentLockUI(segmentId, lockedByName) {
    const segItem = document.getElementById(`seg-item-${segmentId}`);
    if (!segItem) return;

    // Remove existing lock badge if any
    const existingBadge = segItem.querySelector('.lock-badge');
    if (existingBadge) existingBadge.remove();

    if (lockedByName) {
        const badge = document.createElement('span');
        badge.className = 'lock-badge badge rounded-pill ms-2';
        badge.style.fontSize = '0.6em';
        badge.style.backgroundColor = window.getUserColor(lockedByName);
        badge.innerText = lockedByName.charAt(0).toUpperCase();
        badge.title = `Locked by ${lockedByName}`;
        segItem.appendChild(badge);
    }
}

function setEditorLocked(locked, lockedByName) {
    const targetInput = document.getElementById('target-input');
    const noteInput = document.getElementById('note-input');
    const sourceDisplay = document.getElementById('source-display');

    if (locked) {
        if (targetInput) {
            targetInput.disabled = true;
            targetInput.placeholder = `${lockedByName} is working...`;
        }
        if (noteInput) noteInput.disabled = true;
        if (sourceDisplay) sourceDisplay.classList.add('locked-overlay');
    } else {
        if (targetInput) {
            targetInput.disabled = false;
            targetInput.placeholder = "Type translation here...";
        }
        if (noteInput) noteInput.disabled = false;
        if (sourceDisplay) sourceDisplay.classList.remove('locked-overlay');
    }
}

function updateActiveUsersUI() {
    const container = document.getElementById('active-users-container');
    if (!container) return;

    // Toggle container visibility: Hide if only 1 user (self) or 0
    // User request: "badges dissapear (all)" when collaborator closes tab
    if (Object.keys(activeUsers).length > 1) {
        container.style.display = 'flex';
        const collabBadge = document.getElementById('collab-badge');
        if (collabBadge) collabBadge.style.display = 'inline-block';
    } else {
        container.style.display = 'none';
        const collabBadge = document.getElementById('collab-badge');
        if (collabBadge) collabBadge.style.display = 'none';
    }

    container.innerHTML = '';
    Object.values(activeUsers).forEach(user => {
        const wrapper = document.createElement('div');
        wrapper.className = 'user-badge-wrapper';
        wrapper.style.cursor = 'pointer';
        wrapper.onclick = () => {
            if (user.current_segment_id) {
                if (typeof loadSegment === 'function') {
                    loadSegment(user.current_segment_id);
                }
            } else {
                showToast(`${user.name} is not working on a segment.`);
            }
        };

        const badge = document.createElement('span');
        badge.title = user.email + (user.current_segment_id ? " (Click to jump)" : "");
        badge.innerText = user.name.charAt(0).toUpperCase();

        // Color
        const color = window.getUserColor(user.name);
        badge.className = 'badge rounded-pill text-white';
        badge.style.backgroundColor = color;

        const dots = document.createElement('span');
        dots.id = `typing-dots-${user.user_id}`;
        dots.className = 'typing-dots';
        dots.innerText = ''; // Hidden by default

        wrapper.appendChild(badge);
        wrapper.appendChild(dots);
        container.appendChild(wrapper);
    });
}

function emitSegmentUpdate(segmentId, targetText, note) {
    if (socket) {
        socket.emit('update_segment', {
            project_id: window.GLOSSIO_CONFIG.projectId,
            segment_id: segmentId,
            target_text: targetText,
            note: note
        });
    }
}

function emitTyping(segmentId) {
    if (socket) {
        socket.emit('typing', {
            project_id: window.GLOSSIO_CONFIG.projectId,
            segment_id: segmentId
        });
    }
}

function emitLockSegment(segmentId) {
    if (socket) {
        socket.emit('lock_segment', {
            project_id: window.GLOSSIO_CONFIG.projectId,
            segment_id: segmentId
        });
    }
}

function emitUnlockSegment(segmentId) {
    if (socket) {
        socket.emit('unlock_segment', {
            project_id: window.GLOSSIO_CONFIG.projectId,
            segment_id: segmentId
        });
    }
}

function showToast(message) {
    // Simple toast implementation
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) return;

    const toast = document.createElement('div');
    toast.className = 'toast show align-items-center text-white bg-primary border-0 mb-2';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
