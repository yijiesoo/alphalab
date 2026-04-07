"""
Pytest configuration and fixtures for tests.

This file sets up the Python path so tests can import from flask_app and factor-lab.
"""

import sys
from pathlib import Path

# Add the project root to sys.path so imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure both modules are importable
sys.path.insert(0, str(project_root / "flask_app"))
sys.path.insert(0, str(project_root / "factor-lab"))
