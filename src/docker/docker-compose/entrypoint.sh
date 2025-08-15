#!/bin/bash
set -e

if [ -d "/opt/airflow/gaiaflow" ]; then
    echo "[INFO] Installing local gaiaflow..."
    pip install /opt/airflow/gaiaflow/
else
    echo "[INFO] Installing gaiaflow from PyPI..."
    pip install gaiaflow
fi

pixi install

exec airflow "$@"

