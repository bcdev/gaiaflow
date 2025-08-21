# Gaiaflow

[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://bcdev.github.io/gaiaflow/)
![Static Badge](https://img.shields.io/badge/Airflow-3.0-8A2BE2?logo=apacheairflow)
![Static Badge](https://img.shields.io/badge/MLFlow-darkblue?logo=mlflow)
![Static Badge](https://img.shields.io/badge/MinIO-red?logo=minio)
![Static Badge](https://img.shields.io/badge/Jupyter-grey?logo=jupyter)
![Static Badge](https://img.shields.io/badge/Minikube-lightblue?logo=kubernetes)


Gaiaflow is a local-first MLOps infrastructure python package tool that simplifies the process 
of building, testing, and deploying ML workflows.
It provides an opinionated CLI for managing Airflow, MLflow, and other 
dependencies, abstracting away complex configurations, and giving you 
a smooth developer experience.

Gaiaflow is a tool that
- provides you with a local MLOps infrastructure via a CLI tool with 
some prerequisites already installed.
- handles the complex Airflow configuration and [Xcom](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html) 
handling and provides the user a simpler interface for creating DAGs.
- provides a [cookiecutter template](https://github.com/bcdev/gaiaflow-cookiecutter)
to get started with your projects with a standardized structure.

- provides tools to deploy models locally and in production (in future)
- provides clear documentation on how to setup production environment to run your 
workflows at scale (in future, private?)


Prerequisites:
- Docker
- Docker compose
- Miniforge
- Mamba/Conda

To install it, you can do it via:

`pip install gaiaflow`

Check installation:

`gaiaflow --help`

You can read the documentation [here]()