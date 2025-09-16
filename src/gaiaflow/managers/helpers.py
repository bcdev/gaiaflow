import os
import shutil
import socket
import subprocess
from contextlib import contextmanager
from pathlib import Path

import psutil
import yaml

from gaiaflow.constants import AIRFLOW_SERVICES, MINIO_SERVICES, MLFLOW_SERVICES
from gaiaflow.managers.utils import (
    env_exists,
    find_python_packages,
    handle_error,
    is_wsl,
    log_error,
    log_info,
    run,
)


@contextmanager
def temporary_copy(src: Path, dest: Path):
    print("copying...", src, dest)
    shutil.copyfile(src, dest)
    try:
        yield
    finally:
        if dest.exists():
            dest.unlink()


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
        "alpine/socat",
    ]

    AIRFLOW_CONTAINERS = [
        "airflow-apiserver",
        "airflow-scheduler",
        "airflow-dag-processor",
        "airflow-triggerer",
        "docker-proxy",
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


class MinikubeHelper:
    def __init__(self, profile: str = "airflow"):
        self.profile = profile

    def is_running(self) -> bool:
        result = subprocess.run(
            ["minikube", "status", "--profile", self.profile],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return b"Running" in result.stdout

    def start(self):
        if self.is_running():
            log_info(f"Minikube cluster [{self.profile}] is already running.")
            return

        log_info(f"Starting Minikube cluster [{self.profile}]...")
        cmd = [
            "minikube",
            "start",
            "--profile",
            self.profile,
            "--driver=docker",
            "--cpus=4",
            "--memory=4g",
        ]
        if is_wsl():
            cmd.append("--extra-config=kubelet.cgroup-driver=cgroupfs")

        try:
            run(cmd, f"Error starting minikube profile [{self.profile}]")
        except subprocess.CalledProcessError:
            log_info("Retrying after cleanup...")
            self.cleanup()
            run(cmd, f"Error starting minikube profile [{self.profile}]")

    def stop(self):
        log_info(f"Stopping minikube profile [{self.profile}]...")
        run(
            ["minikube", "stop", "--profile", self.profile],
            f"Error stopping minikube profile [{self.profile}]",
        )

    def cleanup(self):
        log_info(f"Deleting minikube profile: {self.profile}")
        run(
            ["minikube", "delete", "--profile", self.profile],
            f"Error deleting minikube profile [{self.profile}]",
        )

    def run_cmd(self, args: list[str], **kwargs):
        full_cmd = ["minikube", "-p", self.profile] + args
        return subprocess.run(full_cmd, **kwargs)


class DockerHandlerMode:
    LOCAL = "local"
    MINIKUBE = "minikube"
    LOCAL_USER = "local-user"
    MINIKUBE_USER = "minikube-user"

class BaseDockerHandler:
    """Abstract docker handler with optional hooks."""
    def __init__(self, **kwargs):
        pass

    @classmethod
    def get_docker_handler(cls, mode: DockerHandlerMode, **kwargs):
        handler_cls = HANDLER_REGISTRY.get(mode)
        if not handler_cls:
            raise ValueError(f"Unknown Docker build mode: {mode}")
        return handler_cls(**kwargs)

    def pre_build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        """Override this if you want a different or no pre_build"""
        log_info(f"Updating Dockerfile at {dockerfile_path}")
        BaseDockerHandler._add_copy_statements_to_dockerfile(
            str(dockerfile_path), find_python_packages(project_path)
        )
        runner_src = Path(__file__).parent.parent.resolve() / "core" / "runner.py"
        runner_dest = project_path / "runner.py"
        return temporary_copy(runner_src, runner_dest)

    def build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        raise NotImplementedError

    def post_build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        pass

    def list_images(self):
        raise NotImplementedError

    def remove_image(self, image_name: str):
        raise NotImplementedError

    def _update_dockerfile(self, dockerfile_path: Path):
        BaseDockerHandler._add_copy_statements_to_dockerfile(
            str(dockerfile_path), find_python_packages(self.project_path)
        )

    @staticmethod
    def _add_copy_statements_to_dockerfile(
        dockerfile_path: str, local_packages: list[str]
    ):
        with open(dockerfile_path, "r") as f:
            lines = f.readlines()

        env_index = next(
            (i for i, line in enumerate(lines) if line.strip().startswith("ENV")),
            None,
        )

        if env_index is None:
            raise ValueError("No ENV found in Dockerfile.")

        entrypoint_index = next(
            (
                i
                for i, line in enumerate(lines)
                if line.strip().startswith("ENTRYPOINT")
            ),
            None,
        )

        if entrypoint_index is None:
            raise ValueError("No ENTRYPOINT found in Dockerfile.")

        copy_lines = [f"COPY {pkg} ./{pkg}\n" for pkg in local_packages]
        copy_lines.append("COPY runner.py ./runner.py\n")

        updated_lines = (
            lines[: env_index + 1]
            + copy_lines  #
            + lines[entrypoint_index:]
        )
        with open(dockerfile_path, "w") as f:
            f.writelines(updated_lines)

        print("Dockerfile updated with COPY statements.")


class LocalDockerHandler(BaseDockerHandler):
    def build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        log_info(f"Building Docker image [{image_name}] locally")
        run(
            [
                "docker",
                "build",
                "-t",
                image_name,
                "-f",
                str(dockerfile_path),
                str(project_path),
            ],
            "Error building Docker image locally",
        )

    def list_images(self):
        run(["docker", "image", "ls"], "Error listing Docker images locally")

    def remove_image(self, image_name: str):
        run(
            ["docker", "rmi", "-f", image_name],
            f"Error removing Docker image {image_name} locally",
        )


class MinikubeDockerHandler(BaseDockerHandler):
    def __init__(self, minikube_helper: MinikubeHelper):
        self.minikube_helper = minikube_helper
        self.env = self._get_minikube_env()

    def is_running(self):
        if not self.minikube_helper.is_running():
            raise RuntimeError(
                "Minikube not running. Please run the Gaiaflow services in prod-local mode first."
            )

    def build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        self.is_running()
        log_info(f"Building Docker image [{image_name}] in Minikube context")
        run(
            [
                "docker",
                "build",
                "-t",
                image_name,
                "-f",
                str(dockerfile_path),
                str(project_path),
            ],
            "Error building Docker image inside Minikube",
            env=self.env,
        )

    def list_images(self):
        self.is_running()
        run(
            ["docker", "image", "ls"],
            "Error listing Docker images inside Minikube",
            env=self.env,
        )

    def remove_image(self, image_name: str):
        self.is_running()
        run(
            ["docker", "rmi", "-f", image_name],
            f"Error removing Docker image {image_name} inside Minikube",
            env=self.env,
        )

    def _get_minikube_env(self):
        self.is_running()
        result = self.minikube_helper.run_cmd(
            ["docker-env", "--shell", "bash"], stdout=subprocess.PIPE, check=True
        )
        return MinikubeDockerHandler._parse_minikube_env(result.stdout.decode())

    @staticmethod
    def _parse_minikube_env(output: str) -> dict:
        env = os.environ.copy()
        for line in output.splitlines():
            if line.startswith("export "):
                try:
                    key, value = line.replace("export ", "").split("=", 1)
                    env[key.strip()] = value.strip('"')
                except ValueError:
                    continue
        return env


class LocalUserCustomImageDockerHandler(LocalDockerHandler):
    def pre_build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        pass

    def build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        log_info("Building user provided dockerfile")
        super().build(image_name, dockerfile_path, project_path)


class MinikubeUserCustomImageDockerHandler(MinikubeDockerHandler):
    def pre_build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        pass

    def build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        log_info("Building user provided dockerfile")
        super().build(image_name, dockerfile_path, project_path)


HANDLER_REGISTRY = {
    DockerHandlerMode.LOCAL: LocalDockerHandler,
    DockerHandlerMode.MINIKUBE: MinikubeDockerHandler,
    DockerHandlerMode.LOCAL_USER: LocalUserCustomImageDockerHandler,
    DockerHandlerMode.MINIKUBE_USER: MinikubeUserCustomImageDockerHandler,
}


class DockerHelper:
    def __init__(self, image_name: str, project_path: Path, handler: BaseDockerHandler):
        self.image_name = image_name
        self.project_path = project_path
        self.handler = handler

    def build_image(self, dockerfile_path: Path):
        if not dockerfile_path.exists():
            log_error(f"Dockerfile not found at {dockerfile_path}")
            return

        pre_build_ctx = self.handler.pre_build(
            self.image_name, dockerfile_path, self.project_path
        )
        if pre_build_ctx:
            with pre_build_ctx:
                self.handler.build(self.image_name, dockerfile_path, self.project_path)
        else:
            self.handler.build(self.image_name, dockerfile_path, self.project_path)

        self.handler.post_build(self.image_name, dockerfile_path, self.project_path)

    def list_images(self):
        self.handler.list_images()

    def remove_image(self, image_name: str):
        self.handler.remove_image(image_name)

    def prune_images(self):
        self.handler.prune_images()


class KubeConfigHelper:
    def __init__(self, gaiaflow_path: Path, os_type: str):
        self.gaiaflow_path = gaiaflow_path
        self.os_type = os_type

    def create_inline(self):
        if self.os_type == "linux" or is_wsl():
            kube_config = Path.home() / ".kube" / "config"
            backup_config = kube_config.with_suffix(".backup")

            self._backup_kube_config(kube_config, backup_config)
            self._patch_kube_config(kube_config)
            self._write_inline(kube_config)

            if backup_config.exists():
                shutil.copy(backup_config, kube_config)
                backup_config.unlink()
                log_info("Reverted kube config to original state.")

    def _backup_kube_config(self, kube_config: Path, backup_config: Path):
        if kube_config.exists():
            with open(kube_config, "r") as f:
                config_data = yaml.safe_load(f)
            with open(backup_config, "w") as f:
                yaml.dump(config_data, f)

    def _patch_kube_config(self, kube_config: Path):
        if not kube_config.exists():
            return

        with open(kube_config, "r") as f:
            config_data = yaml.safe_load(f)

        for cluster in config_data.get("clusters", []):
            cluster_info = cluster.get("cluster", {})
            if self.os_type == "windows":
                server = cluster_info.get("server", "")
                if "127.0.0.1" in server or "localhost" in server:
                    cluster_info["server"] = server.replace(
                        "127.0.0.1", "host.docker.internal"
                    ).replace("localhost", "host.docker.internal")
                    cluster_info["insecure-skip-tls-verify"] = True
            elif is_wsl():
                cluster_info["server"] = "https://192.168.49.2:8443"
                cluster_info["insecure-skip-tls-verify"] = True

        with open(kube_config, "w") as f:
            yaml.dump(config_data, f)

    def _write_inline(self, kube_config: Path):
        filename = self.gaiaflow_path / "_docker" / "kube_config_inline"
        log_info("Creating kube config inline file...")
        with open(filename, "w") as f:
            subprocess.call(
                [
                    "minikube",
                    "kubectl",
                    "--",
                    "config",
                    "view",
                    "--flatten",
                    "--minify",
                    "--raw",
                ],
                cwd=self.gaiaflow_path / "_docker",
                stdout=f,
            )
        log_info(f"Created kube config inline file {filename}")
