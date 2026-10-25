"""Integración Día lectivo (configurable desde la interfaz)."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN

PLATFORMS = ["binary_sensor"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICIO_CONSULTAR = "consultar"
SCHEMA_CONSULTAR = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("fecha"): cv.date,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def _consultar(call: ServiceCall) -> ServiceResponse:
        entity_id = call.data["entity_id"]
        registro = er.async_get(hass).async_get(entity_id)
        sensor = (
            hass.data.get(DOMAIN, {}).get(registro.unique_id) if registro else None
        )
        if sensor is None:
            raise ServiceValidationError(
                f"{entity_id} no es un sensor de la integración Día lectivo"
            )
        fecha = call.data.get("fecha") or dt_util.now().date()
        motivo = sensor.calendario.motivo_no_lectivo(fecha)
        return {
            "entity_id": entity_id,
            "fecha": fecha.isoformat(),
            "lectivo": motivo is None,
            "motivo": motivo,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICIO_CONSULTAR,
        _consultar,
        schema=SCHEMA_CONSULTAR,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_recargar))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _recargar(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Se llama al cambiar las opciones (nueva URL)."""
    await hass.config_entries.async_reload(entry.entry_id)
