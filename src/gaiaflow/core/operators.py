from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.standard.operators.python import PythonOperator

from .utils import (
    build_env_from_secrets,
    build_env_vars,
    build_xcom_templates,
    inject_params_as_env_vars,
)


class BaseTaskOperator:
    def __init__(
        self,
        task_id,
        func_path,
        func_args,
        func_kwargs,
        func_kwargs_from_tasks,
        func_args_from_tasks,
        image,
        secrets,
        env_vars,
        retries,
        params,
        environment,
    ):
        self.task_id = task_id
        self.func_path = func_path
        self.func_args = func_args
        self.func_kwargs = func_kwargs
        self.func_kwargs_from_tasks = func_kwargs_from_tasks
        self.func_args_from_tasks = func_args_from_tasks
        self.image = image
        self.secrets = secrets
        self.env_vars = env_vars
        self.retries = retries
        self.params = params
        self.environment = environment

    def create_task(self):
        raise NotImplementedError


class DevTaskOperator(BaseTaskOperator):
    def create_task(self):
        from gaiaflow.core.runner import run

        op_kwargs = {
            "func_path": self.func_path,
            "args": self.func_args,
            "kwargs": self.func_kwargs,
            "xcom_pull_kwargs": self.func_kwargs_from_tasks,
            "xcom_pull_args": self.func_args_from_tasks,
        }

        return PythonOperator(
            task_id=self.task_id,
            python_callable=run,
            op_kwargs=op_kwargs,
            do_xcom_push=True,
            retries=self.retries,
            params=self.params,
        )


class ProdLocalTaskOperator(BaseTaskOperator):
    def create_task(self):
        if not self.image:
            raise ValueError("Docker image must be provided for Kubernetes tasks.")

        xcom_kwargs_pull = build_xcom_templates(self.func_kwargs_from_tasks)
        xcom_args_pull = build_xcom_templates(self.func_args_from_tasks)

        env_vars = build_env_vars(
            func_path=self.func_path,
            func_args=self.func_args,
            func_kwargs=self.func_kwargs,
            func_args_from_tasks=self.func_args_from_tasks,
            func_kwargs_from_tasks=self.func_kwargs_from_tasks,
            xcom_args_pull_results=xcom_args_pull,
            xcom_kwargs_pull_results=xcom_kwargs_pull,
            custom_env_vars=self.env_vars,
            env=self.environment.value,
        )

        all_env_vars = {**inject_params_as_env_vars(self.params), **env_vars}
        env_from = build_env_from_secrets(self.secrets or [])

        return KubernetesPodOperator(
            task_id=self.task_id,
            image=self.image,
            cmds=["python", "-m", "gaiaflow.core.runner"],
            env_vars=all_env_vars,
            env_from=env_from,
            get_logs=True,
            is_delete_operator_pod=True,
            log_events_on_failure=True,
            in_cluster=(self.environment == self.environment.PROD),
            do_xcom_push=True,
            retries=self.retries,
            params=self.params,
        )


class ProdTaskOperator(ProdLocalTaskOperator):
    """"""


class DockerTaskOperator(BaseTaskOperator):
    def create_task(self):
        """"""
        # TODO: cont. this.
        return DockerOperator(
            task_id="run_my_test_image",
            image="my-test-image:latest",
            container_name="test_container",
            api_version="auto",
            command=None,
            docker_url="unix://var/run/docker.sock",
            environment={
            "FUNC_PATH": "test.train",
            "FUNC_KWARGS": '{"preprocessed_path": "test/path/"}'
            },
            network_mode="bridge",
            mount_tmp_dir=False,
        )
