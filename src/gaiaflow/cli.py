from importlib.metadata import version

import typer
from ruamel.yaml import YAML

from .commands import minikube, mlops

pkg_version = version("gaiaflow")

app = typer.Typer(add_completion=False)

# app.command()(start)
app.add_typer(mlops.app, name="dev", help="Manage Gaiaflow development services.")
app.add_typer(
    minikube.app,
    name="prod-local",
    help="Manage Gaiaflow production-like services. Start this once "
    "you have developed your package and tested your workflow in the dev mode.",
)
# app.command(name="start")(start)
#
# def update_files(ctx_path, abs_proj_path):
#     yaml = YAML()
#     yaml.preserve_quotes = True
#
#     # ctx_path = Path(__file__).parent.parent.resolve()
#     print("ctx_path", ctx_path)
#     compose_path = ctx_path / "docker" / "docker-compose" / "docker-compose.yml"
#     print("compose_path", compose_path)
#
#     with open(compose_path) as f:
#         compose_data = yaml.load(f)
#
#     env_file = ctx_path / "environment.yml"
#
#     def get_env_name_from_yml(env_file: Path) -> str:
#         with open(env_file, "r") as f:
#             env_yaml = yaml.load(f)
#         return env_yaml.get("name")
#
#     env_name = get_env_name_from_yml(env_file)
#     print(env_name)
#
#     x_common = compose_data.get("x-airflow-common", {})
#     original_vols = x_common.get("volumes", [])
#     new_volumes = []
#     print("original_vols", original_vols)
#     for vol in original_vols:
#         parts = vol.split(":", 1)
#         if len(parts) == 2:
#             src, dst = parts
#             src_path = (abs_proj_path / Path(src).name).resolve()
#             print("src_path", src_path)
#             new_volumes.append(f"{src_path}:{dst}")
#
#     existing_mounts = {Path(v.split(":", 1)[0]).name for v in new_volumes}
#     python_packages = find_python_packages(abs_proj_path)
#
#     for child in abs_proj_path.iterdir():
#         if (
#             child.is_dir() and child.name not in existing_mounts and child.name
#         ) in python_packages:
#             dst_path = f"/opt/airflow/{child.name}"
#             new_volumes.append(f"{child.resolve()}:{dst_path}")
#
#     compose_data["x-airflow-common"]["volumes"] = new_volumes
#
#     result = [f"/opt/airflow/{item}" for item in python_packages]
#     pythonpath_entry = ":".join(result)
#     print("python_packages", python_packages, pythonpath_entry)
#     env_updates = {
#         "PYTHONPATH": f"{pythonpath_entry}:/opt/airflow/dags:${{PYTHONPATH}}",
#         "PATH": f"/home/airflow/.local/share/mamba/envs/{env_name}/bin:/usr/bin:/bin:${{PATH}}",
#         "LD_LIBRARY_PATH": f"/home/airflow/.local/share/mamba/envs/{env_name}/lib:/lib/x86_64-linux-gnu:${{LD_LIBRARY_PATH}}",
#     }
#
#     compose_data["x-airflow-common"]["environment"].update(env_updates)
#
#     with compose_path.open("w") as f:
#         yaml.dump(compose_data, f)
#
#
# @app.command()
# def start(
#     project_path: Path = typer.Option(
#         ..., "--path", exists=True, help="Path to your project"
#     ),
# ):
#     print("env_path", project_path)
#     abs_proj_path = Path(project_path).resolve()
#     print("env_path after resolving", abs_proj_path)
#     if not abs_proj_path.exists():
#         raise FileNotFoundError(f"{abs_proj_path} not found")
#     version = get_gaialfow_version()
#     temp_pth = f"/tmp/gaiaflow-{version}"
#     ctx_path = Path(temp_pth)
#     os.makedirs(ctx_path, exist_ok=True)
#     print("ctx_path", ctx_path)
#     script_dir = Path(__file__).parent.resolve()
#     docker_dir = script_dir.parent / "docker"
#     shutil.copytree(docker_dir, ctx_path / "docker", dirs_exist_ok=True)
#     shutil.copy(script_dir.parent / ".env", ctx_path / ".env")
#     shutil.copy(abs_proj_path / "environment.yml", ctx_path / "environment.yml")
#     update_files(ctx_path, abs_proj_path)
#     # subprocess.run(
#     #     ["docker", "compose", "-f",
#     #      "docker/docker-compose/docker-compose.yml", "up", "--build"],
#     #     cwd=ctx_path,
#     #     check=True
#     # )


if __name__ == "__main__":
    app()
