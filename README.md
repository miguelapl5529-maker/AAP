# AAP — Autonomous Agent Platform

Runtime que interpreta agentes definidos por datos (Agent Definitions), no por código.
Diseño completo en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — léelo antes de tocar nada.

## Estado

V1 "Laboratory" completa por hitos (ver `docs/ARCHITECTURE.md` §26 y el plan de la
sesión que abrió este repo): **H0–H10**, el recorrido planeado entero.

## UI

`http://localhost:8080/` redirige al Dashboard (`/ui/`). HTML/CSS/JS planos, sin
build ni framework (§15.1, §25: "primero fea pero funcional") — la API los sirve
como estáticos, así que `docker compose up` no necesita una etapa de build de
frontend. El formulario de "Crear agente" se genera recorriendo
`GET /schema/agent-definition`: añadir un campo al schema le añade un control a
la UI sin tocar `ui/app.js`. El Run Inspector hace polling cada 1.5s (§0.5: no
hace falta WebSocket) y para en cuanto el run llega a un estado terminal.

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

## Evaluación (§12)

```bash
python -m aap.cli.main evaluate demand-hunter
```

Corre el eval set fijo declarado en `evaluation.eval_set_ref` (`evals/demand_hunter_v1.jsonl`)
contra la versión activa: cada escenario trae su propio plan de tool_calls scripteado
(determinista, sin LLM real) y comprobaciones puramente programáticas — **sin juez-LLM**,
tal como pide la brief. El resultado se persiste en `runtime.db:evaluations` y queda
visible en `GET /agents/{id}/metrics`. Las métricas mecánicas (Capa 1: tasa de éxito,
coste, latencia, error de tool, denegaciones de política) se calculan siempre de los
runs reales, sin ejecutar nada — por eso sí son endpoints de la API
(`GET /agents/{id}/metrics`, `GET /agents/{id}/compare?a=&b=`), mientras que correr el
eval set completo queda en el CLI (ejecuta runs de verdad, aunque scripteados e
instantáneos).

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
