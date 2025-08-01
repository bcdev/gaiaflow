import json
from pathlib import Path
from typing import List

import fsspec
import typer

from ..managers.minikube_manager import MinikubeManager

from ..utils import (get_gaiaflow_path, get_gaialfow_version,
                     save_project_state, parse_key_value_pairs)

app = typer.Typer()
fs = fsspec.filesystem("file")


@app.command(help="Start Gaiaflow production-like services.")
def start(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="Set this to true if you need a "
        "fresh production-like environment installation. ",
    ),
):
    """"""

@app.command(help="Stop Gaiaflow production-like services.")
def stop(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="Set this to true if you need a "
        "fresh production-like environment installation. ",
    ),
):
    """"""


@app.command(help="Clean Gaiaflow production-like services.")
def clean(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="Set this to true if you need a "
        "fresh production-like environment installation. ",
    ),
):
    """"""


@app.command(help="Restart Gaiaflow production-like services.")
def restart(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="Set this to true if you need a "
        "fresh production-like environment installation. ",
    ),
):
    """"""


@app.command(help="Containerize your package into a docker image.")
def dockerize(
    local: bool = typer.Option(
        False,
        "--local",
        "-l",
        help="This will create the image in your local docker instance instead "
        "of creating it inside prod-local environment",
    ),
):
    """"""


@app.command(
    help="Create a config file for Airflow to talk to Kubernetes "
    "cluster. To be used only when debugging required."
)
def create_config():
    """"""


@app.command(help="Create secrets to provide to the production-like environment.")
def create_secrets(
    name: str = typer.Option(..., "--name", help="Name of the secret"),
    data: list[str] = typer.Option(
        ..., "--data", help="Secret data as key=value pairs"
    ),
):
    secret_data = parse_key_value_pairs(data)
    print(secret_data)

