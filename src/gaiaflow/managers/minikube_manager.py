import platform
import subprocess
from pathlib import Path
from typing import Any, Literal, Set

from gaiaflow.constants import (
    AIRFLOW_SERVICES,
    MINIO_SERVICES,
    MLFLOW_SERVICES,
    Action,
    BaseAction,
    ExtendedAction,
)
from gaiaflow.managers.base_manager import BaseGaiaflowManager
from gaiaflow.managers.helpers import (
    BaseDockerHandler,
    DockerHelper,
    KubeConfigHelper,
    MinikubeHelper,
    DockerHandlerMode,
)
from gaiaflow.managers.mlops_manager import MlopsManager
from gaiaflow.managers.utils import log_info, run


class MinikubeManager(BaseGaiaflowManager):
    allowed_kwargs = {"secret_name", "secret_data", "dockerfile_path"}

    def __init__(
        self,
        gaiaflow_path: Path,
        user_project_path: Path,
        action: Action,
        force_new: bool = False,
        prune: bool = False,
        docker_handler_mode: DockerHandlerMode = DockerHandlerMode.LOCAL,
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
        handler = BaseDockerHandler.get_docker_handler(
            docker_handler_mode, minikube_helper=self.minikube_helper
        )
        self.docker_helper = DockerHelper(
            image_name=image_name,
            project_path=user_project_path,
            handler=handler,
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
            ExtendedAction.LIST_IMAGES,
            ExtendedAction.REMOVE_IMAGE,
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
                kwargs["dockerfile_path"]
            ),
            ExtendedAction.CREATE_CONFIG: manager.create_kube_config_inline,
            ExtendedAction.CREATE_SECRET: lambda: manager.create_secrets(
                kwargs["secret_name"], kwargs["secret_data"]
            ),
            ExtendedAction.LIST_IMAGES: manager.list_images,
            ExtendedAction.REMOVE_IMAGE: lambda:  manager.remove_image(
                kwargs["image_name"]),
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

    def build_docker_image(self, dockerfile_path: str = ""):
        if dockerfile_path != "":
            dockerfile_path = (
                self.gaiaflow_path / "_docker" / "user-package" / "Dockerfile"
            )
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

    def list_images(self):
        self.docker_helper.list_images()

    def remove_image(self, image_name: str):
        self.docker_helper.remove_image(image_name)