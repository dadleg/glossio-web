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

    socket.on('segment_updated', (data) => {
        console.log('Segment updated:', data);
        // Update the UI for the segment
        const segItem = document.getElementById(`seg-item-${data.segment_id}`);
        if (segItem) {
            // Update preview text if needed, or mark as translated
            if (data.target_text) {
                segItem.classList.add('translated');
            }
        }

        // If this segment is currently open in the editor, update the inputs
        // Real-time override: Last write wins, so we always update
        if (window.currentSegmentId === data.segment_id) {
            const targetInput = document.getElementById('target-input');
            const noteInput = document.getElementById('note-input');

            if (targetInput) {
                targetInput.value = data.target_text;

                // Update color
                if (data.last_modified_by_name) {
                    targetInput.style.color = getUserColor(data.last_modified_by_name);
                }
            }
            if (noteInput) noteInput.value = data.note;

            // Update Log
            const logDiv = document.getElementById('last-modified-log');
            if (logDiv && data.last_modified_by_name) {
                const date = new Date(data.last_modified_at);
                const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                logDiv.innerText = `Last edited by ${data.last_modified_by_name} on ${dateStr}`;
            }
        }

        // Update note indicator in sidebar
        if (segItem) {
            if (data.note && data.note.trim().length > 0) {
                segItem.classList.add('has-note');
            } else {
                segItem.classList.remove('has-note');
            }
        }
    });

    socket.on('user_typing', (data) => {
        // Show typing indicator for specific user
        const dots = document.getElementById(`typing-dots-${data.user_id}`);
        if (dots) {
            dots.classList.add('active');
            dots.innerText = '...';

            // Clear existing timeout if any
            if (dots.timeout) clearTimeout(dots.timeout);

            dots.timeout = setTimeout(() => {
                dots.classList.remove('active');
                dots.innerText = '';
            }, 2000);
        }
    });
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

        const badge = document.createElement('span');
        badge.title = user.email;
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
