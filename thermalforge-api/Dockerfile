FROM python:3.12.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system thermalforge \
    && useradd --system --gid thermalforge --home-dir /app thermalforge

COPY pyproject.toml requirements.lock alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN python -m pip install --upgrade pip \
    && python -m pip install --requirement requirements.lock \
    && python -m pip install --no-deps .

RUN chown -R thermalforge:thermalforge /app
USER thermalforge

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
