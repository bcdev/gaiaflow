from kubernetes.client import V1EnvFromSource, V1SecretReference

def inject_params_as_env_vars(params: dict) -> dict:
    return {f"PARAMS_{k.upper()}": f"{{{{ params.{k} }}}}" for k in params}


def build_env_from_secrets(secrets: list[str]) -> list[V1EnvFromSource]:
    return [
        V1EnvFromSource(secret_ref=V1SecretReference(name=secret)) for secret in secrets
    ]
