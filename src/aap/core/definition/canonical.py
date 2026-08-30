"""Serialización canónica y hash de contenido (§14.1).

El hash es la identidad real de una versión: dos definiciones idénticas
son la misma versión. Claves ordenadas, sin espacios superfluos.
"""

import hashlib
import json


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(data: dict) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
