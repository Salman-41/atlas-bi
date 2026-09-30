FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
RUN useradd --create-home atlas && mkdir /app/data && chown -R atlas:atlas /app
USER atlas
EXPOSE 8000
CMD ["uvicorn", "atlas.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
