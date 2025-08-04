from pathlib import Path
from typing import Literal

GAIAFLOW_CONFIG_DIR = Path.home() / ".gaiaflow"
GAIAFLOW_CONFIG_DIR.mkdir(exist_ok=True)
GAIAFLOW_STATE_FILE = GAIAFLOW_CONFIG_DIR / "state.json"

ACTIONS = Literal["start", "stop", "restart"]
