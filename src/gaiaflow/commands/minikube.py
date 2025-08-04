from pathlib import Path

import fsspec
import typer

from gaiaflow.managers.minikube_manager import MinikubeManager
from gaiaflow.utils import parse_key_value_pairs

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
    MinikubeManager(action="start", force_new=force_new)


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
    print(secret_data, name)


@app.command(
    help="Clean Gaiaflow production-like services. This will only remove the "
    "minikube speicifc things. To remove local docker stuff, use the dev mode."
)
def clean(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    prune: bool = typer.Option(False, "--prune", help=""),
):
    """"""
