import json
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path

import fsspec
import psutil
from ruamel.yaml import YAML

from gaiaflow.constants import (AIRFLOW_SERVICES, GAIAFLOW_STATE_FILE,
                                MINIO_SERVICES, MLFLOW_SERVICES, Action,
                                BaseAction, Service)
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.managers.utils import (create_directory, delete_project_state,
                                     find_python_packages,
                                     gaiaflow_path_exists_in_state,
                                     handle_error, log_error, log_info, run,
                                     save_project_state, set_permissions)

_IMAGES = [
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

_VOLUMES = [
    "docker-compose_postgres-db-volume-airflow",
    "docker-compose_postgres-db-volume-mlflow",
]


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
        **kwargs,
    ):
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")
        self.service = service
        self.cache = cache
        self.jupyter_port = jupyter_port
        self.delete_volume = delete_volume
        self.docker_build = docker_build
        self.os_type = platform.system().lower()
        self.project_root = Path(__file__).resolve().parent
        self.fs = fsspec.filesystem("file")
        self.prod_local = prod_local

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

        manager = MlopsManager(**kwargs)

        action_map = {
            BaseAction.START: manager.start,
            BaseAction.STOP: manager.stop,
            BaseAction.RESTART: manager.restart,
            BaseAction.CLEANUP: manager.cleanup,
        }

        try:
            action_method = action_map[action]
        except KeyError:
            raise ValueError(f"Unknown action: {action}")

        action_method()

    def start(self):
        log_info("Starting Gaiaflow services")

        if self.force_new:
            self.cleanup()

        gaiaflow_path_exists = gaiaflow_path_exists_in_state(self.gaiaflow_path, True)

        if not gaiaflow_path_exists:
            log_info("Setting up directories...")
            create_directory(f"{self.user_project_path}/logs")
            create_directory(f"{self.user_project_path}/data")

            log_info("Updating .env file...")
            self._update_env_file_with_airflow_uid(f"{self.user_project_path}/.env")

            log_info("Creating gaiaflow context...")
            self._create_gaiaflow_context()

            log_info("Updating gaiaflow context with user project information...")
            self._update_files()

            save_project_state(self.user_project_path, self.gaiaflow_path)
        else:
            log_info(
                "Gaiaflow project already exists at "
                f"{self.gaiaflow_path}, "
                "skipping creating new context."
            )

        if self.service == Service.jupyter or self.service == Service.all:
            self._check_port()

        if self.docker_build:
            build_cmd = ["build"]
            if not self.cache:
                build_cmd.append("--no-cache")

            log_info("Building Docker images")
            self._docker_compose_action(build_cmd, self.service)

        if self.service == Service.all:
            self._start_jupyter()
            self._docker_compose_action(["up", "-d"], service=None)
        elif self.service == Service.jupyter:
            self._start_jupyter()
        else:
            self._docker_compose_action(["up", "-d"], service=self.service)

    def stop(self):
        log_info("Shutting down Gaiaflow services...")
        if self.service == Service.jupyter:
            self._stop_jupyter()
        elif self.service == Service.all:
            down_cmd = ["down"]
            if self.delete_volume:
                log_info("Removing volumes with shutdown")
                down_cmd.append("-v")
            self._docker_compose_action(down_cmd)
            self._stop_jupyter()
        else:
            down_cmd = ["down"]
            if self.delete_volume:
                log_info("Removing volumes with shutdown")
                down_cmd.append("-v")
            self._docker_compose_action(down_cmd, self.service)

        log_info("Stopped Gaiaflow services successfully")

    def _check_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", self.jupyter_port)) == 0:
                handle_error(f"Port {self.jupyter_port} is already in use.")

    def _stop_jupyter(self):
        log_info(f"Attempting to stop Jupyter processes on port {self.jupyter_port}")
        for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                name = proc.info.get("name") or ""
                if any("jupyter-lab" in arg for arg in cmdline) or "jupyter" in name:
                    log_info(f"Terminating process {proc.pid} ({name})")
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    @staticmethod
    def _docker_services_for(component):
        services = {
            "airflow": AIRFLOW_SERVICES,
            "mlflow": MLFLOW_SERVICES,
            "minio": MINIO_SERVICES,
        }
        return services.get(component, [])

    def _docker_compose_action(self, actions, service=None):
        if self.prod_local:
            base_cmd = [
                "docker",
                "compose",
                "-f",
                f"{self.gaiaflow_path}/docker/docker-compose/docker-compose.yml",
                "-f",
                f"{self.gaiaflow_path}/docker/docker-compose/docker-compose-minikube-network.yml",
            ]
        else:
            base_cmd = [
                "docker",
                "compose",
                "-f",
                f"{self.gaiaflow_path}/docker/docker-compose/docker-compose.yml",
            ]
        if service:
            services = MlopsManager._docker_services_for(service)
            print("Services:::", services, service)
            if not services:
                handle_error(f"Unknown service: {service}")
            cmd = base_cmd + actions + services
        else:
            cmd = base_cmd + actions

        log_info(f"Running: {' '.join(cmd)}")
        run(cmd, f"Error running docker compose {actions}")

    def _start_jupyter(self):
        log_info("Starting Jupyter Lab...")
        cmd = ["jupyter", "lab", "--ip=0.0.0.0", f"--port={self.jupyter_port}"]
        subprocess.Popen(cmd)

    def _update_env_file_with_airflow_uid(self, env_path):
        if self.os_type == "linux":
            uid = str(os.getuid())
        else:
            uid = 50000

        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()

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

        with open(env_path, "w") as f:
            f.writelines(new_lines)

        log_info(f"Set AIRFLOW_UID={uid} in {env_path}")

    def _create_gaiaflow_context(self):
        self.fs.makedirs(self.gaiaflow_path, exist_ok=True)

        package_dir = Path(__file__).parent.parent.resolve()
        docker_dir = package_dir.parent / "docker"

        shutil.copytree(docker_dir, self.gaiaflow_path / "docker", dirs_exist_ok=True)
        shutil.copy(
            self.user_project_path / "environment.yml",
            self.gaiaflow_path / "environment.yml",
        )
        log_info(f"Gaiaflow context created at {self.gaiaflow_path}")

    def _update_files(self):
        yaml = YAML()
        yaml.preserve_quotes = True

        compose_path = (
            self.gaiaflow_path / "docker" / "docker-compose" / "docker-compose.yml"
        )

        with open(compose_path) as f:
            compose_data = yaml.load(f)

        x_common = compose_data.get("x-airflow-common", {})
        original_vols = x_common.get("volumes", [])
        new_volumes = []
        for vol in original_vols:
            parts = vol.split(":", 1)
            if len(parts) == 2:
                src, dst = parts
                src_path = (self.user_project_path / Path(src).name).resolve()
                print("src_path", src_path)
                new_volumes.append(f"{src_path}:{dst}")

        existing_mounts = {Path(v.split(":", 1)[0]).name for v in new_volumes}
        python_packages = find_python_packages(self.user_project_path)

        for python_package in python_packages:
            set_permissions(python_package, 0o755)

        for child in self.user_project_path.iterdir():
            if (
                child.is_dir() and child.name not in existing_mounts and child.name
            ) in python_packages:
                dst_path = f"/opt/airflow/{child.name}"
                new_volumes.append(f"{child.resolve()}:{dst_path}")

        new_volumes.append(
            f"{self.gaiaflow_path / 'docker'}/kube_config_inline:/home/airflow/.kube/config"
        )
        new_volumes.append(
            f"{self.gaiaflow_path / 'docker' / 'docker-compose'}/entrypoint.sh:/opt/airflow/entrypoint.sh"
        )
        new_volumes.append(
            f"{self.user_project_path}/pyproject.toml:/opt/airflow/pyproject.toml"
        )
        # TODO: For windows not needed?
        new_volumes.append("/var/run/docker.sock:/var/run/docker.sock")
        # TODO: Remove this before publishing .This is only needed for
        #  development
        new_volumes.append("/home/yogesh/Projects/BC/gaiaflow:/opt/airflow/gaiaflow")

        compose_data["x-airflow-common"]["volumes"] = new_volumes

        with compose_path.open("w") as f:
            yaml.dump(compose_data, f)

        entrypoint_path = (
            self.gaiaflow_path / "docker" / "docker-compose" / "entrypoint.sh"
        )
        set_permissions(entrypoint_path)

    def cleanup(self):
        try:
            log_info("Attempting deleting Gaiaflow context at {self.gaiaflow_path}")
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
            run(
                ["docker", "builder", "prune", "-a", "-f"],
                "Error pruning docker build cache",
            )
            run(
                ["docker", "system", "prune", "-a", "-f"],
                "Error pruning docker system",
            )
            run(
                ["docker", "volume", "prune", "-a", "-f"],
                "Error pruning docker volumes",
            )
            run(
                ["docker", "network", "rm", "docker-compose_ml-network"],
                "Error removing docker network",
            )
            for image in _IMAGES:
                run(["docker", "rmi", "-f", image], f"Error deleting image {image}")
            for volume in _VOLUMES:
                run(
                    ["docker", "volume", "rm", volume],
                    f"Error removing volume {volume}",
                )
        log_info("Gaiaflow cleanup complete!")
