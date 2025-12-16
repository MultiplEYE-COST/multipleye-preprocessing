import sys
from pathlib import Path

# Ensure repository root is on sys.path so imports like `preprocessing.*` work
# tests/ is directly under the repo root, so parents[1] is the repository root
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
