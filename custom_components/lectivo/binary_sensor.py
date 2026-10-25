"""binary_sensor: on = hoy es lectivo, off = no lo es.

Se añade desde Ajustes > Dispositivos y servicios > Añadir integración > Día lectivo,
con un nombre y la URL (o ruta) del CSV. El CSV se vuelve a leer como mucho una vez
al día; la última copia buena se guarda en /config/.storage y se usa si falla la lectura.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CONF_URL, DOMAIN
from .fuente import async_leer_texto, es_url
from .lectivo_core import CalendarioLectivo

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)   # cada cuánto se recalcula on/off
REFRESCO_OK = timedelta(hours=24)      # cada cuánto se vuelve a leer el CSV
REFRESCO_ERROR = timedelta(hours=1)    # reintento si la lectura falla


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    origen = entry.options.get(CONF_URL, entry.data.get(CONF_URL, ""))
    async_add_entities(
        [LectivoSensor(hass, entry.entry_id, entry.data[CONF_NAME], origen)], True
    )


class LectivoSensor(BinarySensorEntity):
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, uid: str, nombre: str, origen: str) -> None:
        self.hass = hass
        self._attr_unique_id = uid
        self._attr_name = nombre
        self._origen = origen
        self._cache = Path(
            hass.config.path(".storage", f"lectivo_{hashlib.sha1(origen.encode()).hexdigest()[:12]}.csv")
        )
        self._calendario: CalendarioLectivo | None = None
        self._proxima_lectura = datetime.min.replace(tzinfo=dt_util.UTC)
        self._ultima_lectura_ok: datetime | None = None
        self._attr_is_on = False
        self._attr_extra_state_attributes: dict = {}

    @property
    def calendario(self) -> CalendarioLectivo:
        return self._calendario or CalendarioLectivo.vacio()

    async def async_added_to_hass(self) -> None:
        # Registro por unique_id para que la acción lectivo.consultar encuentre el sensor.
        self.hass.data.setdefault(DOMAIN, {})[self._attr_unique_id] = self

    async def async_will_remove_from_hass(self) -> None:
        self.hass.data.get(DOMAIN, {}).pop(self._attr_unique_id, None)

    # ---------- lectura del calendario ----------

    async def _refrescar(self) -> None:
        ahora = dt_util.utcnow()
        if ahora < self._proxima_lectura:
            return
        if not self._origen.strip():
            # Sin CSV configurado: solo se excluyen los fines de semana.
            self._calendario = CalendarioLectivo.vacio()
            self._proxima_lectura = ahora + REFRESCO_OK
            return
        try:
            texto = await async_leer_texto(self.hass, self._origen)
            calendario = CalendarioLectivo.desde_texto(texto, self._origen)
        except Exception as err:  # no existe, red, HTTP, CSV mal formado...
            self._proxima_lectura = ahora + REFRESCO_ERROR
            _LOGGER.warning("%s: no se pudo leer %s (%s)", self.name, self._origen, err)
            if self._calendario is None or self._calendario.esta_vacio:
                await self._cargar_cache()
            if self._calendario is None:
                # Sin CSV ni copia: todos lectivos salvo fines de semana.
                self._calendario = CalendarioLectivo.vacio()
            return
        self._calendario = calendario
        self._ultima_lectura_ok = ahora
        self._proxima_lectura = ahora + REFRESCO_OK
        if es_url(self._origen):
            await self.hass.async_add_executor_job(self._guardar_cache, texto)

    def _guardar_cache(self, texto: str) -> None:
        try:
            self._cache.write_text(texto, encoding="utf-8")
        except OSError as err:
            _LOGGER.debug("No se pudo guardar la caché %s: %s", self._cache, err)

    async def _cargar_cache(self) -> None:
        if not es_url(self._origen):
            return
        try:
            texto = await self.hass.async_add_executor_job(self._cache.read_text, "utf-8")
            self._calendario = CalendarioLectivo.desde_texto(texto, str(self._cache))
            _LOGGER.warning("%s: usando la última copia guardada", self.name)
        except (OSError, ValueError):
            pass

    # ---------- estado ----------

    async def async_update(self) -> None:
        await self._refrescar()
        calendario = self.calendario
        hoy = dt_util.now().date()
        self._attr_is_on = calendario.es_lectivo(hoy)
        sig_lectivo = calendario.proximo(hoy, True)
        sig_no_lectivo = calendario.proximo(hoy, False)
        self._attr_extra_state_attributes = {
            "calendario_cargado": not calendario.esta_vacio,
            "manana_lectivo": calendario.es_lectivo(hoy + timedelta(days=1)),
            "proximo_dia_lectivo": sig_lectivo.isoformat() if sig_lectivo else None,
            "proximo_dia_no_lectivo": sig_no_lectivo.isoformat() if sig_no_lectivo else None,
            "fecha": hoy.isoformat(),
            "motivo_no_lectivo": calendario.motivo_no_lectivo(hoy),
            "origen": self._origen,
            "ultima_lectura": (
                self._ultima_lectura_ok.isoformat() if self._ultima_lectura_ok else None
            ),
        }
