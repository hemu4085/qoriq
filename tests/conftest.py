"""pytest configuration for tests"""
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))
