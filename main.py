#!/usr/bin/env python3
"""Main entry point for OpenSubTools GUI."""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from subtitles.gui.app import main

if __name__ == "__main__":
    main()
