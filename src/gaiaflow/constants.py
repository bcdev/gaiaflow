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

AIRFLOW_SERVICES = [
    "airflow-apiserver",
    "airflow-scheduler",
    "airflow-init",
    "airflow-dag-processor",
    "airflow-triggerer",
    "postgres-airflow",
]

MLFLOW_SERVICES = ["mlflow", "postgres-mlflow"]

MINIO_SERVICES = ["minio", "minio_client"]

DEFAULT_MINIO_AWS_ACCESS_KEY_ID = "minio"
DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY = "minio123"
