import os
import platform
import socket
import subprocess
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional

import psutil
import typer

from ..utils import handle_error, log, run


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


class MlopsManager:
    def __init__(
        self,
        gaiaflow_path: str,
        user_project_path: str,
        force_new: bool = False,
        action: str = None,
        service: Service = None,
        cache: bool = False,
        jupyter_port: int = 8895,
        delete_volume: bool = False,
        docker_build: bool = False,
    ):
        self.action = action
        self.service = service
        self.cache = cache
        self.jupyter_port = jupyter_port
        self.delete_volume = delete_volume
        self.docker_build = docker_build
        self.os_type = platform.system().lower()
        current_dir = Path(__file__).resolve().parent
        self.project_root = current_dir
        self.gaiaflow_path = gaiaflow_path
        self.user_project_path = user_project_path
        self.force_new = force_new

        if action == "stop":
            self.cleanup()

        if action == "restart":
            self.cleanup()
            self.start()

        if action == "start":
            self.start()

    def create_directory(self, dir_name):
        if not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
                log(f"Created directory: {dir_name}")
            except Exception as e:
                handle_error(f"Failed to create {dir_name} directory: {e}")
        else:
            log(f"Directory {dir_name} already exists")

        try:
            os.chmod(dir_name, 0o777)
            log(f"Set permissions for {dir_name}")
        except Exception:
            log(f"Warning: Could not set permissions for {dir_name}")

    def check_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", self.jupyter_port)) == 0:
                handle_error(f"Port {self.jupyter_port} is already in use.")

    def stop_jupyter(self):
        log(f"Attempting to stop Jupyter processes on port {self.jupyter_port}")
        for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                name = proc.info.get("name") or ""
                if any("jupyter-lab" in arg for arg in cmdline) or "jupyter" in name:
                    log(f"Terminating process {proc.pid} ({name})")
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

        log(f"Running: {' '.join(cmd)}")
        run(cmd, f"Error running docker compose {actions}")

    def cleanup(self):
        log("Shutting down Gaiaflow services...")
        if self.service == "jupyter":
            self.stop_jupyter()
        elif self.service is None:
            down_cmd = ["down"]
            if self.delete_volume:
                log("Removing volumes with shutdown")
                down_cmd.append("-v")
            self.docker_compose_action(down_cmd, self.service)
            self.stop_jupyter()
        else:
            down_cmd = ["down"]
            if self.delete_volume:
                log("Removing volumes with shutdown")
                down_cmd.append("-v")
            self.docker_compose_action(down_cmd, self.service)

        log("Cleanup complete")

    def start_jupyter(self):
        log("Starting Jupyter Lab...")
        cmd = ["jupyter", "lab", "--ip=0.0.0.0", f"--port={self.jupyter_port}"]
        subprocess.Popen(cmd)

    def update_env_file_with_airflow_uid(self, env_path=".env"):
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

        print(f"Set AIRFLOW_UID={uid} in {env_path}")

    def create_gaiaflow_context(self, force_new: bool = False):
        if force_new:
            shutil.rmtree(self.gaiaflow_path)
        fs.makedirs(self.gaiaflow_path, exist_ok=True)

        script_dir = Path(__file__).parent.resolve()
        docker_dir = script_dir.parent / "docker"

        shutil.copytree(docker_dir, self.gaiaflow_path / "docker", dirs_exist_ok=True)
        shutil.copy(script_dir.parent / ".env", self.gaiaflow_path / ".env")
        shutil.copy(
            user_project_path / "environment.yml",
            self.gaiaflow_path / "environment.yml",
        )

    def update_files(self):
        yaml = YAML()
        yaml.preserve_quotes = True

        print("gaiaflow_path", self.gaiaflow_path)
        compose_path = (
            self.gaiaflow_path / "docker" / "docker-compose" / "docker-compose.yml"
        )
        print("compose_path", compose_path)

        with open(compose_path) as f:
            compose_data = yaml.load(f)

        env_file = self.gaiaflow_path / "environment.yml"

        def get_env_name_from_yml(env_file: Path) -> str:
            with open(env_file, "r") as f:
                env_yaml = yaml.load(f)
            return env_yaml.get("name")

        env_name = get_env_name_from_yml(env_file)
        print(env_name)

        x_common = compose_data.get("x-airflow-common", {})
        original_vols = x_common.get("volumes", [])
        new_volumes = []
        print("original_vols", original_vols)
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
        print("python_packages", python_packages, pythonpath_entry)
        env_updates = {
            "PYTHONPATH": f"{pythonpath_entry}:/opt/airflow/dags:${{PYTHONPATH}}",
            "PATH": f"/home/airflow/.local/share/mamba/envs/{env_name}/bin:/usr/bin:/bin:${{PATH}}",
            "LD_LIBRARY_PATH": f"/home/airflow/.local/share/mamba/envs/{env_name}/lib:/lib/x86_64-linux-gnu:${{LD_LIBRARY_PATH}}",
        }

        compose_data["x-airflow-common"]["environment"].update(env_updates)

        with compose_path.open("w") as f:
            yaml.dump(compose_data, f)

    def start(self):
        log("Starting Gaiaflow services")
        log("Setting up directories and gaiaflow context...")
        self.create_directory("../logs")
        self.create_directory("../data")
        self.update_env_file_with_airflow_uid()
        self.create_gaiaflow_context(self.force_new)
        self.update_files()

        if self.service == "jupyter" or self.service is None:
            self.check_port()

        if self.docker_build:
            build_cmd = ["build"]
            if not self.cache:
                build_cmd.append("--no-cache")

            log("Building Docker images")
            self.docker_compose_action(build_cmd, self.service)

        if self.service is None:
            self.start_jupyter()
            self.docker_compose_action(["up", "-d"], service=None)
        elif self.service == "jupyter":
            self.start_jupyter()
        else:
            self.docker_compose_action(["up", "-d"], service=self.service)
