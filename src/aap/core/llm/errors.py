"""Errores de provider. El router los usa para decidir si degrada o falla (§17.2)."""


class ProviderUnavailableError(RuntimeError):
    """El provider no puede atender la petición ahora (sin configurar, red caída, 5xx)."""


class ProviderTimeoutError(ProviderUnavailableError):
    pass


class NoProviderAvailableError(RuntimeError):
    """Se agotó la cadena de degradación para una capacidad sin encontrar un provider sano."""
