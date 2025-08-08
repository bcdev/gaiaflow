# This Dockerfile is to create an image that contains the dependencies that your package needs as well as the package
# itself. This image will be then used to run the DAGs you create in this repository on the Airflow hosted
# on our development Kubernetes cluster in AWS.

FROM  mambaorg/micromamba:latest

WORKDIR /app

COPY environment.yml .

RUN micromamba install -f environment.yml -n base
# This is temporary. Once gaiaflow is released, it will used installed from PyPi.
COPY ./gaiaflow ./gaiaflow
RUN micromamba run -n base pip install /app/gaiaflow
ENV PATH=/opt/conda/bin:$PATH

ENTRYPOINT ["python", "-m", "gaiaflow.core.runner"]
