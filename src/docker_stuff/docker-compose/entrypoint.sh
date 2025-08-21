#!/bin/bash
set -e

if [ -d "/opt/airflow/gaiaflow" ]; then
    echo "[INFO] Installing local gaiaflow..."
    pip install /opt/airflow/gaiaflow/ -e .
else
    echo "[INFO] Installing gaiaflow from PyPI..."
    pip install gaiaflow
fi

micromamba run -n default_user_env pip install -e /opt/airflow/

exec airflow "$@"

