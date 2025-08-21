# CLI Reference

To see options for any command, add `--help` at the end of your command.

```bash
gaiaflow --help
```

## `gaiaflow dev`

Manage local development services.

```bash
gaiaflow dev [OPTIONS] COMMAND [ARGS]...
```

**Commands**

- `start` – Start Gaiaflow dev services
- `stop` – Stop Gaiaflow dev services
- `restart` – Restart services
- `cleanup` – Remove temporary context and state
- `dockerize` – Build a Docker image of your ML package

**Example**

```bash
gaiaflow dev start -p /path/to/project --service airflow --jupyter-port 8888
```


## `gaiaflow prod-local`
Manage **production-like services** (via Minikube).

**Commands**

- `start` – Start production-like services
- `stop` – Stop services
- `restart` – Restart services
- `dockerize` – Build image inside Minikube
- `create-config` – Generate Airflow K8s config (debugging only)
- `create-secret` – Create Kubernetes (K8s) secrets
- `cleanup` – Remove Minikube-specific resources

**Example**

```bash
gaiaflow prod-local start -p /path/to/project --force-new
```

