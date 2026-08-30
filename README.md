# AAP — Autonomous Agent Platform

Runtime que interpreta agentes definidos por datos (Agent Definitions), no por código.
Diseño completo en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — léelo antes de tocar nada.

## Estado

V1 "Laboratory" en construcción por hitos (ver `docs/ARCHITECTURE.md` §26 y el plan
de la sesión que abrió este repo). Hito actual: **H0 — esqueleto y andamiaje**.

## Arrancar en local (sin Docker)

```bash
pip install -e ".[dev]"
uvicorn aap.api.main:app --reload --port 8080
# en otra terminal:
python -m aap.worker.main
```

`GET http://localhost:8080/health` debe responder `{"status":"ok","api":true,"worker":true,"db":true,"providers":{}}`
una vez el worker lleva unos segundos corriendo.

## Arrancar con Docker

```bash
cp .env.example .env
docker compose up -d
curl http://localhost:8080/health
```

El estado (`control.db`, `runtime.db`, `domain.db`) vive en `./data`, montado como
volumen — nunca dentro de la imagen (§19.2). `docker compose down && docker compose up -d`
debe dejar el sistema exactamente como estaba.

## Tests

```bash
pytest
```

## Reglas que no se rompen

Ver `docs/ARCHITECTURE.md` §4 (P1–P10) y §33. Resumen operativo:

1. La Definición del agente es la fuente de verdad; la UI y la API solo la editan.
2. Ninguna tool se ejecuta sin pasar por el Policy Engine.
3. Todo run tiene presupuesto; todo lo que ocurre se registra como evento.
4. `core/` no importa de `tools/`, `domain/`, `api/` ni `factory/` (§20.2).
5. Nada entra sin un problema medido que lo justifique.
