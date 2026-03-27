# -*- mode: python ; coding: utf-8 -*-
"""
Glossio Backend PyInstaller Spec File
Builds a single executable for the Flask backend
"""

import sys
import os

block_cipher = None

# Get the project root directory (one level up from backend/)
project_root = os.path.abspath(os.path.join(SPECPATH, '..'))

a = Analysis(
    [
        os.path.join(project_root, 'run.py'),
        os.path.join(project_root, 'app', 'services', 'gemma_service.py'),
        os.path.join(project_root, 'app', 'services', 'task_queue.py'),
    ],
    pathex=[project_root],
    binaries=[],
    datas=[
        # Include templates
        (os.path.join(project_root, 'app/templates'), 'app/templates'),
        # Include static files
        (os.path.join(project_root, 'app/static'), 'app/static'),
        # Include data files (abbreviations CSVs)
        (os.path.join(project_root, 'app/data'), 'app/data'),
        # Include Firebase credentials
        (os.path.join(project_root, 'serviceAccountKey.json'), '.'),
        # Include .env file if exists
        (os.path.join(project_root, '.env'), '.') if os.path.exists(os.path.join(project_root, '.env')) else ('', ''),
    ],
    hiddenimports=[
        'eventlet',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'dns',
        'dns.resolver',
        'engineio.async_drivers.eventlet',
        'engineio.async_drivers.threading',
        'flask_socketio',
        'firebase_admin',
        'spacy',
        'simple_websocket',
        'wsproto',
        'redis',
        'app.services.gemma_service',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 
        'transformers', 
        'accelerate', 
        'bitsandbytes', 
        'nvidia', 
        'cuda', 
        'triton',
        'scipy',
        'pandas'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='glossio-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for production to hide console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
