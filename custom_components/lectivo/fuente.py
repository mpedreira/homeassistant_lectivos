"""Lectura del CSV desde una URL http(s) o desde una ruta local."""
from __future__ import annotations

from pathlib import Path

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

TIMEOUT_HTTP = 20


class RutaNoPermitida(Exception):
    """La ruta local no está permitida por Home Assistant."""


def es_url(origen: str) -> bool:
    return origen.strip().lower().startswith(("http://", "https://"))


async def async_leer_texto(hass: HomeAssistant, origen: str) -> str:
    origen = origen.strip()
    if es_url(origen):
        sesion = async_get_clientsession(hass)
        async with sesion.get(
            origen, timeout=aiohttp.ClientTimeout(total=TIMEOUT_HTTP)
        ) as resp:
            resp.raise_for_status()
            return await resp.text(encoding="utf-8-sig")
    if not hass.config.is_allowed_path(origen):
        raise RutaNoPermitida(origen)
    return await hass.async_add_executor_job(Path(origen).read_text, "utf-8-sig")
