import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
import yaml

from gaiaflow.constants import ACTIONS
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.utils import log_error, log_info, run

# from gen_docker_image_name import DOCKER_IMAGE_NAME


class MinikubeManager(BaseGaiaflowManager):
    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: ACTIONS,
        force_new: bool = False,
        build_only: bool = False,
        create_config_only: bool = False,
        secret_data: dict =None,
        secret_name: str = "",
        prune: bool = False,
    ):
        super().__init__(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            action=action,
            force_new=force_new,
            prune=prune
        )

        if secret_data is None:
            secret_data = {}

        self.minikube_profile = "airflow"
        self.docker_image_name = "DOCKER_IMAGE_NAME"
        self.build_only = build_only
        self.os_type = platform.system().lower()

        if action == "stop":
            self.stop_minikube()
        elif action == "restart":
            self.stop_minikube()
            self.start_minikube()
        elif action == "start":
            self.start_minikube()
        elif build_only:
            self.build_docker_image()
        elif create_config_only:
            self.create_kube_config_inline()
        elif secret_data != {}:
            self.create_secrets(secret_name, secret_data)

    def start_minikube(self):
        # TODO: Use force_new and stop docker services
        log_info(f"Checking Minikube cluster [{self.minikube_profile}] status...")
        try:
            result = subprocess.run(
                ["minikube", "status", "--profile", self.minikube_profile],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            if b"Running" in result.stdout:
                log_info(
                    f"Minikube cluster [{self.minikube_profile}] is already running."
                )
        except subprocess.CalledProcessError:
            log_info(
                f"Minikube cluster [{self.minikube_profile}] is not running. Starting..."
            )

            run(
                [
                    "minikube",
                    "start",
                    "--profile",
                    self.minikube_profile,
                    "--driver=docker",
                    "--cpus=4",
                    "--memory=4g",
                ],
                f"Error starting minikube profile [{self.minikube_profile}]",
            )

        self.create_kube_config_inline()
        self.restart_docker_compose()

    def stop_minikube(self):
        log_info(f"Stopping minikube profile [{self.minikube_profile}]...")
        try:
            run(
                ["minikube", "stop", "--profile", self.minikube_profile],
                f"Error stopping minikube profile [{self.minikube_profile}]",
            )
        except Exception as e:
            log_info(str(e))
            log_info(f"Deleting profile {self.minikube_profile}")
        run(
            ["minikube", "delete", "--profile", self.minikube_profile],
            f"Error deleting minikube profile [{self.minikube_profile}]",
        )
        log_info(f"Stopped minikube profile [{self.minikube_profile}]")

    def build_docker_image(self):
        if not Path("Dockerfile").exists():
            log_error(f"Dockerfile not found at {Path('Dockerfile')}")
        log_info(f"Building Docker image [{self.docker_image_name}]...")

        result = subprocess.run(
            ["minikube", "-p", self.minikube_profile, "docker-env", "--shell", "bash"],
            stdout=subprocess.PIPE,
            check=True,
        )
        env = os.environ.copy()
        for line in result.stdout.decode().splitlines():
            if line.startswith("export "):
                try:
                    key, value = line.replace("export ", "").split("=", 1)
                    env[key.strip()] = value.strip('"')
                except ValueError:
                    continue
        run(
            ["docker", "build", "-t", self.docker_image_name, "."],
            "Error building docker image.",
            env=env,
        )

    def create_kube_config_inline(self):
        kube_config = Path.home() / ".kube" / "config"
        backup_config = kube_config.with_suffix(".backup")
        filename = "../kube_config_inline"

        if self.os_type == "windows" and kube_config.exists():
            log_info("Detected Windows: patching kube config with host.docker.internal")
            with open(kube_config, "r") as f:
                config_data = yaml.safe_load(f)

            with open(backup_config, "w") as f:
                yaml.dump(config_data, f)

            for cluster in config_data.get("clusters", []):
                server = cluster.get("cluster", {}).get("server", "")
                if "127.0.0.1" in server or "localhost" in server:
                    cluster["cluster"]["server"] = server.replace(
                        "127.0.0.1", "host.docker.internal"
                    ).replace("localhost", "host.docker.internal")

            with open(kube_config, "w") as f:
                yaml.dump(config_data, f)

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
                stdout=f,
            )

        log_info(f"Created kube config inline file {filename}")

        log_info(
            f"Adding insecure-skip-tls-verfiy for local setup in kube config inline file {filename}"
        )

        with open(filename, "r") as f:
            kube_config_data = yaml.safe_load(f)

        if self.os_type == "windows":
            for cluster in kube_config_data.get("clusters", []):
                cluster_data = cluster.get("cluster", {})
                if "insecure-skip-tls-verify" not in cluster_data:
                    cluster_data["insecure-skip-tls-verify"] = True

        log_info(f"Saving kube config inline file {filename}")
        with open(filename, "w") as f:
            yaml.safe_dump(kube_config_data, f, default_flow_style=False)

        if self.os_type == "windows" and backup_config.exists():
            shutil.copy(backup_config, kube_config)
            backup_config.unlink()
            log_info("Reverted kube config to original state.")

    def create_secrets(self, secret_name: str, secret_data: dict[str, Any]):
        log_info(f"Checking if secret [{secret_name}] exists...")
        check_cmd = [
            "minikube",
            "kubectl",
            "-p",
            self.minikube_profile,
            "--",
            "get",
            "secret",
            secret_name,
        ]
        result = subprocess.run(
            check_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if result.returncode == 0:
            log_info(f"Secret [{secret_name}] already exists. Skipping creation.")
        else:
            log_info(f"Creating secret [{secret_name}]...")
            create_cmd = [
                "minikube",
                "kubectl",
                "-p",
                self.minikube_profile,
                "--",
                "create",
                "secret",
                "generic",
                secret_name,
            ]
            for k, v in secret_data.items():
                create_cmd.append(f"--from-literal={k}={v}")
            subprocess.check_call(create_cmd)

    def start(self):
        log_info("Starting full setup...")
        self.start_minikube()
        self.build_docker_image()
        self.create_kube_config_inline()
        self.create_secrets(
            secret_name="my-minio-creds",
            secret_data={
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
            },
        )
        log_info(f"Minikube cluster [{self.minikube_profile}] is ready!")

    def restart_docker_compose(self):
        log_info("Restarting Docker Compose services...")
        run(
            [
                "docker",
                "compose",
                "-f",
                "docker/docker-compose/docker-compose.yml",
                "down",
            ],
            "Error running docker compose down",
        )
        run(
            [
                "docker",
                "compose",
                "-f",
                "docker/docker-compose/docker-compose.yml",
                "-f",
                "docker/docker-compose/docker-compose-minikube-network.yml",
                "up",
                "-d",
            ],
            "Error running docker compose up",
        )


app = typer.Typer()


@app.command()
def manage(
    stop: bool = typer.Option(False, "--stop", "-s", help="Stop minikube cluster"),
    restart: bool = typer.Option(
        False, "--restart", "-r", help="Restart minikube cluster"
    ),
    start: bool = typer.Option(False, "--start", help="Start minikube cluster"),
    build_only: bool = typer.Option(
        False, "--build-only", help="Only build docker image inside minikube"
    ),
    create_config_only: bool = typer.Option(
        False, "--create-config-only", help="Create inline config for Docker compose."
    ),
    create_secrets: bool = typer.Option(
        False, "--create-secrets", help="Create secrets for pods (Deprecated)"
    ),
):
    print("pwd", os.getcwd())
    manager = MinikubeManager()

    if stop:
        manager.stop_minikube()
    elif restart:
        manager.stop_minikube()
        manager.start_minikube()
    elif start:
        manager.start_minikube()
    elif build_only:
        manager.build_docker_image()
    elif create_config_only:
        manager.create_kube_config_inline()

    if create_secrets:
        manager.create_secrets(
            secret_name="my-minio-creds",
            secret_data={
                "AWS_ACCESS_KEY_ID": "minio",
                "AWS_SECRET_ACCESS_KEY": "minio123",
            },
        )
