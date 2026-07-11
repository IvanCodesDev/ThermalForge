from __future__ import annotations

import os


# Tests may exercise explicitly labelled development/screening adapters. The
# installed application itself runs in THERMALFORGE_MODE=real.
os.environ.setdefault("THERMALFORGE_MODE", "development")
