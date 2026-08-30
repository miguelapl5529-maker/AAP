"""Exportación determinista a YAML (§14.1, §16.4).

La base de datos manda para ejecutar; Git manda para revisar y recuperar.
`export_yaml` produce el fichero que iría a `agents/<slug>/v<N>.yaml`;
`definition_from_yaml_doc` recupera el contenido puro (sin `version`ni
`status`, que son metadatos de la fila, no del comportamiento) para poder
re-validarlo y comparar su hash contra el original — la prueba de
"exportar-importar es idempotente" que exige M1.
"""

import yaml

from aap.core.definition.canonical import content_hash
from aap.core.definition.validate import validate_definition

_METADATA_KEYS = ("version", "status", "content_hash")


def export_yaml(version_record: dict) -> str:
    doc = {
        "id": version_record["agent_id"],
        "version": version_record["version"],
        "status": version_record["status"],
        "content_hash": version_record["content_hash"],
        **version_record["definition"],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def definition_from_yaml_doc(yaml_text: str) -> dict:
    doc = yaml.safe_load(yaml_text)
    return {k: v for k, v in doc.items() if k not in _METADATA_KEYS}


def roundtrip_hash_matches(version_record: dict) -> bool:
    """Exporta, reimporta, revalida y compara el hash: la prueba de M1."""
    yaml_text = export_yaml(version_record)
    recovered = definition_from_yaml_doc(yaml_text)
    validated = validate_definition(recovered)
    return content_hash(validated.model_dump(mode="json")) == version_record["content_hash"]
