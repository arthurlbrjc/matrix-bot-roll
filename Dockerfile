FROM python:3.14-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libolm-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction

COPY . .

ENV PYTHONPATH=/app/src

RUN useradd --create-home bot \
    && mkdir -p /app/store \
    && chown -R bot:bot /app
USER bot

VOLUME ["/app/store"]

EXPOSE 8080

CMD ["python", "-m", "matrix_bot_roll.main"]