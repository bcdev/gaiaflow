import json

from airflow.providers.cncf.kubernetes.operators.pod import \
    KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator
from kubernetes.client import V1EnvFromSource, V1SecretReference


class Environment(Enum):
    DEV = "dev"
    PROD_LOCAL = "prod_local"
    PROD = "prod"


TASK_REGISTRY = {
    Environment.DEV: _create_python_task,
    Environment.PROD: _create_kubernetes_task,
    Environment.PROD_LOCAL: _create_kubernetes_task,
}

class XComConfig:
    def __init__(self, task: str, key: str = "return_value"):
        self.task = task
        self.key = key

    def to_dict(self) -> dict:
        return {"task": self.task, "key": self.key}

def create_task(
        task_id: str,
        func_path: str,
        func_kwargs: dict = None,
        image: str = None,
        env: str = "dev",
        func_kwargs_from_tasks: dict = None,
        secrets: list = None,
        env_vars: dict = None,
        retries: int = 3,
        **operator_kwargs
):
    """
    Create an Airflow task that can run in different environments.

    Args:
        task_id: Unique task identifier
        func_path: Python import path to the function (e.g.,'my.module:myfunction')
        func_args: Static positional arguments to pass to the function
        func_kwargs: Static keyword arguments to pass to the function
        image: Docker image for production and prod-like environments
        env: Environment to run in ('dev', 'prod_local', 'prod')
        func_args_from_tasks: Dynamic positional arguments from other tasks via XCom (ordered list)
        func_kwargs_from_tasks: Dynamic keyword arguments from other tasks via XCom
        secrets: List of Kubernetes secrets to mount
        env_vars: Environment variables for the task for production and prod-like environments
        retries: Number of retries on failure
        **operator_kwargs: Additional arguments passed to the underlying operator
    """

    try:
        environment = Environment(env)
    except ValueError:
        raise ValueError(
            f"env must be one of {[e.value for e in Environment]}, got '{env}'"
        )

    if func_kwargs is None:
        func_kwargs = {}

    if func_kwargs is None:
        func_kwargs = {}

    if env_vars is None:
        env_vars = {}

    full_kwargs = {
        "func_path": func_path,
        "kwargs": func_kwargs,
    }



    if func_kwargs_from_tasks_dict:
        func_kwargs_from_tasks_dict = {
            k: (v.to_dict() if isinstance(v, XComConfig) else XComConfig(v).to_dict())
            for k, v in func_kwargs_from_tasks.items()
        }
        # full_kwargs["xcom_pull_tasks"] = func_kwargs_from_tasks_dict
    else:
        func_kwargs_from_tasks_dict = {}

    if environment == Environment.DEV:
        return _create_python_task(
            task_id=task_id,
            func_path=func_path,
            func_args=func_args,
            func_kwargs=func_kwargs,
            func_args_from_tasks=func_args_from_tasks_list,
            func_kwargs_from_tasks=func_kwargs_from_tasks_dict,
            xcom_push=xcom_push,
            retries=retries,
            **operator_kwargs,
        )

    elif environment in [Environment.PROD, Environment.PROD_LOCAL]:
        if not image:
            raise ValueError(f"Docker image is required for {env} environment")

        return _create_kubernetes_task(
            task_id=task_id,
            func_path=func_path,
            func_args=func_args,
            func_kwargs=func_kwargs,
            func_args_from_tasks=func_args_from_tasks_list,
            func_kwargs_from_tasks=func_kwargs_from_tasks_dict,
            image=image,
            secrets=secrets,
            env_vars=env_vars,
            xcom_push=xcom_push,
            retries=retries,
            in_cluster=(environment == Environment.PROD),
            **operator_kwargs,
        )

    # if env == "dev":
    #     from .runner import run
    #     return PythonOperator(
    #         task_id=task_id,
    #         python_callable=run,
    #         op_kwargs=full_kwargs,
    #         do_xcom_push=xcom_push,
    #         retries=retries,
    #     )
    #
    # elif env == "prod" or env == "prod_local":
    #     if not image:
    #         raise ValueError(f"Docker image expected when in {env} mode")
    #     if env == "prod_local":
    #         in_cluster = False
    #     else:
    #         in_cluster = True
    #     if secrets:
    #         env_from = [V1EnvFromSource(secret_ref=V1SecretReference(
    #             name=secret)) for secret in secrets]
    #     else:
    #         env_from = None
    #
    #     xcom_pull_results = {}
    #
    #     for arg_key, pull_config in (func_kwargs_from_tasks or {}).items():
    #         source_task = pull_config["task"]
    #         key = pull_config.get("key", "return_value")
    #         xcom_pull_results[source_task] = (
    #
    #                 "{{ ti.xcom_pull(task_ids='" + source_task + "', key='" + key + "') }}"
    #
    #         )
    #
    #     default_env_vars = {
    #         "FUNC_PATH": func_path,
    #         "FUNC_KWARGS": json.dumps(func_kwargs),
    #         "XCOM_PULL_TASKS": json.dumps(func_kwargs_from_tasks or {}),
    #         "XCOM_PULL_RESULTS": json.dumps(xcom_pull_results),
    #         "ENV": "prod",
    #     }
    #
    #     if env_vars:
    #         env_vars.update(default_env_vars)
    #
    #     return KubernetesPodOperator(
    #         task_id=task_id,
    #         name=task_id,
    #         image=image,
    #         cmds=["python", "-m", "tech_talk.runner"],
    #         env_vars=env_vars,
    #         env_from=env_from,
    #         get_logs=True,
    #         is_delete_operator_pod=True,
    #         log_events_on_failure=True,
    #         in_cluster=in_cluster,
    #         do_xcom_push=xcom_push,
    #         retries=retries
    #     )
    #
    # else:
    #     raise ValueError(f"env can only be dev, prod_local or prod, but got"
    #                      f" {env}")


def _create_python_task(
        task_id: str,
        func_path: str,
        func_args: list,
        func_kwargs: dict,
        func_args_from_tasks: list,
        func_kwargs_from_tasks: dict,
        xcom_push: bool,
        retries: int,
        **operator_kwargs
) -> PythonOperator:
    from .runner import run

    full_kwargs = {
        "func_path": func_path,
        "args": func_args,
        "kwargs": func_kwargs,
    }

    if func_args_from_tasks:
        full_kwargs["xcom_pull_args"] = func_args_from_tasks

    if func_kwargs_from_tasks:
        full_kwargs["xcom_pull_tasks"] = func_kwargs_from_tasks

    return PythonOperator(
        task_id=task_id,
        python_callable=run,
        op_kwargs=full_kwargs,
        do_xcom_push=xcom_push,
        retries=retries,
        **operator_kwargs
    )


def _create_kubernetes_task(
        task_id: str,
        func_path: str,
        func_args: list,
        func_kwargs: dict,
        func_args_from_tasks: list,
        func_kwargs_from_tasks: dict,
        image: str,
        secrets: Optional[List[str]],
        env_vars: dict,
        xcom_push: bool,
        retries: int,
        in_cluster: bool,
        **operator_kwargs
) -> KubernetesPodOperator:

    xcom_pull_results = _build_xcom_templates(func_args_from_tasks, func_kwargs_from_tasks)

    task_env_vars = _build_env_vars(
        func_path=func_path,
        func_args=func_args,
        func_kwargs=func_kwargs,
        func_args_from_tasks=func_args_from_tasks,
        func_kwargs_from_tasks=func_kwargs_from_tasks,
        xcom_pull_results=xcom_pull_results,
        custom_env_vars=env_vars
    )

    env_from = _build_env_from_secrets(secrets) if secrets else None

    return KubernetesPodOperator(
        task_id=task_id,
        name=task_id,
        image=image,
        cmds=["python", "-m", "tech_talk.runner"],
        env_vars=task_env_vars,
        env_from=env_from,
        get_logs=True,
        is_delete_operator_pod=True,
        log_events_on_failure=True,
        in_cluster=in_cluster,
        do_xcom_push=xcom_push,
        retries=retries,
        **operator_kwargs
    )


def _build_xcom_templates(func_kwargs_from_tasks: dict) -> dict:
    xcom_pull_results = {}

    for arg_key, pull_config in func_kwargs_from_tasks.items():
        source_task = pull_config["task"]
        key = pull_config.get("key", "return_value")
        xcom_pull_results[source_task] = (
                "{{ ti.xcom_pull(task_ids='" + source_task + "', key='" + key + "') }}"
        )

    return xcom_pull_results


def _build_env_vars(
        func_path: str,
        func_kwargs: dict,
        func_kwargs_from_tasks: dict,
        xcom_pull_results: dict,
        custom_env_vars: dict
) -> dict:
    default_env_vars = {
        "FUNC_PATH": func_path,
        "FUNC_KWARGS": json.dumps(func_kwargs),
        "XCOM_PULL_TASKS": json.dumps(func_kwargs_from_tasks),
        "XCOM_PULL_RESULTS": json.dumps(xcom_pull_results),
        "ENV": "prod",
    }

    final_env_vars = {**default_env_vars, **custom_env_vars}
    return final_env_vars


def _build_env_from_secrets(secrets: List[str]) -> List[V1EnvFromSource]:
    return [
        V1EnvFromSource(secret_ref=V1SecretReference(name=secret))
        for secret in secrets
    ]