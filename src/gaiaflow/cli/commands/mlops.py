from pathlib import Path
from typing import List
from types import SimpleNamespace

import fsspec
import typer

from gaiaflow.constants import Service

app = typer.Typer()
fs = fsspec.filesystem("file")

def load_imports():
    from gaiaflow.constants import BaseAction
    from gaiaflow.managers.mlops_manager import MlopsManager
    from gaiaflow.managers.utils import (
        create_gaiaflow_context_path,
        gaiaflow_path_exists_in_state,
        save_project_state,
    )

    return SimpleNamespace(
        BaseAction=BaseAction,
        MlopsManager=MlopsManager,
        create_gaiaflow_context_path=create_gaiaflow_context_path,
        gaiaflow_path_exists_in_state=gaiaflow_path_exists_in_state,
        save_project_state=save_project_state,
    )

@app.command(help="Start Gaiaflow development services")
def start(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="If you need a fresh gaiaflow installation. "
        "NOTE. It only removes the current version of Gaiaflow. If you need "
        "to remove the docker related stuff, use the cleanup --prune "
        "command",
    ),
    service: List[Service] = typer.Option(
        ["all"],
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
    imports = load_imports()
    typer.echo(f"Selected Gaiaflow services: {service}")
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(project_path)
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        imports.save_project_state(user_project_path, gaiaflow_path)
    else:
        typer.echo(
            f"Gaiaflow project already exists at {gaiaflow_path}. Skipping "
            f"saving to the state"
        )

    if service != ["all"]:
        for s in service:
            typer.echo(f"Running start on {s}...")
            imports.MlopsManager(
                gaiaflow_path=gaiaflow_path,
                user_project_path=user_project_path,
                force_new=force_new,
                action=imports.BaseAction.START,
                service=s,
                cache=cache,
                jupyter_port=jupyter_port,
                delete_volume=delete_volume,
                docker_build=docker_build,
            )
    else:
        typer.echo("Running start with all services")
        imports.MlopsManager(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            force_new=force_new,
            action=imports.BaseAction.START,
            service=Service.all,
            cache=cache,
            jupyter_port=jupyter_port,
            delete_volume=delete_volume,
            docker_build=docker_build,
        )


@app.command(help="Stop Gaiaflow development services")
def stop(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    service: List[Service] = typer.Option(
        ["all"],
        "--service",
        "-s",
        help="Services to manage. Use multiple --service flags, or leave empty to run all.",
    ),
    delete_volume: bool = typer.Option(
        False, "--delete-volume", "-v", help="Delete volumes on shutdown"
    ),
):
    """"""
    imports = load_imports()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(project_path)
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
    if service != ["all"]:
        for s in service:
            typer.echo(f"Stopping service:  {s}")
            imports.MlopsManager(
                Path(gaiaflow_path),
                Path(user_project_path),
                action=imports.BaseAction.STOP,
                service=s,
                delete_volume=delete_volume,
            )
    else:
        typer.echo("Stopping all services")
        imports.MlopsManager(
            Path(gaiaflow_path),
            Path(user_project_path),
            service=Service.all,
            action=imports.BaseAction.STOP,
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
        ["all"],
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
    imports = load_imports()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(project_path)
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
    if service != ["all"]:
        for s in service:
            typer.echo(f"Stopping service:  {s}")
            imports.MlopsManager(
                Path(gaiaflow_path),
                Path(user_project_path),
                force_new=force_new,
                action=imports.BaseAction.RESTART,
                service=s,
                cache=cache,
                jupyter_port=jupyter_port,
                delete_volume=delete_volume,
                docker_build=docker_build,
            )
    else:
        typer.echo("Stopping all services")
        imports.MlopsManager(
            Path(gaiaflow_path),
            Path(user_project_path),
            force_new=force_new,
            action=imports.BaseAction.RESTART,
            cache=cache,
            jupyter_port=jupyter_port,
            delete_volume=delete_volume,
            docker_build=docker_build,
            service=Service.all,
        )


@app.command(
    help="Clean Gaiaflow development services. This will remove the "
    "gaiaflow static context directory from the /tmp folder and "
    "also remove the state for this project."
)
def cleanup(
    project_path: Path = typer.Option(..., "--path", "-p", help="Path to your project"),
    prune: bool = typer.Option(
        False, "--prune", help="Prune Docker image, network and cache"
    ),
):
    imports = load_imports()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path)
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
    imports.MlopsManager(
        Path(gaiaflow_path),
        Path(user_project_path),
        action=imports.BaseAction.CLEANUP,
        prune=prune,
    )


# TODO: To let the user update the current infra with new local packages or
#  mounts as they want it.
# def update():
