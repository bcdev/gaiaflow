from pathlib import Path
from types import SimpleNamespace

import fsspec
import typer

from gaiaflow.constants import DEFAULT_IMAGE_NAME
from gaiaflow.managers.helpers import DockerHandlerMode

app = typer.Typer()
fs = fsspec.filesystem("file")


def load_imports():
    from gaiaflow.constants import BaseAction
    from gaiaflow.managers.minikube_manager import ExtendedAction, MinikubeManager
    from gaiaflow.managers.utils import (
        create_gaiaflow_context_path,
        gaiaflow_path_exists_in_state,
        parse_key_value_pairs,
    )

    return SimpleNamespace(
        BaseAction=BaseAction,
        ExtendedAction=ExtendedAction,
        MinikubeManager=MinikubeManager,
        create_gaiaflow_context_path=create_gaiaflow_context_path,
        gaiaflow_path_exists_in_state=gaiaflow_path_exists_in_state,
        parse_key_value_pairs=parse_key_value_pairs,
    )


@app.command(help="Start Gaiaflow production-like services.")
def start(
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="Set this to true if you need a "
        "fresh production-like environment installation. ",
    ),
):
    """"""
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.BaseAction.START,
        force_new=force_new,
    )


@app.command(help="Stop Gaiaflow production-like services.")
def stop():
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.BaseAction.STOP,
    )


@app.command(help="Restart Gaiaflow production-like services.")
def restart(
    force_new: bool = typer.Option(
        False,
        "--force-new",
        "-f",
        help="Set this to true if you need a "
        "fresh production-like environment installation. ",
    ),
):
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.BaseAction.RESTART,
        force_new=force_new,
    )


@app.command(
    help="Containerize your package into a docker image inside the minikube cluster."
)
def dockerize(
    image_name: str = typer.Option(
        DEFAULT_IMAGE_NAME, "--image-name", "-i", help=("Name of your image.")
    ),
    dockerfile_path: Path = typer.Option(
        None, "--dockerfile-path", "-d", help=("Path to your custom Dockerfile")
    ),
):
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    if dockerfile_path:
        docker_build_mode = "minikube-user"
    else:
        docker_build_mode = "minikube"
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.ExtendedAction.DOCKERIZE,
        docker_build_mode=docker_build_mode,
        image_name=image_name,
        dockerfile_path=dockerfile_path,
    )


@app.command(help="List all the docker images in your system")
def list_images():
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.ExtendedAction.LIST_IMAGES,
        docker_handler_mode=DockerHandlerMode.MINIKUBE,
    )

@app.command(help="Delete a docker image from your system")
def remove_image(image_name: str = typer.Option(
        DEFAULT_IMAGE_NAME, "--image-name", "-i", help=("Name of image "
                                                        "to be deleted.")
    ),):
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.ExtendedAction.REMOVE_IMAGE,
        image_name=image_name,
        docker_handler_mode=DockerHandlerMode.MINIKUBE,
    )


@app.command(
    help="Create a config file for Airflow to talk to Kubernetes "
    "cluster. To be used only when debugging required."
)
def create_config():
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.ExtendedAction.CREATE_CONFIG,
    )


@app.command(help="Create secrets to provide to the production-like environment.")
def create_secret(
    name: str = typer.Option(..., "--name", help="Name of the secret"),
    data: list[str] = typer.Option(
        ..., "--data", help="Secret data as key=value pairs"
    ),
):
    imports = load_imports()
    project_path = Path.cwd()
    secret_data = imports.parse_key_value_pairs(data)
    print(secret_data, name)
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action=imports.ExtendedAction.CREATE_SECRET,
        secret_name=name,
        secret_data=secret_data,
    )


@app.command(
    help="Clean Gaiaflow production-like services. This will only remove the "
    "minikube specific things. To remove local docker stuff, use the dev mode."
)
def cleanup():
    imports = load_imports()
    project_path = Path.cwd()
    gaiaflow_path, user_project_path = imports.create_gaiaflow_context_path(
        project_path
    )
    gaiaflow_path_exists = imports.gaiaflow_path_exists_in_state(gaiaflow_path, True)
    if not gaiaflow_path_exists:
        typer.echo("Please create a project with Gaiaflow before running this command.")
        return
    imports.MinikubeManager.run(
        gaiaflow_path=gaiaflow_path,
        user_project_path=user_project_path,
        action="cleanup",
    )
