import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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


def log(message: str):
    print(f"\033[0;34m[{datetime.now().strftime('%H:%M:%S')}]\033[0m {message}")


def error(message: str):
    print(f"\033[0;31mERROR:\033[0m {message}", file=sys.stderr)


def run(command: list, error_message: str):
    try:
        subprocess.call(command)
    except Exception:
        log(error_message)
        raise


def handle_error(message: str):
    error(f"Error: {message}")
    sys.exit(1)


def get_state_file() -> Path:
    """Get the path to the state file."""
    config_dir = Path.home() / ".gaiaflow"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "state.json"


def save_project_state(project_path: Path, gaiaflow_path: Path):
    """Save the current project state."""
    state_file = get_state_file()
    state = {
        "project_path": str(project_path),
        "gaiaflow_path": str(gaiaflow_path),
        "gaiaflow_version": get_gaialfow_version(),
    }
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def load_project_state() -> dict | None:
    """Load the current project state."""
    state_file = get_state_file()
    if not state_file.exists():
        return None

    try:
        with open(state_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def get_gaiaflow_path() -> Path:
    """Get the gaiaflow path from state or raise error."""
    state = load_project_state()
    if not state:
        typer.echo(
            "No active Gaiaflow project found. Please run 'start' first.", err=True
        )
        raise typer.Exit(1)

    gaiaflow_path = Path(state["gaiaflow_path"])
    print(gaiaflow_path)
    if not gaiaflow_path.exists():
        typer.echo(f"Gaiaflow installation not found at {gaiaflow_path}", err=True)
        raise typer.Exit(1)

    return gaiaflow_path

def parse_key_value_pairs(pairs: list[str]) -> dict:
    data = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"Invalid format: '{pair}'. Expected key=value.")
        key, value = pair.split("=", 1)
        data[key] = value
    return data
