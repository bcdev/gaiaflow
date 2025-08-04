from pathlib import Path
from typing import List

import fsspec
import typer

from gaiaflow.managers.mlops_manager import MlopsManager, Service
from gaiaflow.utils import (
    gaiaflow_path_exists_in_state,
    get_gaialfow_version,
    save_project_state,
)

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
    gaiaflow_path_exists = gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if gaiaflow_path_exists:
        save_project_state(user_project_path, gaiaflow_path)
    else:
        typer.echo(
            f"Gaiaflow project already exists at {gaiaflow_path}. Skipping "
            f"saving to the state"
        )

    if service:
        for s in service:
            typer.echo(f"Running start on {s}...")
            MlopsManager(
                gaiaflow_path=gaiaflow_path,
                user_project_path=user_project_path,
                force_new=force_new,
                action="start",
                service=s,
                cache=cache,
                jupyter_port=jupyter_port,
                delete_volume=delete_volume,
                docker_build=docker_build,
            )
    else:
        typer.echo("Running start with all services")
        MlopsManager(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            force_new=force_new,
            action="start",
            service=None,
            cache=cache,
            jupyter_port=jupyter_port,
            delete_volume=delete_volume,
            docker_build=docker_build,
        )


@app.command(help="Stop Gaiaflow development services")
def stop(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
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
    user_project_path = Path(project_path).resolve()
    if not user_project_path.exists():
        raise FileNotFoundError(f"{user_project_path} not found")

    version = get_gaialfow_version()
    project_name = str(user_project_path).split("/")[-1]
    gaiaflow_path = Path(f"/tmp/gaiaflow-{version}-{project_name}")
    gaiaflow_path_exists = gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
    if service:
        for s in service:
            typer.echo(f"Stopping service:  {s}")
            MlopsManager(
                Path(gaiaflow_path),
                Path(user_project_path),
                action="stop",
                service=s,
                delete_volume=delete_volume,
            )
    else:
        typer.echo("Stopping all services")
        MlopsManager(
            Path(gaiaflow_path),
            Path(user_project_path),
            action="stop",
            delete_volume=delete_volume,
        )


@app.command(help="Restart Gaiaflow development services")
def restart(
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
    delete_volume: bool = typer.Option(
        False, "--delete-volume", "-v", help="Delete volumes on shutdown"
    ),
    cache: bool = typer.Option(False, "--cache", "-c", help="Use Docker cache"),
    jupyter_port: int = typer.Option(
        8895, "--jupyter-port", "-j", help="Port for JupyterLab"
    ),
    docker_build: bool = typer.Option(
        False, "--docker-build", "-b", help="Force Docker image build"
    ),
):
    """"""
    user_project_path = Path(project_path).resolve()
    if not user_project_path.exists():
        raise FileNotFoundError(f"{user_project_path} not found")

    version = get_gaialfow_version()
    project_name = str(user_project_path).split("/")[-1]
    gaiaflow_path = Path(f"/tmp/gaiaflow-{version}-{project_name}")
    gaiaflow_path_exists = gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
    if service:
        for s in service:
            typer.echo(f"Stopping service:  {s}")
            MlopsManager(
                Path(gaiaflow_path),
                Path(user_project_path),
                force_new=force_new,
                action="restart",
                service=s,
                cache=cache,
                jupyter_port=jupyter_port,
                delete_volume=delete_volume,
                docker_build=docker_build,
            )
    else:
        typer.echo("Stopping all services")
        MlopsManager(
            Path(gaiaflow_path),
            Path(user_project_path),
            force_new=force_new,
            action="restart",
            cache=cache,
            jupyter_port=jupyter_port,
            delete_volume=delete_volume,
            docker_build=docker_build,
        )


@app.command(
    help="Clean Gaiaflow development services. This will remove the "
    "gaiaflow static context directory from the /tmp folder and "
    "also remove the state for this project."
)
def clean(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    prune: bool = typer.Option(
        False, "--prune", help="Prune Docker image, network and cache"
    ),
):
    user_project_path = Path(project_path).resolve()
    if not user_project_path.exists():
        raise FileNotFoundError(f"{user_project_path} not found")
    version = get_gaialfow_version()
    project_name = str(user_project_path).split("/")[-1]
    gaiaflow_path = Path(f"/tmp/gaiaflow-{version}-{project_name}")
    gaiaflow_path_exists = gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
    MlopsManager(
        Path(gaiaflow_path),
        Path(user_project_path),
        action="clean",
        prune=prune,
    )


# TODO: To let the user update the current infra with new local packages or
#  mounts as they want it.
# def update():
