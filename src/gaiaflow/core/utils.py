import re
import subprocess

from kubernetes.client import V1EnvFromSource, V1SecretReference


def inject_params_as_env_vars(params: dict) -> dict:
    return {f"PARAMS_{k.upper()}": f"{{{{ params.{k} }}}}" for k in params}


def build_env_from_secrets(secrets: list[str]) -> list[V1EnvFromSource]:
    return [
        V1EnvFromSource(secret_ref=V1SecretReference(name=secret)) for secret in secrets
    ]


def docker_network_gateway() -> str | None:
    network_name = "airflow"
    try:
        result = subprocess.run(
            ["docker", "network", "inspect", network_name],
            check=True,
            capture_output=True,
            text=True,
        )

        for line in result.stdout.splitlines():
            if "Gateway" in line:
                match = re.search(r'"Gateway"\s*:\s*"([^"]+)"', line)
                if match:
                    print(f"Docker network Gateway for Minikube is - "
                          f"{match.group(1)}")
                    return match.group(1)
        print("Is your minikube cluster running? Please run and try again.")
        return None

    except subprocess.CalledProcessError as e:
        print(f"Error running docker network inspect: {e}")
        return None
    except FileNotFoundError:
        print("Docker command not found. Is Docker installed and in your PATH?")
        return None
