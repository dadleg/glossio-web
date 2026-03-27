const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
    // File dialogs
    openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
    saveFileDialog: (defaultName) => ipcRenderer.invoke('save-file-dialog', defaultName),

    // Auto-update
    checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
    installUpdate: () => ipcRenderer.invoke('install-update'),

    // Update event listeners
    onUpdateAvailable: (callback) => ipcRenderer.on('update-available', (_, info) => callback(info)),
    onUpdateProgress: (callback) => ipcRenderer.on('update-progress', (_, progress) => callback(progress)),
    onUpdateDownloaded: (callback) => ipcRenderer.on('update-downloaded', (_, info) => callback(info)),

    // Window controls
    controlWindow: (action) => ipcRenderer.send('window-control', action),

    // Platform info
    platform: process.platform,

    // Check if running in Electron
    isElectron: true
});

// Log for debugging
console.log('Preload script loaded - Electron APIs exposed with auto-update support');
