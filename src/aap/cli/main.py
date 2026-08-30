"""CLI mínima para operar Agent Definitions y runs sin UI (§25, etapa B0).

    python -m aap.cli.main validate definicion.yaml
    python -m aap.cli.main create-agent demand-hunter "Demand Hunter"
    python -m aap.cli.main create-version demand-hunter definicion.yaml
    python -m aap.cli.main export demand-hunter 1 --out agents/demand-hunter/v1.yaml
    python -m aap.cli.main show demand-hunter
    python -m aap.cli.main trace <run_id>
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from aap.core.definition import repository as repo
from aap.core.definition.export import export_yaml
from aap.core.definition.validate import DefinitionValidationError, validate_definition
from aap.core.events.log import list_events
from aap.core.runtime.runs import RunNotFoundError, get_run
from aap.core.runtime.tool_calls import list_tool_calls


def _load_doc(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    if path.endswith((".yaml", ".yml")):
        return yaml.safe_load(text)
    return json.loads(text)


def cmd_validate(args: argparse.Namespace) -> int:
    data = _load_doc(args.file)
    try:
        validate_definition(data)
    except DefinitionValidationError as exc:
        print(f"INVALIDA: {exc}", file=sys.stderr)
        return 1
    print("OK: definición válida")
    return 0


def cmd_create_agent(args: argparse.Namespace) -> int:
    agent = repo.create_agent(args.id, args.name, owner=args.owner)
    print(json.dumps(agent, indent=2, ensure_ascii=False))
    return 0


def cmd_create_version(args: argparse.Namespace) -> int:
    data = _load_doc(args.file)
    try:
        version = repo.create_version(args.agent_id, data, created_by=args.by, notes=args.notes)
    except DefinitionValidationError as exc:
        print(f"INVALIDA: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in version.items() if k != "definition"}, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    version = repo.get_version(args.agent_id, args.version)
    yaml_text = export_yaml(version)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(yaml_text, encoding="utf-8")
        print(f"exportado a {out_path}")
    else:
        print(yaml_text)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    agent = repo.get_agent(args.agent_id)
    versions = repo.list_versions(args.agent_id)
    print(json.dumps({"agent": agent, "versions": [
        {k: v for k, v in ver.items() if k != "definition"} for ver in versions
    ]}, indent=2, ensure_ascii=False))
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    try:
        run = get_run(args.run_id)
    except RunNotFoundError:
        print(f"no existe el run {args.run_id}", file=sys.stderr)
        return 1

    print(f"RUN {run['id']}  agent={run['agent_id']}  version={run['agent_version_id']}")
    print(f"status={run['status']}  steps={run['steps']}  tool_calls={run['tool_calls']}  "
          f"cost_usd={run['cost_usd']}  termination={run['termination_reason']}")
    print()
    print("EVENTOS")
    for ev in list_events(args.run_id):
        print(f"  [{ev['seq']:>3}] {ev['ts']}  {ev['level']:<5} {ev['type']:<16} "
              f"step={ev['step']}  {json.dumps(ev['payload'], ensure_ascii=False)}")
    print()
    print("TOOL CALLS")
    for call in list_tool_calls(args.run_id):
        print(f"  step={call['step']} {call['tool_id']:<20} status={call['status']:<10} "
              f"latency_ms={call['latency_ms']}  {call['error'] or ''}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aap")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="valida un fichero YAML/JSON contra el schema")
    p.add_argument("file")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("create-agent", help="crea la identidad lógica de un agente")
    p.add_argument("id")
    p.add_argument("name")
    p.add_argument("--owner")
    p.set_defaults(func=cmd_create_agent)

    p = sub.add_parser("create-version", help="valida y guarda una versión inmutable nueva")
    p.add_argument("agent_id")
    p.add_argument("file")
    p.add_argument("--by")
    p.add_argument("--notes")
    p.set_defaults(func=cmd_create_version)

    p = sub.add_parser("export", help="exporta una versión a YAML determinista")
    p.add_argument("agent_id")
    p.add_argument("version", type=int)
    p.add_argument("--out")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("show", help="muestra un agente y sus versiones")
    p.add_argument("agent_id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("trace", help="reconstruye la traza completa de un run")
    p.add_argument("run_id")
    p.set_defaults(func=cmd_trace)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
