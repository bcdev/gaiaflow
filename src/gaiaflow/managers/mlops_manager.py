import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Set

import fsspec
import psutil
import yaml
from ruamel.yaml import YAML

from gaiaflow.constants import (
    AIRFLOW_SERVICES,
    GAIAFLOW_STATE_FILE,
    MINIO_SERVICES,
    MLFLOW_SERVICES,
    Action,
    BaseAction,
    ExtendedAction,
    Service,
)
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.managers.utils import (
    convert_crlf_to_lf,
    create_directory,
    delete_project_state,
    env_exists,
    gaiaflow_path_exists_in_state,
    handle_error,
    log_error,
    log_info,
    run,
    save_project_state,
    set_permissions,
    update_entrypoint_install_path,
    update_micromamba_env_in_docker,
)


class DockerResources:
    IMAGES = [
        "docker-compose-airflow-apiserver:latest",
        "docker-compose-airflow-scheduler:latest",
        "docker-compose-airflow-dag-processor:latest",
        "docker-compose-airflow-triggerer:latest",
        "docker-compose-airflow-init:latest",
        "docker-compose-mlflow:latest",
        "minio/mc:latest",
        "minio/minio:latest",
        "postgres:13",
    ]

    AIRFLOW_CONTAINERS = [
        "airflow-apiserver",
        "airflow-scheduler",
        "airflow-dag-processor",
        "airflow-triggerer",
    ]

    VOLUMES = [
        "docker-compose_postgres-db-volume-airflow",
        "docker-compose_postgres-db-volume-mlflow",
    ]

    SERVICES = {
        "airflow": AIRFLOW_SERVICES,
        "mlflow": MLFLOW_SERVICES,
        "minio": MINIO_SERVICES,
    }


class DockerComposeHelper:
    def __init__(self, gaiaflow_path: Path, is_prod_local: bool):
        self.gaiaflow_path = gaiaflow_path
        self.is_prod_local = is_prod_local

    def _base_cmd(self) -> list[str]:
        base = [
            "docker",
            "compose",
            "-f",
            f"{self.gaiaflow_path}/_docker/docker-compose/docker-compose.yml",
        ]
        if self.is_prod_local:
            base += [
                "-f",
                f"{self.gaiaflow_path}/_docker/docker-compose/docker-compose-minikube-network.yml",
            ]
        return base

    @staticmethod
    def docker_services_for(component: str) -> list[str]:
        return DockerResources.SERVICES.get(component, [])

    def run_compose(self, actions: list[str], service: str | None = None):
        cmd = self._base_cmd()
        if service:
            services = self.docker_services_for(service)
            if not services:
                handle_error(f"Unknown service: {service}")
            cmd += actions + services
        else:
            cmd += actions

        log_info(f"Running: {' '.join(cmd)}")
        run(cmd, f"Error running docker compose {actions}")

    @staticmethod
    def prune():
        prune_cmds = [
            (
                ["docker", "builder", "prune", "-a", "-f"],
                "Error pruning docker build cache",
            ),
            (["docker", "system", "prune", "-a", "-f"], "Error pruning docker system"),
            (["docker", "volume", "prune", "-a", "-f"], "Error pruning docker volumes"),
            (
                ["docker", "network", "rm", "docker-compose_ml-network"],
                "Error removing docker network",
            ),
        ]
        for cmd, msg in prune_cmds:
            run(cmd, msg)

        for image in DockerResources.IMAGES:
            run(["docker", "rmi", "-f", image], f"Error deleting image {image}")
        for volume in DockerResources.VOLUMES:
            run(["docker", "volume", "rm", volume], f"Error removing volume {volume}")


class JupyterHelper:
    def __init__(
        self, port: int, env_tool: str, user_env_name: str | None, gaiaflow_path: Path
    ):
        self.port = port
        self.env_tool = env_tool
        self.user_env_name = user_env_name
        self.gaiaflow_path = gaiaflow_path

    def check_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", self.port)) == 0:
                handle_error(f"Port {self.port} is already in use.")

    def stop(self):
        log_info(f"Attempting to stop Jupyter processes on port {self.port}")
        for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                name = proc.info.get("name") or ""
                if "jupyter" in name or any("jupyter-lab" in arg for arg in cmdline):
                    log_info(f"Terminating process {proc.pid} ({name})")
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def start(self):
        env_name = self.get_env_name()
        if not env_exists(env_name, env_tool=self.env_tool):
            print(
                f"Environment {env_name} not found. Run `mamba env create -f environment.yml`?"
            )
            return
        cmd = [
            self.env_tool,
            "run",
            "-n",
            env_name,
            "jupyter",
            "lab",
            "--ip=0.0.0.0",
            f"--port={self.port}",
        ]
        log_info("Starting Jupyter Lab..." + " ".join(cmd))
        subprocess.Popen(cmd)

    def get_env_name(self):
        if self.user_env_name:
            return self.user_env_name
        env_path = Path(self.gaiaflow_path).resolve() / "environment.yml"
        with open(env_path, "r") as f:
            env_yml = yaml.safe_load(f)
        return env_yml.get("name")


class MlopsManager(BaseGaiaflowManager):
    """Manager class to Start/Stop/Restart MLOps Docker services."""

    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: Action,
        service: Service = Service.all,
        cache: bool = False,
        jupyter_port: int = 8895,
        delete_volume: bool = False,
        docker_build: bool = False,
        force_new: bool = False,
        prune: bool = False,
        prod_local: bool = False,
        user_env_name: str | None = None,
        env_tool: str = "mamba",
        **kwargs,
    ):
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")
        if env_tool not in ("mamba", "conda"):
            raise ValueError(
                f"Invalid env_tool: {env_tool}. Must be 'mamba' or 'conda'"
            )
        self.service = service
        self.cache = cache
        self.delete_volume = delete_volume
        self.docker_build = docker_build
        self.os_type = platform.system().lower()
        # self.project_root = Path(__file__).resolve().parent
        self.fs = fsspec.filesystem("file")
        self.prod_local = prod_local
        self.user_env_name = user_env_name
        self.env_tool = env_tool

        self.docker = DockerComposeHelper(gaiaflow_path, prod_local)
        self.jupyter = JupyterHelper(
            jupyter_port, env_tool, user_env_name, gaiaflow_path
        )

        super().__init__(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            action=action,
            force_new=force_new,
            prune=prune,
        )

    @classmethod
    def run(cls, **kwargs):
        action = kwargs.get("action")
        if action is None:
            raise ValueError("Missing required argument 'action'")

        manager = cls(**kwargs)

        action_map = {
            BaseAction.START: manager.start,
            BaseAction.STOP: manager.stop,
            BaseAction.RESTART: manager.restart,
            BaseAction.CLEANUP: manager.cleanup,
            ExtendedAction.UPDATE_DEPS: manager.update_deps,
        }

        try:
            action_map[action]()
        except KeyError:
            raise ValueError(f"Unknown action: {action}")

    def start(self):
        log_info("Starting Gaiaflow services")

        if self.force_new:
            self.cleanup()

        if not gaiaflow_path_exists_in_state(self.gaiaflow_path, True):
            self._setup_project_context()
        else:
            log_info(
                "Gaiaflow project already exists at "
                f"{self.gaiaflow_path}, "
                "skipping creating new context."
            )

        self._copy_user_env_file()

        if self.service in {Service.jupyter, Service.all}:
            self.jupyter.check_port()

        if self.docker_build:
            self._build_docker_images()

        self._start_services()

    def stop(self):
        log_info("Shutting down Gaiaflow services...")

        if self.service == Service.jupyter:
            self.jupyter.stop()
        elif self.service == Service.all:
            self._stop_all_services()
        else:
            self._stop_service(self.service)

        log_info("Stopped Gaiaflow services successfully")

    def cleanup(self):
        try:
            log_info(f"Attempting deleting Gaiaflow context at {self.gaiaflow_path}")
            shutil.rmtree(self.gaiaflow_path)
        except FileNotFoundError:
            log_error(f"Gaiaflow context not found at {self.gaiaflow_path}")

        try:
            log_info(
                f"Attempting deleting Gaiaflow project state at {GAIAFLOW_STATE_FILE}"
            )
            delete_project_state(self.gaiaflow_path)
        except (json.JSONDecodeError, FileNotFoundError):
            raise
        if self.prune:
            self.docker.prune()

        log_info("Gaiaflow cleanup complete!")

    @staticmethod
    def update_deps():
        log_info("Running update_deps")
        update_micromamba_env_in_docker(DockerResources.AIRFLOW_CONTAINERS)
        log_info("Finished running update_deps")

    def _setup_project_context(self):
        create_directory(self.user_project_path / "logs")
        create_directory(self.user_project_path / "data")

        log_info("Updating .env file...")
        self._update_env_file_with_airflow_uid(self.user_project_path / ".env")

        log_info("Creating gaiaflow context...")
        self._create_gaiaflow_context()

        log_info("Updating gaiaflow context with user project information...")
        self._update_files()

        save_project_state(self.user_project_path, self.gaiaflow_path)

    def _build_docker_images(self):
        build_cmd = ["build"]
        if not self.cache:
            build_cmd.append("--no-cache")
        log_info("Building Docker images")
        if self.service == Service.all:
            self.docker.run_compose(build_cmd)
        elif self.service != Service.jupyter:
            self.docker.run_compose(build_cmd, self.service)

    def _start_services(self):
        if self.service == Service.all:
            self.jupyter.start()
            self.docker.run_compose(["up", "-d"])
        elif self.service == Service.jupyter:
            self.jupyter.start()
        else:
            self.docker.run_compose(["up", "-d"], self.service)

    def _stop_all_services(self):
        down_cmd = ["down"]
        if self.delete_volume:
            log_info("Removing volumes with shutdown")
            down_cmd.append("-v")
        self.docker.run_compose(down_cmd)
        self.jupyter.stop()

    def _stop_service(self, service: Service):
        down_cmd = ["down"]
        if self.delete_volume:
            log_info("Removing volumes with shutdown")
            down_cmd.append("-v")
        self.docker.run_compose(down_cmd, service)

    def _update_env_file_with_airflow_uid(self, env_path: Path):
        uid = str(os.getuid()) if self.os_type == "linux" else "50000"

        lines = []
        if env_path.exists():
            lines = env_path.read_text().splitlines(keepends=True)

        key_found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("AIRFLOW_UID="):
                new_lines.append(f"AIRFLOW_UID={uid}\n")
                key_found = True
            else:
                new_lines.append(line)

        if not key_found:
            new_lines.append(f"AIRFLOW_UID={uid}\n")

        env_path.write_text("".join(new_lines))

        log_info(f"Set AIRFLOW_UID={uid} in {env_path}")

    def _copy_user_env_file(self):
        log_info("Copying user environment.yml file")
        shutil.copy(
            self.user_project_path / "environment.yml",
            self.gaiaflow_path / "environment.yml",
        )

    def _create_gaiaflow_context(self):
        self.fs.makedirs(self.gaiaflow_path, exist_ok=True)

        package_dir = Path(__file__).parent.parent.resolve()
        docker_dir = package_dir.parent / "_docker"

        shutil.copytree(docker_dir, self.gaiaflow_path / "_docker", dirs_exist_ok=True)
        log_info(f"Gaiaflow context created at {self.gaiaflow_path}")

    def _collect_volumes(self, compose_data: dict) -> list[str]:
        x_common = compose_data.get("x-airflow-common", {})
        original_vols = x_common.get("volumes", [])
        new_volumes = []

        # Re-map predefined volumes to absolute paths
        for vol in original_vols:
            if ":" in vol:
                src, dst = vol.split(":", 1)
                src_path = (
                    (self.user_project_path / Path(src).name).resolve().as_posix()
                )
                new_volumes.append(f"{src_path}:{dst}")

        # Set permissions so that docker containers can execute the code in
        # their package
        set_permissions(self.user_project_path, 0o755)

        new_volumes.append(
            f"{self.user_project_path.resolve().as_posix()}:/opt/airflow/{self.user_project_path.name}"
        )

        # Add special mounts for prod_local mode
        kube_config = (
            self.gaiaflow_path.resolve() / "_docker" / "kube_config_inline"
        ).as_posix()
        entrypoint = (
            self.gaiaflow_path.resolve()
            / "_docker"
            / "docker-compose"
            / "entrypoint.sh"
        ).as_posix()
        pyproject = (self.user_project_path.resolve() / "pyproject.toml").as_posix()
        env_file = (self.user_project_path.resolve() / "environment.yml").as_posix()

        new_volumes += [
            f"{kube_config}:/home/airflow/.kube/config",
            f"{entrypoint}:/opt/airflow/entrypoint.sh",
            f"{pyproject}:/opt/airflow/pyproject.toml",
            f"{env_file}:/opt/airflow/environment.yml",
            "/var/run/docker.sock:/var/run/docker.sock",
        ]

        return new_volumes

    def _update_files(self):
        yaml = YAML()
        yaml.preserve_quotes = True

        compose_path = (
            self.gaiaflow_path / "_docker" / "docker-compose" / "docker-compose.yml"
        )

        with open(compose_path) as f:
            compose_data = yaml.load(f)

        new_volumes = self._collect_volumes(compose_data)
        compose_data["x-airflow-common"]["volumes"] = new_volumes

        with compose_path.open("w") as f:
            yaml.dump(compose_data, f)

        entrypoint_path = (
            self.gaiaflow_path / "_docker" / "docker-compose" / "entrypoint.sh"
        )
        update_entrypoint_install_path(
            entrypoint_path, str(self.user_project_path.name)
        )
        set_permissions(entrypoint_path)
        convert_crlf_to_lf(entrypoint_path)

    def _get_valid_actions(self) -> Set[Action]:
        return super()._get_valid_actions() | {ExtendedAction.UPDATE_DEPS}
