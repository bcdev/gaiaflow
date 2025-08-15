import os
import subprocess
import uuid
from contextlib import contextmanager
from typing import Generator, Callable

import mlflow

import docker
from gaiaflow.constants import (
    DEFAULT_MINIO_AWS_ACCESS_KEY_ID,
    DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY,
    BaseAction,
)
from gaiaflow.managers.base_manager import BaseGaiaflowManager


class MlflowModelManager(BaseGaiaflowManager):
    def __init__(
        self,
        registry_uri=None,
        action: BaseAction = None,
        force_new: bool = False,
        prune: bool = False,
        local: bool = False,
        **kwargs,
    ):
        self.docker_client = docker.from_env()
        self.registry_uri = registry_uri.rstrip("/") if registry_uri else None
        self.local = local

        # TODO: not optimal. Use ContextManager to restore the env vars
        #  Move them to the actual methods where they are needed.
        os.environ["MLFLOW_TRACKING_URI"] = (
            os.getenv("MLFLOW_TRACKING_URI") or "https://localhost:5000"
        )
        os.environ["MLFLOW_S3_ENDPOINT_URL"] = (
            os.getenv("MLFLOW_S3_ENDPOINT_URL") or "https://localhost:9000"
        )
        os.environ["AWS_ACCESS_KEY_ID"] = (
            os.getenv("AWS_ACCESS_KEY_ID") or DEFAULT_MINIO_AWS_ACCESS_KEY_ID
        )
        os.environ["AWS_SECRET_ACCESS_KEY"] = (
            os.getenv("AWS_SECRET_ACCESS_KEY") or DEFAULT_MINIO_AWS_SECRET_ACCESS_KEY
        )

        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI"))

        # This Manager does not need the paths. But it expects that either
        # the model exists in S3 if s3_uri is used or a live instance of MLFlow
        # running if run_id is used
        super().__init__(
            gaiaflow_path="",
            user_project_path="",
            action=action,
            force_new=force_new,
            prune=prune,
            **kwargs,
        )

    def _get_model_uri(self, model_uri=None, run_id=None):
        if model_uri:
            return model_uri
        elif run_id:
            return f"runs:/{run_id}/model"
        else:
            raise ValueError("Either model_uri or run_id must be provided.")

    # TODO: Use this instead
    # @classmethod
    # def run(cls, action, **kwargs):
    #     params = kwargs.get("params", {})
    #     model_uri = params.get("model_uri")
    #     run_id = params.get("run_id")
    #     image_name = params.get("image_name")
    #     enable_mlserver = params.get("enable_mlserver", True)
    #     manag = MlflowModelManager(model_uri, run_id, image_name,
    #                               enable_mlserver)
    #     environment = create_env()
    #     with set_env_cm(environment):
    #         if action == BaseAction.START:
    #             manag.start()



    def start(self, **kwargs):
        print("kwargs inside start, **kwargs", kwargs)
        params = kwargs.get("params", {})

        model_uri = params.get("model_uri")
        run_id = params.get("run_id")
        image_name = params.get("image_name")
        enable_mlserver = params.get("enable_mlserver", True)

        self.build_model_docker_image(model_uri, run_id, image_name, enable_mlserver)
        self.run_container(image_name)

    def stop(self, **kwargs):
        print("kwargs inside stop, **kwargs", kwargs)
        params = kwargs.get("params", {})

        container_id_or_name = params.get("container_id_or_name")
        self.stop_and_remove_container(container_id_or_name)

    def cleanup(self, **kwargs):
        print("kwargs inside cleanup, **kwargs", kwargs)
        params = kwargs.get("params", {})

        container_id_or_name = params.get("container_id_or_name")
        purge = params.get("purge")
        self.stop_and_remove_container(container_id_or_name, purge)

    def build_model_docker_image(
        self, model_uri=None, run_id=None, image_name=None, enable_mlserver=True
    ):
        model_uri_final = self._get_model_uri(model_uri, run_id)

        unique_tag = str(uuid.uuid4())[:8]
        image_name = image_name or f"mlflow-model:{unique_tag}"

        full_image_name = (
            f"{self.registry_uri}/{image_name}" if self.registry_uri else image_name
        )

        print(f"Building Docker image from {model_uri_final} as {full_image_name}...")

        mlflow.models.build_docker(
            model_uri=model_uri_final,
            name=full_image_name,
            enable_mlserver=enable_mlserver,
        )

        return full_image_name

    def run_container(self, image_name, port=8246):
        container = self.docker_client.containers.run(
            image_name,
            detach=True,
            ports={"8080/tcp": port},
            name=f"mlflow_model_{uuid.uuid4().hex[:6]}",
        )
        print(f"Container started: {container.name} on port {port}")
        return container

    def stop_and_remove_container(self, container_id_or_name, purge=False):
        try:
            container = self.docker_client.containers.get(container_id_or_name)
            print(f"Stopping container: {container.name}")
            container.stop()
            container.remove()
            print("Container stopped and removed.")
            if purge:
                image_name = container.image.tags[0]
                self.docker_client.images.remove(image=image_name, force=True)
                print(f"Image {image_name} removed.")
        except docker.context.api.errors.NotFound:
            print("Container not found.")

    def push_image_to_registry(self, image_name):
        if not self.registry_uri:
            raise ValueError("No registry_uri provided.")
        print(f"Pushing image {image_name} to registry {self.registry_uri}...")
        subprocess.run(["docker", "push", image_name], check=True)
        print("Image pushed.")

    def generate_k8s_yaml(self):
        print(" Generating Kubernetes deployment YAML...")
        raise NotImplementedError()

    def deploy_to_kubernetes(self, k8s_yaml_path):
        print(f"Deploying to Kubernetes from {k8s_yaml_path}...")
        subprocess.run(["kubectl", "apply", "-f", k8s_yaml_path], check=True)
        print("Deployment applied.")

#
# @contextmanager
# def set_env_cm(**new_env: str | None) -> Generator[dict[str, str | None]]:
#     """Run the code in the block with a new environment `new_env`."""
#     restore_env = set_env(**new_env)
#     try:
#         yield new_env
#     finally:
#         restore_env()
#
#
# def set_env(**new_env: str | None) -> Callable[[], None]:
#     """
#     Set the new environment in `new_env` and return a no-arg
#     function to restore the old environment.
#     """
#     old_env = {k: os.environ.get(k) for k in new_env.keys()}
#
#     def restore_env():
#         for ko, vo in old_env.items():
#             if vo is not None:
#                 os.environ[ko] = vo
#             elif ko in os.environ:
#                 del os.environ[ko]
#
#     for kn, vn in new_env.items():
#         if vn is not None:
#             os.environ[kn] = vn
#         elif kn in os.environ:
#             del os.environ[kn]
#
#     return restore_env


