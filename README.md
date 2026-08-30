# AAP — Autonomous Agent Platform

Runtime que interpreta agentes definidos por datos (Agent Definitions), no por código.
Diseño completo en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — léelo antes de tocar nada.

## Estado

V1 "Laboratory" en construcción por hitos (ver `docs/ARCHITECTURE.md` §26 y el plan
de la sesión que abrió este repo). Hito actual: **H7 — API + Worker + Docker**.

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

## Probar el pipeline completo (API → cola → worker)

```bash
curl -X POST localhost:8080/agents -d '{"id":"demo","name":"Demo"}' -H 'Content-Type: application/json'
curl -X POST localhost:8080/agents/demo/versions -d @definicion.json -H 'Content-Type: application/json'
curl -X POST localhost:8080/agents/demo/runs -d '{"input":{}}' -H 'Content-Type: application/json'
# → 202 {"run_id": "...", "status": "queued"} — el worker lo recoge en <2s
curl localhost:8080/runs/<run_id>
curl localhost:8080/runs/<run_id>/events
```

El servidor HTTP nunca ejecuta el bucle del agente (§6.12, §19.2, §22.3): solo encola en
`runtime.db:runs` con `status=queued`; el proceso `worker` (contenedor separado) hace
polling cada 2s y ejecuta con `core/runtime/executor.py`.

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
