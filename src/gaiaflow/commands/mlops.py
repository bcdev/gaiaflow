import json
from pathlib import Path
from typing import List

import fsspec
import typer

from ..managers.mlops_manager import MlopsManager, Service
from ..utils import get_gaiaflow_path, get_gaialfow_version, save_project_state

app = typer.Typer()
fs = fsspec.filesystem("file")


@app.command(help="Start Gaiaflow development services")
def start(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="If you need a "
        "fresh gaiaflow installation. "
        "NOTE. Currently it only removes "
        "the current version of Gaiaflow.",
    ),
    service: List[Service] = typer.Option(
        None,
        "--service",
        "-s",
        help="Services to manage. Use multiple --service flags, or leave empty to run all.",
    ),
    cache: bool = typer.Option(False, "--cache", "-c", help="Use Docker cache"),
    jupyter_port: int = typer.Option(
        8895, "--jupyter-port", "-j", help="Port for JupyterLab"
    ),
    delete_volume: bool = typer.Option(
        False, "--delete-volume", "-v", help="Delete volumes on shutdown"
    ),
    docker_build: bool = typer.Option(
        False, "--docker-build", "-b", help="Force Docker image build"
    ),
):
    typer.echo(f"Selected Gaiaflow services: {service}")
    user_project_path = Path(project_path).resolve()
    if not user_project_path.exists():
        raise FileNotFoundError(f"{user_project_path} not found")

    version = get_gaialfow_version()
    project_name = str(user_project_path).split("/")[-1]
    gaiaflow_path = Path(f"/tmp/gaiaflow-{version}-{project_name}")

    save_project_state(user_project_path, gaiaflow_path)
    print("force_new", force_new)

    # if service:
    #     for s in service:
    #         typer.echo(f"Running {action} on {s}...")
    #         MlopsManager(
    #             gaiaflow_path,
    #             user_project_path,
    #             force_new=force_new,
    #             action="start",
    #             service=s,
    #             cache=cache,
    #             jupyter_port=jupyter_port,
    #             delete_volume=delete_volume,
    #             docker_build=docker_build,
    #         )
    # else:
    #     typer.echo(f"Running {action} with all services")
    #     MlopsManager(
    #         gaiaflow_path,
    #         user_project_path,
    #         force_new=force_new,
    #         action="start",
    #         service=None,
    #         cache=cache,
    #         jupyter_port=jupyter_port,
    #         delete_volume=delete_volume,
    #         docker_build=docker_build,
    #     )


@app.command(help="Stop Gaiaflow development services")
def stop(
    service: List[Service] = typer.Option(
        None,
        "--service",
        "-s",
        help="Services to manage. Use multiple --service flags, or leave empty to run all.",
    ),
    delete_volume: bool = typer.Option(
        False, "--delete-volume", "-v", help="Delete volumes on shutdown"
    ),
):
    """"""
    gaiaflow_path = get_gaiaflow_path()
    print("gaiaflow_path", gaiaflow_path)
    # MlopsManager(
    #     gaiaflow_path,
    #     action="stop",
    #     service=service,
    #     delete_volume=delete_volume,
    # )


@app.command(help="Restart Gaiaflow development services")
def restart(
    service: List[Service] = typer.Option(
        None,
        "--service",
        "-s",
        help="Services to manage. Use multiple --service flags, or leave empty to run all.",
    ),
    delete_volume: bool = typer.Option(
        False, "--delete-volume", "-v", help="Delete volumes on shutdown"
    ),
):
    """"""
    gaiaflow_path = get_gaiaflow_path()
    print("gaiaflow_path", gaiaflow_path)
    # MlopsManager(
    #     gaiaflow_path,
    #     action="restart",
    #     service=service,
    #     delete_volume=delete_volume,
    # )


@app.command(help="Clean Gaiaflow development services")
def clean(
    service: List[Service] = typer.Option(
        None,
        "--service",
        "-s",
        help="Services to manage. Use multiple --service flags, or leave empty to run all.",
    ),
    delete_volume: bool = typer.Option(
        False, "--delete-volume", "-v", help="Delete volumes on shutdown"
    ),
):
    """"""
    gaiaflow_path = get_gaiaflow_path()
    print("gaiaflow_path", gaiaflow_path)
    # MlopsManager(
    #     gaiaflow_path,
    #     action="clean",
    #     service=service,
    #     delete_volume=delete_volume,
    # )
