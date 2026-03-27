# Glossio Desktop App

## Project Structure

```
glossio_web2/
├── frontend/          # Electron app
│   ├── main.js        # Main process (spawns backend)
│   ├── preload.js     # IPC bridge
│   └── package.json   # Electron dependencies
│
├── backend/           # PyInstaller config
│   └── glossio.spec   # Build specification
│
├── app/               # Flask application
├── scripts/           # Build and dev scripts
└── build/             # Build output
```

## Development

### Prerequisites
- Node.js 18+
- Python 3.10+
- PostgreSQL (for cloud mode)

### Run in Development
```bash
# Terminal 1: Start Flask backend
source .venv/bin/activate
python run.py

# Terminal 2: Start Electron
cd frontend
npm install
npm start
```

Or use the dev script:
```bash
./scripts/dev.sh
```

## Building

### Build for Current Platform
```bash
./scripts/build-all.sh
```

### Build for Specific Platform
```bash
# Backend only
pyinstaller backend/glossio.spec

# Frontend only
cd frontend
npm run build:win   # Windows
npm run build:mac   # macOS
npm run build:linux # Linux
```

## Architecture

- **Electron (frontend)**: Renders UI in Chromium, manages window
- **Flask (backend)**: API, database, WebSocket, Firebase auth
- **Communication**: HTTP + WebSocket over localhost:5000

## User Modes

| Mode | Database | Collaboration |
|------|----------|---------------|
| Offline | SQLite | ❌ |
| Online | PostgreSQL | ✅ |
