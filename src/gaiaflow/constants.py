from enum import Enum
from pathlib import Path

GAIAFLOW_CONFIG_DIR = Path.home() / ".gaiaflow"
GAIAFLOW_CONFIG_DIR.mkdir(exist_ok=True)
GAIAFLOW_STATE_FILE = GAIAFLOW_CONFIG_DIR / "state.json"


class BaseAction(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    CLEANUP = "cleanup"


class ExtendedAction(str, Enum):
    DOCKERIZE = "dockerize"
    CREATE_CONFIG = "create_config"
    CREATE_SECRET = "create_secret"


class Service(str, Enum):
    airflow = "airflow"
    mlflow = "mlflow"
    minio = "minio"
    jupyter = "jupyter"
    all = "all"


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

# TODO: Talk with Tejas/Norman (currently contains random values)
RESOURCE_PROFILES = {
    "low": {
        "request_cpu": "250m",
        "limit_cpu": "500m",
        "request_memory": "512Mi",
        "limit_memory": "1Gi",
        "limit_gpu": "0",
    },
    "medium": {
        "request_cpu": "500m",
        "limit_cpu": "1",
        "request_memory": "1Gi",
        "limit_memory": "2Gi",
        "limit_gpu": "0",
    },
    "high": {
        "request_cpu": "1",
        "limit_cpu": "2",
        "request_memory": "2Gi",
        "limit_memory": "4Gi",
        "limit_gpu": "0.5",
    },
    "ultra": {
        "request_cpu": "2",
        "limit_cpu": "4",
        "request_memory": "4Gi",
        "limit_memory": "8Gi",
        "limit_gpu": "1",
    },
}
