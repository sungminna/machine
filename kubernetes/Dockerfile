FROM apache/airflow
USER root
COPY requirements.txt /opt/airflow/requirements.txt

USER airflow

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /opt/airflow/requirements.txt