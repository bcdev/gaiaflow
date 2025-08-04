import json
import os
import platform
import shutil
import socket
import subprocess
from enum import Enum
from pathlib import Path

import fsspec
import psutil
from ruamel.yaml import YAML

from gaiaflow.constants import ACTIONS, GAIAFLOW_STATE_FILE
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.utils import (
    create_directory,
    delete_project_state,
    find_python_packages,
    handle_error,
    log_error,
    log_info,
    run,
)


class Service(str, Enum):
    airflow = "airflow"
    mlflow = "mlflow"
    minio = "minio"
    jupyter = "jupyter"


_AIRFLOW_SERVICES = [
    "airflow-apiserver",
    "airflow-scheduler",
    "airflow-init",
    "airflow-dag-processor",
    "airflow-triggerer",
    "postgres-airflow",
]

_MLFLOW_SERVICES = ["mlflow", "postgres-mlflow"]

_MINIO_SERVICES = ["minio", "minio_client"]

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
        action: ACTIONS,
        service: Service = None,
        cache: bool = False,
        jupyter_port: int = 8895,
        delete_volume: bool = False,
        docker_build: bool = False,
        force_new: bool = False,
        prune: bool = False,
    ):
        super().__init__(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            action=action,
            force_new=force_new,
            prune=prune,
        )
        self.service = service
        self.cache = cache
        self.jupyter_port = jupyter_port
        self.delete_volume = delete_volume
        self.docker_build = docker_build
        self.os_type = platform.system().lower()
        self.project_root = Path(__file__).resolve().parent
        self.fs = fsspec.filesystem("file")

        if self.action == "stop":
            self.stop()

        if self.action == "restart":
            self.stop()
            self.start()

        if self.action == "start":
            self.start()

        if self.action == "clean":
            self.stop()
            self.cleanup()

    def check_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", self.jupyter_port)) == 0:
                handle_error(f"Port {self.jupyter_port} is already in use.")

    def stop_jupyter(self):
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
    def docker_services_for(component):
        services = {
            "airflow": _AIRFLOW_SERVICES,
            "mlflow": _MLFLOW_SERVICES,
            "minio": _MINIO_SERVICES,
        }
        return services.get(component, [])

    def docker_compose_action(self, actions, service=None):
        base_cmd = [
            "docker",
            "compose",
            "-f",
            f"{self.gaiaflow_path}/docker/docker-compose/docker-compose.yml",
        ]
        if service:
            services = MlopsManager.docker_services_for(service)
            print("Services:::", services, service)
            if not services:
                handle_error(f"Unknown service: {service}")
            cmd = base_cmd + actions + services
        else:
            cmd = base_cmd + actions

        log_info(f"Running: {' '.join(cmd)}")
        run(cmd, f"Error running docker compose {actions}")

    def stop(self):
        log_info("Shutting down Gaiaflow services...")
        if self.service == "jupyter":
            self.stop_jupyter()
        elif self.service is None:
            down_cmd = ["down"]
            if self.delete_volume:
                log_info("Removing volumes with shutdown")
                down_cmd.append("-v")
            self.docker_compose_action(down_cmd, self.service)
            self.stop_jupyter()
        else:
            down_cmd = ["down"]
            if self.delete_volume:
                log_info("Removing volumes with shutdown")
                down_cmd.append("-v")
            self.docker_compose_action(down_cmd, self.service)

        log_info("Stopped Gaiaflow services successfully")

    def start_jupyter(self):
        log_info("Starting Jupyter Lab...")
        cmd = ["jupyter", "lab", "--ip=0.0.0.0", f"--port={self.jupyter_port}"]
        subprocess.Popen(cmd)

    def update_env_file_with_airflow_uid(self, env_path):
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

    def create_gaiaflow_context(self, force_new: bool = False):
        if force_new:
            shutil.rmtree(self.gaiaflow_path)
        self.fs.makedirs(self.gaiaflow_path, exist_ok=True)

        package_dir = Path(__file__).parent.parent.resolve()
        docker_dir = package_dir.parent / "docker"

        shutil.copytree(docker_dir, self.gaiaflow_path / "docker", dirs_exist_ok=True)
        shutil.copy(package_dir.parent / ".env", self.gaiaflow_path / ".env")
        shutil.copy(
            self.user_project_path / "environment.yml",
            self.gaiaflow_path / "environment.yml",
        )
        log_info(f"Gaiaflow context created at {self.gaiaflow_path}")

    def update_files(self):
        yaml = YAML()
        yaml.preserve_quotes = True

        compose_path = (
            self.gaiaflow_path / "docker" / "docker-compose" / "docker-compose.yml"
        )

        with open(compose_path) as f:
            compose_data = yaml.load(f)

        env_file = self.gaiaflow_path / "environment.yml"

        def get_env_name_from_yml(env_file: Path) -> str:
            with open(env_file, "r") as f:
                env_yaml = yaml.load(f)
            return env_yaml.get("name")

        env_name = get_env_name_from_yml(env_file)

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

        for child in self.user_project_path.iterdir():
            if (
                child.is_dir() and child.name not in existing_mounts and child.name
            ) in python_packages:
                dst_path = f"/opt/airflow/{child.name}"
                new_volumes.append(f"{child.resolve()}:{dst_path}")

        compose_data["x-airflow-common"]["volumes"] = new_volumes

        result = [f"/opt/airflow/{item}" for item in python_packages]
        pythonpath_entry = ":".join(result)
        log_info("Found and mounting following python packages " + str(python_packages))
        env_updates = {
            "PYTHONPATH": f"{pythonpath_entry}:/opt/airflow/dags:${{PYTHONPATH}}",
            "PATH": f"/home/airflow/.local/share/mamba/envs/{env_name}/bin:/usr/bin:/bin:${{PATH}}",
            "LD_LIBRARY_PATH": f"/home/airflow/.local/share/mamba/envs/{env_name}/lib:/lib/x86_64-linux-gnu:${{LD_LIBRARY_PATH}}",
        }

        compose_data["x-airflow-common"]["environment"].update(env_updates)

        with compose_path.open("w") as f:
            yaml.dump(compose_data, f)

    def start(self):
        log_info("Starting Gaiaflow services")
        log_info("Setting up directories...")
        create_directory(f"{self.user_project_path}/logs")
        create_directory(f"{self.user_project_path}/data")
        log_info("Updating .env file...")
        self.update_env_file_with_airflow_uid(f"{self.user_project_path}/.env")
        log_info("Creating gaiaflow context...")
        self.create_gaiaflow_context(self.force_new)
        log_info("Updating gaiaflow context with user project information...")
        self.update_files()

        if self.service == "jupyter" or self.service is None:
            self.check_port()

        if self.docker_build:
            build_cmd = ["build"]
            if not self.cache:
                build_cmd.append("--no-cache")

            log_info("Building Docker images")
            self.docker_compose_action(build_cmd, self.service)

        if self.service is None:
            self.start_jupyter()
            self.docker_compose_action(["up", "-d"], service=None)
        elif self.service == "jupyter":
            self.start_jupyter()
        else:
            self.docker_compose_action(["up", "-d"], service=self.service)

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
