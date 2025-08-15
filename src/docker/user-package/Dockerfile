# This Dockerfile is to create an image that contains the dependencies that your package needs as well as the package
# itself. This image will be then used to run the DAGs you create in this repository on the Airflow hosted
# on our development Kubernetes cluster in AWS.

FROM  mambaorg/micromamba:latest

WORKDIR /app

COPY environment.yml .

RUN micromamba install -f environment.yml -n base
# This is temporary. Once gaiaflow is released, it will used installed from PyPi.
COPY ./BC/gaiaflow ./gaiaflow
RUN micromamba run -n base pip install /app/gaiaflow
RUN micromamba run -n base micromamba install apache-airflow

ENV PATH=/opt/conda/bin:$PATH

#ENTRYPOINT ["python", "-m", "gaiaflow.core.runner"]
# Optional: install local development version if mounted
# If /app/gaiaflow exists (from a bind mount), pip install it; otherwise, rely on environment.yml
# TODO: Needs fixing before releasing.
#ENTRYPOINT ["sh", "-c", "\
#if [ -d /app/gaiaflow ]; then \
#    echo 'Installing local gaiaflow for development'; \
#    micromamba run -n base pip install /app/gaiaflow; \
#else \
#    echo 'Using gaiaflow from environment.yml or PyPI'; \
#fi; \
#python -m gaiaflow.core.runner"]
ENTRYPOINT ["python", "-m", "gaiaflow.core.runner"]