# !!PLEASE DO NOT EDIT/DELETE THIS!!
# This file is the main entry point to your package when using Airflow to
# run your tasks from your DAGs called from the task_factory.
# It imports the required function from your package and executes it with the
# arguments provided

import ast
import json
import os
import pickle
from typing import Any

from airflow.models.taskinstance import TaskInstance
from airflow.utils.context import Context


def _extract_params_from_env(prefix="PARAMS_") -> dict[str, str]:
    return {
        k[len(prefix) :].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


def run(
    func_path: str | None = None,
    args: list | None = None,
    kwargs: dict[str, str] | None = None,
    xcom_pull_kwargs: dict | None = None,
    xcom_pull_args: dict | None = None,
    **context: Context,
) -> dict[str, str]:
    env = os.environ.get("ENV", "dev")
    print(f"## Runner running in {env} mode ##")

    if env == "dev":
        print("args", args)
        print("kwargs", kwargs)
        print("xcom_pull_args", xcom_pull_args)
        print("xcom_pull_kwargs", xcom_pull_kwargs)
        kwargs["params"] = context.get("params", {})
        ti: TaskInstance = context.get("ti")
        if ti and xcom_pull_kwargs:
            for arg_key, pull_config in xcom_pull_kwargs.items():
                source_task = pull_config["task"]
                key = pull_config.get("key", "return_value")
                pulled_val = ti.xcom_pull(task_ids=source_task, key=key)
                kwargs[arg_key] = (
                    pulled_val
                    if not isinstance(pulled_val, dict)
                    else pulled_val.get(arg_key)
                )
        print(f"[XCom] [dev] Pulled kwargs {kwargs}")
        if ti and xcom_pull_args:
            for index_str, pull_config in sorted(
                xcom_pull_args.items(), key=lambda x: int(x[0])
            ):
                index = int(index_str)
                source_task = pull_config["task"]
                pulled_val = ti.xcom_pull(task_ids=source_task, key="return_value").get(
                    pull_config["key"]
                )
                if len(args) <= index:
                    args.extend([None] * (index - len(args)))
                args.insert(index, pulled_val)
        print(f"[XCom] Pulled args: {args}")
    else:
        func_path = os.environ.get("FUNC_PATH", "")
        args = json.loads(os.environ.get("FUNC_ARGS", "{}"))
        kwargs = json.loads(os.environ.get("FUNC_KWARGS", "{}"))
        xcom_pull_args = json.loads(os.environ.get("XCOM_PULL_ARGS", "{}"))
        xcom_pull_kwargs = json.loads(os.environ.get("XCOM_PULL_KWARGS", "{}"))
        xcom_pull_args_results = json.loads(
            os.environ.get("XCOM_PULL_ARGS_RESULTS", "{}")
        )
        xcom_pull_kwargs_results = json.loads(
            os.environ.get("XCOM_PULL_KWARGS_RESULTS", "{}")
        )
        print("args", args)
        print("kwargs", kwargs)
        print("xcom_pull_args", xcom_pull_args)
        print("xcom_pull_kwargs", xcom_pull_kwargs)
        print(f"[XCom] [prod] Pulled args from env: {xcom_pull_args_results}")
        print(f"[XCom] [prod] Pulled kwargs from env: {xcom_pull_kwargs_results}")
        params = _extract_params_from_env()
        kwargs["params"] = params
        print("Params passed in kwargs['params']", kwargs["params"])

        if xcom_pull_args:
            for index_str, pull_config in sorted(
                xcom_pull_args.items(), key=lambda x: int(x[0])
            ):
                index = int(index_str)
                task_name = pull_config["task"]
                pulled_val = xcom_pull_args_results.get(task_name, {})
                if pulled_val:
                    try:
                        pulled_val = ast.literal_eval(pulled_val)
                        args.insert(index, pulled_val.get(pull_config["key"]))
                        print("Pulled val in args::", pulled_val)
                    except Exception as e:
                        print(
                            f"[XCom] [prod] Failed to parse XCOM for {index_str}: {e}"
                        )

        if xcom_pull_kwargs:
            for arg_key, pull_config in xcom_pull_kwargs.items():
                pulled_val = xcom_pull_kwargs_results.get(pull_config["task"])
                if pulled_val:
                    try:
                        pulled_val = ast.literal_eval(pulled_val)
                        if isinstance(pulled_val, dict):
                            kwargs[arg_key] = pulled_val.get(arg_key)
                        else:
                            kwargs[arg_key] = pulled_val
                    except Exception as e:
                        print(f"[XCom] [prod] Failed to parse XCOM for {arg_key}: {e}")

        module_path, func_name = func_path.rsplit(":", 1)
    import importlib
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)

    print(f"Running {func_path} with args: {args} and kwargs :{kwargs}")
    result = func(*args, **kwargs)
    print("Function result:", result)
    if os.environ.get("ENV") == "prod" or os.environ.get("ENV") == "prod_local":
        # This is needed when we use KubernetesPodOperator and want to
        # share information via XCOM.
        _write_xcom_result(result)
    if os.environ.get("ENV") == "dev_docker":
        with open("/tmp/script.out", "wb+") as tmp:
            pickle.dump(result, tmp)
    return result


def _write_xcom_result(result: Any) -> None:
    try:
        xcom_dir = "/airflow/xcom"
        os.makedirs(xcom_dir, exist_ok=True)

        with open(f"{xcom_dir}/return.json", "w") as f:
            json.dump(result, f)

        print("Result written to XCom successfully")
    except Exception as e:
        print(f"Failed to write XCom result: {e}")
        raise


if __name__ == "__main__":
    run()
