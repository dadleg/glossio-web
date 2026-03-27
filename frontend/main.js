const { app, BrowserWindow, ipcMain, dialog, Notification } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const { autoUpdater } = require('electron-updater');

let mainWindow;
let backendProcess = null;
const BACKEND_PORT = 5000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;

// ==========================================
// AUTO-UPDATE CONFIGURATION
// ==========================================

// Configure auto-updater
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = true;

function setupAutoUpdater() {
    // Check for updates silently
    if (app.isPackaged) {
        autoUpdater.checkForUpdatesAndNotify();

        // Check for updates every hour
        setInterval(() => {
            autoUpdater.checkForUpdatesAndNotify();
        }, 60 * 60 * 1000);
    }

    autoUpdater.on('checking-for-update', () => {
        console.log('Checking for updates...');
    });

    autoUpdater.on('update-available', (info) => {
        console.log('Update available:', info.version);
        if (mainWindow) {
            mainWindow.webContents.send('update-available', info);
        }
    });

    autoUpdater.on('update-not-available', () => {
        console.log('No updates available');
    });

    autoUpdater.on('download-progress', (progress) => {
        console.log(`Download progress: ${Math.round(progress.percent)}%`);
        if (mainWindow) {
            mainWindow.webContents.send('update-progress', progress);
        }
    });

    autoUpdater.on('update-downloaded', (info) => {
        console.log('Update downloaded:', info.version);

        // Show notification to user
        const notification = new Notification({
            title: 'Update Ready',
            body: `Glossio ${info.version} is ready to install. Restart to update.`
        });
        notification.show();

        // Also notify renderer
        if (mainWindow) {
            mainWindow.webContents.send('update-downloaded', info);
        }
    });

    autoUpdater.on('error', (error) => {
        console.error('Auto-updater error:', error);
    });
}

// IPC handler to restart and install update
ipcMain.handle('install-update', () => {
    autoUpdater.quitAndInstall(false, true);
});

ipcMain.handle('check-for-updates', async () => {
    try {
        const result = await autoUpdater.checkForUpdates();
        return result?.updateInfo || null;
    } catch (e) {
        return null;
    }
});

// Check if backend is running
function checkBackendHealth() {
    return new Promise((resolve) => {
        http.get(`${BACKEND_URL}/health`, (res) => {
            resolve(res.statusCode === 200);
        }).on('error', () => {
            resolve(false);
        });
    });
}

// Wait for backend to be ready
// Wait for backend to be ready (60 seconds max = 120 attempts x 500ms)
async function waitForBackend(maxAttempts = 120) {
    for (let i = 0; i < maxAttempts; i++) {
        const isHealthy = await checkBackendHealth();
        if (isHealthy) {
            console.log('Backend is ready!');
            return true;
        }
        // Check if process crashed
        if (backendProcess === null) {
            console.error('Backend process crashed before becoming ready');
            return false;
        }
        await new Promise(resolve => setTimeout(resolve, 500));
        if (i % 10 === 0) {
            console.log(`Waiting for backend... (${i * 500 / 1000}s)`);
        }
    }
    console.error('Backend failed to start (timeout)');
    return false;
}

// Start the Python backend
function startBackend() {
    const isDev = !app.isPackaged;

    // Check if LOCAL_MODE is requested (can be set via environment or config file)
    const localMode = process.env.LOCAL_MODE || 'true';  // Default to local mode for offline-first experience

    let backendPath;
    if (isDev) {
        // Development: Run Python directly
        backendPath = path.join(__dirname, '..', '.venv', 'bin', 'python');
        const runScript = path.join(__dirname, '..', 'run.py');

        console.log('Starting backend in dev mode:', backendPath, runScript);
        console.log('LOCAL_MODE:', localMode);
        backendProcess = spawn(backendPath, [runScript], {
            cwd: path.join(__dirname, '..'),
            env: { ...process.env, FLASK_ENV: 'development', LOCAL_MODE: localMode }
        });
    } else {
        // Production: Run PyInstaller executable
        const executableName = process.platform === 'win32' ? 'glossio-backend.exe' : 'glossio-backend';
        backendPath = path.join(process.resourcesPath, 'backend', executableName);

        console.log('Starting backend in production mode:', backendPath);
        console.log('LOCAL_MODE:', localMode);

        // Check if the executable exists
        const fs = require('fs');
        if (!fs.existsSync(backendPath)) {
            console.error('Backend executable not found at:', backendPath);
            return false;
        }

        try {
            backendProcess = spawn(backendPath, [], {
                cwd: path.dirname(backendPath),
                env: { ...process.env, LOCAL_MODE: localMode }
            });
        } catch (err) {
            console.error('Failed to spawn backend:', err);
            return false;
        }
    }

    backendProcess.stdout.on('data', (data) => {
        console.log(`Backend: ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`Backend Error: ${data}`);
    });

    backendProcess.on('error', (err) => {
        console.error('Backend spawn error:', err);
        backendProcess = null;
    });

    backendProcess.on('close', (code) => {
        console.log(`Backend process exited with code ${code}`);
        backendProcess = null;
    });

    return true;
}

// Stop the backend
function stopBackend() {
    if (backendProcess) {
        console.log('Stopping backend...');
        backendProcess.kill();
        backendProcess = null;
    }
}

// Create the main window
async function createWindow() {
    // Start backend first
    startBackend();

    // Wait for backend to be ready
    const backendReady = await waitForBackend();

    if (!backendReady) {
        dialog.showErrorBox('Error', 'Failed to start the application backend. Please try again.');
        app.quit();
        return;
    }

    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        frame: false, // Frameless window
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        icon: path.join(__dirname, 'icons', 'icon.png'),
        title: 'Glossio - Translation Assistant'
    });

    // Remove the default menu
    mainWindow.setMenu(null);

    // Load the Flask app
    mainWindow.loadURL(BACKEND_URL);

    // Open DevTools in development
    if (!app.isPackaged) {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// App lifecycle
app.whenReady().then(() => {
    createWindow();
    setupAutoUpdater();
});

app.on('window-all-closed', () => {
    stopBackend();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

app.on('before-quit', () => {
    stopBackend();
});

// IPC handlers for renderer process
ipcMain.handle('open-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
            { name: 'Documents', extensions: ['docx'] }
        ]
    });
    return result.filePaths[0] || null;
});

ipcMain.handle('save-file-dialog', async (event, defaultName) => {
    const result = await dialog.showSaveDialog(mainWindow, {
        defaultPath: defaultName,
        filters: [
            { name: 'Documents', extensions: ['docx'] }
        ]
    });
    return result.filePath || null;
});

// Window control handlers
ipcMain.on('window-control', (event, action) => {
    if (!mainWindow) return;
    switch (action) {
        case 'minimize':
            mainWindow.minimize();
            break;
        case 'maximize':
            if (mainWindow.isMaximized()) {
                mainWindow.unmaximize();
            } else {
                mainWindow.maximize();
            }
            break;
        case 'close':
            mainWindow.close();
            break;
    }
});
