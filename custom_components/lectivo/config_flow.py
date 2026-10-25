"""Alta y opciones desde la interfaz: nombre + URL (o ruta) del CSV."""
from __future__ import annotations

import logging
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import CONF_URL, DOMAIN
from .fuente import RutaNoPermitida, async_leer_texto
from .lectivo_core import CalendarioLectivo

_LOGGER = logging.getLogger(__name__)


async def _validar(hass, origen: str) -> str | None:
    """Devuelve None si se puede guardar, o la clave del error.

    - Sin origen, o CSV que aún no existe / no se puede leer: se acepta
      (el sensor tratará todos los días laborables como lectivos).
    - Ruta no permitida o CSV mal formado: error.
    """
    if not origen:
        return None
    try:
        texto = await async_leer_texto(hass, origen)
    except RutaNoPermitida:
        return "ruta_no_permitida"
    except Exception as err:  # red, HTTP, fichero inexistente...
        _LOGGER.warning("No se pudo leer %s al configurar (%s); se aceptará igualmente", origen, err)
        return None
    try:
        CalendarioLectivo.desde_texto(texto, origen)
    except ValueError as err:
        _LOGGER.warning("CSV no válido: %s", err)
        return "csv_invalido"
    return None


class LectivoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errores: dict[str, str] = {}
        if user_input is not None:
            nombre = user_input[CONF_NAME].strip()
            origen = user_input.get(CONF_URL, "").strip()
            await self.async_set_unique_id(re.sub(r"\W+", "_", nombre.lower()))
            self._abort_if_unique_id_configured()
            error = await _validar(self.hass, origen)
            if error is None:
                return self.async_create_entry(
                    title=nombre, data={CONF_NAME: nombre, CONF_URL: origen}
                )
            errores["base"] = error
        esquema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")): str,
                vol.Optional(CONF_URL, default=(user_input or {}).get(CONF_URL, "")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=esquema, errors=errores)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LectivoOptionsFlow()


class LectivoOptionsFlow(config_entries.OptionsFlow):
    """Cambiar la URL del CSV sin borrar y volver a crear la integración."""

    async def async_step_init(self, user_input=None):
        errores: dict[str, str] = {}
        actual = self.config_entry.options.get(
            CONF_URL, self.config_entry.data.get(CONF_URL, "")
        )
        if user_input is not None:
            origen = user_input.get(CONF_URL, "").strip()
            error = await _validar(self.hass, origen)
            if error is None:
                return self.async_create_entry(data={CONF_URL: origen})
            errores["base"] = error
            actual = origen
        esquema = vol.Schema({vol.Optional(CONF_URL, default=actual): str})
        return self.async_show_form(step_id="init", data_schema=esquema, errors=errores)
