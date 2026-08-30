"""Migraciones del *schema de definición* (distintas de las migraciones de SQLite).

R10: el mecanismo debe existir y estar probado antes de necesitarse de
verdad. En V1 solo hay `schema_version: 1`, así que esto es la identidad
— pero ya es el punto único por el que pasaría una definición vieja.
"""

from aap.core.definition.models import SCHEMA_VERSION


class UnsupportedSchemaVersionError(ValueError):
    pass


def migrate(data: dict) -> dict:
    version = data.get("schema_version", SCHEMA_VERSION)
    if version == SCHEMA_VERSION:
        return data
    raise UnsupportedSchemaVersionError(
        f"schema_version {version} no soportado (actual: {SCHEMA_VERSION}); "
        "no existe todavía una migración registrada"
    )
