import os
import platform
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Set, Literal

import yaml

from gaiaflow.constants import (
    AIRFLOW_SERVICES,
    MINIO_SERVICES,
    MLFLOW_SERVICES,
    Action,
    BaseAction,
    ExtendedAction,
)
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.managers.mlops_manager import MlopsManager
from gaiaflow.managers.utils import (
    find_python_packages,
    is_wsl,
    log_error,
    log_info,
    run,
    set_permissions,
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


class BaseDockerHandler:
    """Abstract docker handler with optional hooks."""

    @classmethod
    def get_docker_handler(cls, mode: str, **kwargs):
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

    def prune_images(self):
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
            ["docker", "build", "-t", image_name, "-f", str(dockerfile_path), str(project_path)],
            "Error building Docker image locally",
        )

    def list_images(self):
        run(["docker", "image", "ls"], "Error listing Docker images locally")

    def remove_image(self, image_name: str):
        run(["docker", "rmi", "-f", image_name], f"Error removing Docker image {image_name} "
                                                 "locally")

    def prune_images(self):
        run(["docker", "image", "prune", "-f"], "Error pruning Docker images "
                                                "locally")

class MinikubeDockerHandler(BaseDockerHandler):
    def __init__(self, minikube_helper: MinikubeHelper):
        self.minikube_helper = minikube_helper
        self.env = self._get_minikube_env()

    def build(self, image_name: str, dockerfile_path: Path, project_path: Path):
        log_info(f"Building Docker image [{image_name}] in Minikube context")
        run(
            ["docker", "build", "-t", image_name, "-f", str(dockerfile_path), str(project_path)],
            "Error building Docker image inside Minikube",
            env=self.env,
        )

    def list_images(self):
        run(["docker", "image", "ls"],"Error listing Docker images inside Minikube", env=self.env)

    def remove_image(self, image_name: str):
        run(["docker", "rmi", "-f", image_name], f"Error removing Docker image {image_name} "
                                                 "inside Minikube", env=self.env)

    def prune_images(self):
        run(["docker", "image", "prune", "-f"], "Error pruning Docker images "
                                                "inside Minikube", env=self.env)

    def _get_minikube_env(self):
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
    "local": LocalDockerHandler,
    "minikube": MinikubeDockerHandler,
    "local-user": LocalUserCustomImageDockerHandler,
    "minikube-user": MinikubeUserCustomImageDockerHandler
}

class DockerHelper:
    def __init__(
        self,
        image_name: str,
        project_path: Path,
        builder: BaseDockerHandler
    ):
        self.image_name = image_name
        self.project_path = project_path
        self.builder = builder

    def build_image(self, dockerfile_path: Path):
        if not dockerfile_path.exists():
            log_error(f"Dockerfile not found at {dockerfile_path}")
            return

        pre_build_ctx = self.builder.pre_build(
            self.image_name, dockerfile_path, self.project_path
        )
        if pre_build_ctx:
            with pre_build_ctx:
                self.builder.build(self.image_name, dockerfile_path, self.project_path)
        else:
            self.builder.build(self.image_name, dockerfile_path, self.project_path)

        self.builder.post_build(self.image_name, dockerfile_path, self.project_path)

    def list_images(self):
        self.builder.list_images()

    def remove_image(self, image_name: str):
        self.builder.remove_image(image_name)

    def prune_images(self):
        self.builder.prune_images()


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


class MinikubeManager(BaseGaiaflowManager):
    allowed_kwargs = {"secret_name", "secret_data", "dockerfile_path"}
    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: Action,
        force_new: bool = False,
        prune: bool = False,
        docker_build_mode: Literal["local", "minikube"] = "local",
        image_name: str = "",
        **kwargs,
    ):
        if kwargs:
            for key in kwargs:
                if key not in self.allowed_kwargs:
                    raise TypeError(f"Unexpected keyword argument: {key}")

        self.minikube_profile = "airflow"
        # TODO: get the docker image name automatically
        #  For CI, get the package name, version and create repository. See
        #  in test-airflow-ci test_ecr_push.yml
        self.os_type = platform.system().lower()
        self.image_name = image_name

        self.minikube_helper = MinikubeHelper()
        builder = BaseDockerHandler.get_docker_builder(docker_build_mode,
                                                       minikube_helper=self.minikube_helper)
        self.docker_helper = DockerHelper(
            image_name=image_name,
            project_path=user_project_path,
            builder=builder,
        )
        self.kube_helper = KubeConfigHelper(
            gaiaflow_path=gaiaflow_path, os_type=self.os_type
        )

        super().__init__(
            gaiaflow_path=gaiaflow_path,
            user_project_path=user_project_path,
            action=action,
            force_new=force_new,
            prune=prune,
        )

    def _get_valid_actions(self) -> Set[Action]:
        return super()._get_valid_actions() | {
            ExtendedAction.DOCKERIZE,
            ExtendedAction.CREATE_CONFIG,
            ExtendedAction.CREATE_SECRET,
        }

    @classmethod
    def run(cls, **kwargs):
        action = kwargs.get("action", None)
        if action is None:
            raise ValueError("Missing required argument 'action'")

        manager = cls(**kwargs)

        action_map = {
            BaseAction.START: manager.start,
            BaseAction.STOP: manager.stop,
            BaseAction.RESTART: manager.restart,
            BaseAction.CLEANUP: manager.cleanup,
            ExtendedAction.DOCKERIZE: lambda: manager.build_docker_image(
                kwargs["dockerfile_path"]),
            ExtendedAction.CREATE_CONFIG: manager.create_kube_config_inline,
            ExtendedAction.CREATE_SECRET: lambda: manager.create_secrets(
                kwargs["secret_name"], kwargs["secret_data"]
            ),
        }

        try:
            action_map[action]()
        except KeyError:
            raise ValueError(f"Unknown action: {action}")

    def _stop_mlops(self):
        MlopsManager.run(
            gaiaflow_path=self.gaiaflow_path,
            user_project_path=self.user_project_path,
            action=BaseAction.STOP,
        )

    def _start_mlops(self):
        MlopsManager.run(
            gaiaflow_path=self.gaiaflow_path,
            user_project_path=self.user_project_path,
            action=BaseAction.START,
            prod_local=True,
            force_new=self.force_new,
        )

    def start(self):
        if self.force_new:
            self.cleanup()
        self._stop_mlops()
        self.minikube_helper.start()
        self.create_kube_config_inline()
        self._start_mlops()

    def stop(self):
        self.minikube_helper.stop()

    def create_kube_config_inline(self):
        self.kube_helper.create_inline()

    def build_docker_image(self, dockerfile_path: str):
        if not dockerfile_path:
            dockerfile_path = self.gaiaflow_path / "_docker" / "user-package" / "Dockerfile"
        self.docker_helper.build_image(dockerfile_path)

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
