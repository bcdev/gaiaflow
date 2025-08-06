from enum import Enum
from pathlib import Path

GAIAFLOW_CONFIG_DIR = Path.home() / ".gaiaflow"
GAIAFLOW_CONFIG_DIR.mkdir(exist_ok=True)
GAIAFLOW_STATE_FILE = GAIAFLOW_CONFIG_DIR / "state.json"


class BaseActions(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    CLEANUP = "cleanup"


class ExtendedActions(str, Enum):
    DOCKERIZE = "dockerize"
    CREATE_CONFIG = "create_config"
    CREATE_SECRET = "create_secret"
