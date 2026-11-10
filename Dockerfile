FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 postgresql-client tar \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY ops ./ops
COPY ops/container-entrypoint.sh /container-entrypoint.sh
RUN chmod 0755 /container-entrypoint.sh && mkdir -p /var/lib/potok-crm/documents \
    && useradd --system --uid 10001 --create-home potok \
    && chown -R potok:potok /app /var/lib/potok-crm
USER potok
EXPOSE 8000
ENTRYPOINT ["/container-entrypoint.sh"]
