
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.gemma_service import GemmaService

if __name__ == "__main__":
    print("Starting Gemma model download...")
    GemmaService.download_model()
    print("Gemma model download finished.")
