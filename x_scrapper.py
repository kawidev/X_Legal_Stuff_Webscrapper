from __future__ import annotations

import sys
from pathlib import Path


# Allow running the project before editable install (`pip install -e .`).
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from x_legal_stuff_webscrapper.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
