FROM apache/airflow:3.0.3-python3.12

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    bzip2 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH="/root/.pixi/bin:$PATH"
RUN pixi --version

WORKDIR /opt/airflow

RUN chmod -R 755 /opt/airflow
RUN cp /root/.pixi/bin/pixi /usr/local/bin/pixi
RUN chmod +x /usr/local/bin/pixi

RUN mkdir -p /opt/src && chmod 755 /opt/src
RUN chown -R 50000:0 /opt/airflow /opt/src
USER airflow
WORKDIR /opt/airflow
