import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import fsspec
import typer

from gaiaflow.constants import GAIAFLOW_STATE_FILE

fs = fsspec.filesystem("file")


def get_gaialfow_version() -> str:
    try:
        from importlib.metadata import version

        return version("gaiaflow")
    except Exception:
        print("Package not installed. Getting version from the pyproject.toml")
        import tomllib

        pyproject = tomllib.loads(Path("pyproject.toml").read_text())
        return pyproject["project"]["version"]


def find_python_packages(base_path: Path):
    outer_packages = []

    for child in base_path.iterdir():
        if child.is_dir() and (child / "__init__.py").exists():
            outer_packages.append(child.name)

    return outer_packages


def log_info(message: str):
    print(f"\033[0;34m[{datetime.now().strftime('%H:%M:%S')}]\033[0m {message}")


def log_error(message: str):
    print(f"\033[0;31mERROR:\033[0m {message}", file=sys.stderr)


def run(command: list, error_message: str, env=None):
    try:
        subprocess.call(command, env=env)
    except Exception:
        log_info(error_message)
        raise


def handle_error(message: str):
    log_error(f"Error: {message}")
    sys.exit(1)


def get_state_file() -> Path:
    return GAIAFLOW_STATE_FILE

def save_project_state(project_path: Path, gaiaflow_path: Path):
    state_file = get_state_file()
    try:
        if state_file.exists():
            with state_file.open("r") as f:
                state = json.load(f)
        else:
            state = {}
    except (json.JSONDecodeError, FileNotFoundError):
         state = {}

    project_path_str = str(project_path)
    gaiaflow_path_str = str(gaiaflow_path)
    keys_to_delete = [
        k
        for k, v in state.items()
        if v.get("project_path") == project_path_str and k != gaiaflow_path_str
    ]
    for k in keys_to_delete:
        del state[k]

    state[gaiaflow_path_str] = {
        "project_path": project_path_str,
    }

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def load_project_state() -> dict | None:
    state_file = get_state_file()
    print("state_file", state_file)
    if not state_file.exists():
        return None

    try:
        with open(state_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def gaiaflow_path_exists_in_state(gaiaflow_path: Path, check_fs: bool = True) -> bool:
    state = load_project_state()
    if not state:
        return False

    key = str(gaiaflow_path)
    if key not in state:
        return False

    if check_fs and not gaiaflow_path.exists():
        typer.echo(
            f"Gaiaflow path exists in state but not on disk: {gaiaflow_path}", err=True
        )
        return False

    return True


def delete_project_state(gaiaflow_path: Path):
    state_file = get_state_file()
    print("state_file", state_file)
    if not state_file.exists():
        log_error(
            "State file not found at ~/.gaiaflow/state.json. Please run the services."
        )
        return

    try:
        with open(state_file, "r") as f:
            state = json.load(f)

        print("found!", state.get("gaiaflow_path"), state)
        key = str(gaiaflow_path)
        if key in state:
            del state[key]
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        raise


def parse_key_value_pairs(pairs: list[str]) -> dict:
    data = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"Invalid format: '{pair}'. Expected key=value.")
        key, value = pair.split("=", 1)
        data[key] = value
    return data


def create_directory(dir_name):
    if not fs.exists(dir_name):
        try:
            fs.makedirs(dir_name, exist_ok=True)
            log_info(f"Created directory: {dir_name}")
        except Exception as e:
            handle_error(f"Failed to create {dir_name} directory: {e}")
    else:
        log_info(f"Directory {dir_name} already exists")

    set_permissions(dir_name)

def set_permissions(path, mode=0o777):
    try:
        fs.chmod(path, mode)
        log_info(f"Set permissions for {path}")
    except Exception:
        log_info(f"Warning: Could not set permissions for {path}")


def create_gaiaflow_context_path(project_path: Path) -> tuple[Path, Path]:
    user_project_path = Path(project_path).resolve()
    if not user_project_path.exists():
        raise FileNotFoundError(f"{user_project_path} not found")
    version = get_gaialfow_version()
    project_name = str(user_project_path).split("/")[-1]
    gaiaflow_path = Path(f"/tmp/gaiaflow-{version}-{project_name}")

    return gaiaflow_path, user_project_path
