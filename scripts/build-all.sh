#!/bin/bash
# Build script for Glossio Desktop App

set -e

echo "=== Glossio Desktop Build Script ==="
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "Project root: $PROJECT_ROOT"
echo ""

# Step 1: Build Backend
echo "=== Building Backend (PyInstaller) ==="
cd "$PROJECT_ROOT"

# Activate virtual environment
source .venv/bin/activate

# Install PyInstaller if not present
pip install pyinstaller

# Build backend from project root
pyinstaller backend/glossio.spec --distpath build/dist --workpath build/work --clean

echo "Backend built successfully!"
echo ""

# Step 2: Build Frontend
echo "=== Building Frontend (Electron) ==="
cd "$PROJECT_ROOT/frontend"

# Install dependencies
npm install

# Build for current platform
npm run build

echo ""
echo "=== Build Complete! ==="
echo "Output: $PROJECT_ROOT/build/"
