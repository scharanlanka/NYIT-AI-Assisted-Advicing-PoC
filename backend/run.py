"""
Production entry point for Railway.
Adds the parent directory to sys.path so the 'backend' package
resolves correctly when uvicorn is run from inside backend/.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app  # noqa: F401 — re-exported for uvicorn
