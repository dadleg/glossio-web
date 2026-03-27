from dotenv import load_dotenv
load_dotenv()

import sys
from app import create_app
from app.extensions import socketio


# Force PyInstaller to include services
if False:
    import app.services.gemma_service
    import app.services.task_queue

app = create_app()

if __name__ == '__main__':
    # In PyInstaller bundle, use production settings
    is_frozen = getattr(sys, 'frozen', False)
    socketio.run(
        app, 
        debug=not is_frozen,
        allow_unsafe_werkzeug=True  # Required for production with threading mode
    )
