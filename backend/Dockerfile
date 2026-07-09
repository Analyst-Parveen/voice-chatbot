# Production backend image (docker-full mode).
#
# Installs system dependencies for voice (ffmpeg) and MS SQL Server (ODBC 17),
# then the Python app with the selected extras. Heavy because voice/embeddings
# pull PyTorch — this is the server image. Override INSTALL_EXTRAS to slim it
# (e.g. "mssql" only if you run voice elsewhere).
FROM python:3.11-slim

ARG INSTALL_EXTRAS=voice,embeddings,mssql,cache

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps: ffmpeg (Whisper audio decode), curl/gnupg (repo keys),
# unixodbc + Microsoft ODBC Driver 17 (SQL Server).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl gnupg2 apt-transport-https unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (better layer caching: deps before app code).
COPY pyproject.toml ./
COPY app ./app
COPY ingestion ./ingestion
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN pip install --upgrade pip && pip install -e ".[${INSTALL_EXTRAS}]"

RUN mkdir -p /app/models /app/data && chmod +x scripts/*.sh 2>/dev/null || true

EXPOSE 8000
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
