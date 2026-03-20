import sys
import os

# Add the project root to sys.path so we can import 'backend'
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.main import app
