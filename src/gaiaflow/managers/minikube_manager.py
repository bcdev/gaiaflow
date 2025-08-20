import os
import platform
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Set

import yaml

from gaiaflow.constants import (AIRFLOW_SERVICES, MINIO_SERVICES,
                                MLFLOW_SERVICES, Action, BaseAction,
                                ExtendedAction)
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.managers.mlops_manager import MlopsManager
from gaiaflow.managers.utils import (find_python_packages, log_error, log_info,
                                     run, set_permissions)


@contextmanager
def temporary_copy(src: Path, dest: Path):
    print("copying...", src, dest)
    shutil.copy(src, dest)
    try:
        yield
    finally:
        if dest.exists():
            dest.unlink()


class MinikubeManager(BaseGaiaflowManager):
    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: Action,
        force_new: bool = False,
        prune: bool = False,
        local: bool = False,
        image_name: str = "",
        **kwargs,
    ):
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {list(kwargs.keys())}")
        self.minikube_profile = "airflow"
        # TODO: get the docker image name automatically
        #  For CI, get the package name, version and create repository. See
        #  in test-airflow-ci test_ecr_push.yml
        self.os_type = platform.system().lower()
        self.local = local
        self.image_name = image_name

        super().__init__(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            action=action,
            force_new=force_new,
            prune=prune,
        )

    def _get_valid_actions(self) -> Set[Action]:
        return {
            BaseAction.START,
            BaseAction.STOP,
            BaseAction.RESTART,
            BaseAction.CLEANUP,
            ExtendedAction.DOCKERIZE,
            ExtendedAction.CREATE_CONFIG,
            ExtendedAction.CREATE_SECRET,
        }

    @classmethod
    def run(cls, **kwargs):
        action = kwargs.get("action")
        if action is None:
            raise ValueError("Missing required argument 'action'")

        manager = MinikubeManager(**kwargs)

        action_map = {
            BaseAction.START: manager.start,
            BaseAction.STOP: manager.stop,
            BaseAction.RESTART: manager.restart,
            BaseAction.CLEANUP: manager.cleanup,
            ExtendedAction.DOCKERIZE: manager.build_docker_image,
            ExtendedAction.CREATE_CONFIG: manager.create_kube_config_inline,
            ExtendedAction.CREATE_SECRET: manager.create_secrets,
        }

        try:
            action_method = action_map[action]
        except KeyError:
            raise ValueError(f"Unknown action: {action}")

        if action == ExtendedAction.CREATE_SECRET:
            action_method(kwargs["secret_name"], kwargs["secret_data"])
        else:
            action_method()

    def start(self):
        if self.force_new:
            self.cleanup()
        MlopsManager(self.gaiaflow_path, self.user_project_path, action=BaseAction.STOP)
        log_info(f"Checking Minikube cluster [{self.minikube_profile}] status...")
        result = subprocess.run(
            ["minikube", "status", "--profile", self.minikube_profile],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if b"Running" in result.stdout:
            log_info(f"Minikube cluster [{self.minikube_profile}] is already running.")
        else:
            log_info(
                f"Minikube cluster [{self.minikube_profile}] is not running. Starting..."
            )
            try:
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
            except subprocess.CalledProcessError:
                log_info("Cleaning up and starting again...")
                self.cleanup()
                self.start()

        self.create_kube_config_inline()
        MlopsManager(
            self.gaiaflow_path,
            self.user_project_path,
            action=BaseAction.START,
            prod_local=True,
            force_new=self.force_new,
        )

    def stop(self):
        log_info(f"Stopping minikube profile [{self.minikube_profile}]...")
        try:
            run(
                ["minikube", "stop", "--profile", self.minikube_profile],
                f"Error stopping minikube profile [{self.minikube_profile}]",
            )
            log_info(f"Stopped minikube profile [{self.minikube_profile}]")
        except Exception as e:
            log_info(str(e))

    def create_kube_config_inline(self):
        kube_config = Path.home() / ".kube" / "config"
        backup_config = kube_config.with_suffix(".backup")
        filename = f"{self.gaiaflow_path / 'docker'}/kube_config_inline"

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
                cwd=self.gaiaflow_path / "docker",
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

    def build_docker_image(self):
        dockerfile_path = self.gaiaflow_path / "docker" / "user-package" / "Dockerfile"
        if not (dockerfile_path.exists()):
            log_error(f"Dockerfile not found at {dockerfile_path}")
            return

        log_info(f"Updating dockerfile at {dockerfile_path}")
        MinikubeManager._add_copy_statements_to_dockerfile(
            dockerfile_path, find_python_packages(self.user_project_path)
        )
        runner_src = Path(__file__).parent.parent.resolve() / "core" / "runner.py"
        runner_dest = self.user_project_path / "runner.py"

        with temporary_copy(runner_src, runner_dest):
            if self.local:
                log_info(f"Building Docker image [{self.image_name}] locally")
                run(
                    [
                        "docker",
                        "build",
                        "-t",
                        self.image_name,
                        "-f",
                        dockerfile_path,
                        self.user_project_path,
                    ],
                    "Error building docker image.",
                )
                # TODO: For windows?
                set_permissions("/var/run/docker.sock", 0o666)
            else:
                log_info(
                    f"Building Docker image [{self.image_name}] in minikube context"
                )
                result = subprocess.run(
                    [
                        "minikube",
                        "-p",
                        self.minikube_profile,
                        "docker-env",
                        "--shell",
                        "bash",
                    ],
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
                    [
                        "docker",
                        "build",
                        "-t",
                        self.image_name,
                        "-f",
                        dockerfile_path,
                        self.user_project_path,
                    ],
                    "Error building docker image inside minikube cluster.",
                    env=env,
                )

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

    def cleanup(self):
        log_info(f"Deleting minikube profile: {self.minikube_profile}")
        run(
            ["minikube", "delete", "--profile", self.minikube_profile],
            f"Error deleting minikube profile [{self.minikube_profile}]",
        )
        for service in AIRFLOW_SERVICES + MLFLOW_SERVICES + MINIO_SERVICES:
            run(
                ["docker", "network", "disconnect", self.minikube_profile, service],
                f"Error disconnecting network from service: {service}",
            )
        run(
            ["docker", "network", "rm", "-f", "airflow"],
            "Error removing  airflow docker network",
        )
        log_info("Minikube Cleanup complete")
