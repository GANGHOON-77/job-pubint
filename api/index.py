# Vercel serverless function
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi_server import app

# Vercel handler
handler = app