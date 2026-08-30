FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY ui/ ./ui/

RUN pip install --no-cache-dir .

# El proceso concreto (api|worker) se decide en docker-compose.yml,
# nunca en la imagen: API y WORKER comparten imagen y código (§19.2).
CMD ["uvicorn", "aap.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
