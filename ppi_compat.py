"""
Parche de compatibilidad para py_ppi_arg 0.2.3.

`client.py:234` arma las URLs como `urls.api_url + path`, donde `api_url`
termina en barra y casi todos los paths de `urls.py` empiezan con barra:

    "https://api.portfoliopersonal.com/" + "/api/Cotizaciones/Item/Search?q=AL30"
    -> "https://api.portfoliopersonal.com//api/Cotizaciones/Item/Search?q=AL30"

La API toleraba la barra doble y dejó de hacerlo en algún momento entre el
2026-09-02 (última corrida OK) y el 2026-10-01: ahora devuelve 404. El login
sobrevive porque `token` y `validate_2fa` son los dos únicos endpoints de
`urls.py` sin barra inicial, así que el síntoma es "autentica bien y después
todo da 404".

Importar este módulo antes de instanciar PPI normaliza el join. Es idempotente.

    import ppi_compat  # noqa: F401
    from py_ppi_arg import PPI
"""
from __future__ import annotations

from py_ppi_arg.components import client as _client
from py_ppi_arg.components import urls as _urls

_MARCA = "_ppi_compat_barra_doble"


def _api_url(self, path: str) -> str:
    return _urls.api_url.rstrip("/") + "/" + path.lstrip("/")


def aplicar() -> bool:
    """Parcha `RestClient._api_url`. Devuelve True si hizo falta parchear."""
    actual = getattr(_client.RestClient, "_api_url", None)
    if actual is not None and getattr(actual, _MARCA, False):
        return False
    setattr(_api_url, _MARCA, True)
    _client.RestClient._api_url = _api_url
    return True


aplicar()
