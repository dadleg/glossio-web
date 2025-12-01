lucide.createIcons();

// Settings Logic
const apiKeyInput = document.getElementById('deepl-api-key-input');

function loadSettings() {
    const key = localStorage.getItem('glossio_deepl_key');
    if(key && apiKeyInput) apiKeyInput.value = key;
    
    // Theme
    const theme = localStorage.getItem('glossio_theme') || 'light';
    document.body.setAttribute('data-bs-theme', theme);
    const themeToggle = document.getElementById('theme-toggle');
    if(themeToggle) themeToggle.checked = (theme === 'dark');
}

function saveSettings() {
    const key = apiKeyInput.value.trim();
    if(key) {
        localStorage.setItem('glossio_deepl_key', key);
    } else {
        localStorage.removeItem('glossio_deepl_key');
    }
    alert("Settings saved!");
    const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
    modal.hide();
}

function toggleTheme() {
    const isDark = document.getElementById('theme-toggle').checked;
    const theme = isDark ? 'dark' : 'light';
    document.body.setAttribute('data-bs-theme', theme);
    localStorage.setItem('glossio_theme', theme);
}

function uploadResource(type) {
    const form = document.getElementById(`form-${type}`);
    const formData = new FormData(form);
    
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            alert(data.message);
        } else {
            alert("Error: " + data.message);
        }
    })
    .catch(e => alert("Upload failed: " + e));
}

// Load on start
document.addEventListener('DOMContentLoaded', loadSettings);
