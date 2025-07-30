import shutil
import subprocess
import tempfile
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)

@app.command()
def start(env_path: Path = typer.Option(..., "--env",exists=True,  help="Path "
                                                                       "to environment.yml file")):
    print("env_path", env_path)
    env_file = Path(env_path).resolve()
    if not env_file.exists():
        raise FileNotFoundError(f"{env_file} not found")

    with tempfile.TemporaryDirectory() as temp_ctx:
        ctx_path = Path(temp_ctx)
        print("ctx_path", ctx_path)
        script_dir = Path(__file__).parent.resolve()
        docker_dir = script_dir.parent / "docker"
        shutil.copytree(docker_dir , ctx_path / "docker")
        shutil.copy( script_dir.parent / ".env", ctx_path / ".env")

        shutil.copy(env_file, ctx_path / "environment.yml")
        subprocess.run(
            ["docker", "compose", "-f",
             "docker/docker-compose/docker-compose.yml", "up", "--build"],
            cwd=ctx_path,
            check=True
        )
if __name__ == "__main__":
    app()