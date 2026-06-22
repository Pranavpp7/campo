# conftest.py  (project root)
import sys
from pathlib import Path

# Make sure the project root is on sys.path so test files can import
# agents, memory, tools, etc. directly.
sys.path.insert(0, str(Path(__file__).parent))