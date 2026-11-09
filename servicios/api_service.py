"""Servicio de consumo de API pública para UniHogar.

API utilizada: ExchangeRate-API (endpoint abierto, sin clave).
    GET https://open.er-api.com/v6/latest/USD
Devuelve las tasas de todas las monedas respecto al dólar (USD).
Se usa para mostrar el equivalente en dólares del alquiler (C$/mes),
útil para estudiantes extranjeros o familias que envían dinero.

Condiciones de uso: la API abierta pide atribución ("Rates By
Exchange Rate API") y no abusar de las consultas (se actualiza
1 vez al día). Por eso se guarda un caché en memoria de 1 hora.

Este módulo NO importa PySide6: la lógica de red queda separada
de la interfaz gráfica.
"""

import time

import requests

URL_TASAS = "https://open.er-api.com/v6/latest/USD"
TIMEOUT = 10
DURACION_CACHE = 3600  # segundos

_cache = {"momento": 0.0, "datos": None}


class ErrorAPI(Exception):
    """Error al consultar la API (red, respuesta o datos)."""


def consultar_tasa_cordoba(usar_cache=True):
    """Devuelve {'nio_por_usd': float, 'actualizado': str, 'fuente': str}."""

    ahora = time.time()

    if (
        usar_cache
        and _cache["datos"] is not None
        and ahora - _cache["momento"] < DURACION_CACHE
    ):
        return dict(_cache["datos"])

    try:
        respuesta = requests.get(URL_TASAS, timeout=TIMEOUT)
        respuesta.raise_for_status()
        datos = respuesta.json()

    except requests.exceptions.Timeout:
        raise ErrorAPI("La consulta excedió el tiempo de espera.")
    except requests.exceptions.ConnectionError:
        raise ErrorAPI("No hay conexión a Internet.")
    except requests.exceptions.HTTPError as error:
        raise ErrorAPI(f"El servicio respondió con error: {error}")
    except requests.exceptions.RequestException as error:
        raise ErrorAPI(f"Error al consultar la API: {error}")
    except ValueError:
        raise ErrorAPI("La respuesta recibida no contiene JSON válido.")

    if datos.get("result") != "success":
        raise ErrorAPI("La API no devolvió un resultado exitoso.")

    try:
        tasa = float(datos["rates"]["NIO"])
    except (KeyError, TypeError, ValueError):
        raise ErrorAPI("La respuesta no incluye la tasa del córdoba (NIO).")

    if tasa <= 0:
        raise ErrorAPI("La tasa recibida no es válida.")

    resultado = {
        "nio_por_usd": tasa,
        "actualizado": str(datos.get("time_last_update_utc", "")),
        "fuente": "ExchangeRate-API (open.er-api.com)",
    }

    _cache["momento"] = ahora
    _cache["datos"] = resultado

    return dict(resultado)


def cordobas_a_dolares(monto_cordobas, tasa_nio_por_usd):
    """Convierte C$ a US$ (2 decimales). Valida entradas."""

    monto = float(monto_cordobas)

    if monto < 0:
        raise ValueError("El monto no puede ser negativo.")
    if tasa_nio_por_usd <= 0:
        raise ValueError("La tasa debe ser mayor que cero.")

    return round(monto / tasa_nio_por_usd, 2)


def dolares_a_cordobas(monto_dolares, tasa_nio_por_usd):
    monto = float(monto_dolares)

    if monto < 0:
        raise ValueError("El monto no puede ser negativo.")

    return round(monto * tasa_nio_por_usd, 2)
