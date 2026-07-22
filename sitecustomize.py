"""Start FrameJoin Studio only for the renamed embedded pythonw launcher."""
from __future__ import annotations

import os
import sys
from pathlib import Path


if Path(sys.executable).name.lower() == "framejoinstudio.exe":
    root = Path(sys.executable).resolve().parent
    os.chdir(root)
    sys.path.insert(0, str(root))
    from framejoin.ui import run

    raise SystemExit(run())
