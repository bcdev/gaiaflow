import json

from kubernetes.client import V1EnvFromSource, V1SecretReference


class XComConfig:
    def __init__(self, task: str, key: str = "return_value"):
        self.task = task
        self.key = key

    def to_dict(self) -> dict:
        return {"task": self.task, "key": self.key}


def build_xcom_templates(xcom_config: dict) -> dict:
    xcom_pull_results = {}

    for arg_key, pull_config in xcom_config.items():
        source_task = pull_config["task"]

        key = "return_value"
        xcom_pull_results[source_task] = (
            "{{ ti.xcom_pull(task_ids='" + source_task + "', key='" + key + "') }}"
        )

    return xcom_pull_results


def inject_params_as_env_vars(params: dict) -> dict:
    return {f"PARAMS_{k.upper()}": f"{{{{ params.{k} }}}}" for k in params}


def build_env_vars(
    func_path: str,
    func_args: list,
    func_kwargs: dict,
    func_args_from_tasks: dict,
    func_kwargs_from_tasks: dict,
    xcom_args_pull_results: dict,
    xcom_kwargs_pull_results: dict,
    custom_env_vars: dict,
    env: str,
) -> dict:
    default_env = {
        "FUNC_PATH": func_path,
        "FUNC_ARGS": json.dumps(func_args),
        "FUNC_KWARGS": json.dumps(func_kwargs),
        "XCOM_PULL_ARGS": json.dumps(func_args_from_tasks),
        "XCOM_PULL_KWARGS": json.dumps(func_kwargs_from_tasks),
        "XCOM_PULL_ARGS_RESULTS": json.dumps(xcom_args_pull_results),
        "XCOM_PULL_KWARGS_RESULTS": json.dumps(xcom_kwargs_pull_results),
        "ENV": env,
    }
    return {**default_env, **custom_env_vars}


def build_env_from_secrets(secrets: list[str]) -> list[V1EnvFromSource]:
    return [
        V1EnvFromSource(secret_ref=V1SecretReference(name=secret)) for secret in secrets
    ]
