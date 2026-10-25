#!/usr/bin/env bash
# Instala el componente "lectivo" en Home Assistant (Docker).
#
# Uso (desde /home/kour, con lectivo.zip al lado):
#   sudo ./instalar_lectivo.sh              # instala, valida y reinicia HA
#   sudo ./instalar_lectivo.sh --sin-reinicio
#
# Variables opcionales:
#   ZIP=/home/kour/lectivo.zip
#   HA_CONFIG=/root/homeassistant/config
#   HA_CONTAINER=homeassistant
set -euo pipefail

ZIP="${ZIP:-$(dirname "$(readlink -f "$0")")/lectivo.zip}"
HA_CONFIG="${HA_CONFIG:-/root/homeassistant/config}"
HA_CONTAINER="${HA_CONTAINER:-homeassistant}"
REINICIAR=1
[[ "${1:-}" == "--sin-reinicio" ]] && REINICIAR=0

[[ -f "$ZIP" ]]       || { echo "No encuentro $ZIP"; exit 1; }
[[ -d "$HA_CONFIG" ]] || { echo "No existe $HA_CONFIG (ajusta HA_CONFIG)"; exit 1; }
command -v unzip >/dev/null || { echo "Falta unzip: apt install unzip"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
unzip -q "$ZIP" -d "$TMP"

DEST="$HA_CONFIG/custom_components/lectivo"
mkdir -p "$HA_CONFIG/custom_components"

# Copia de seguridad si ya había una versión
if [[ -d "$DEST" ]]; then
  COPIA="$HA_CONFIG/.lectivo_backup_$(date +%Y%m%d%H%M%S)"  # fuera de custom_components
  mv "$DEST" "$COPIA"
  echo "Versión anterior guardada en $COPIA"
fi
cp -r "$TMP/custom_components/lectivo" "$DEST"
find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} +

# CSVs: solo se copian si no existen (no pisa tus ediciones)
mkdir -p "$HA_CONFIG/lectivo"
for f in mateo.csv ejemplo.csv; do
  if [[ -f "$TMP/$f" && ! -e "$HA_CONFIG/lectivo/$f" ]]; then
    cp "$TMP/$f" "$HA_CONFIG/lectivo/$f"
    echo "Copiado $HA_CONFIG/lectivo/$f"
  fi
done

# Mismo propietario que el resto de la configuración
PROP="$(stat -c '%u:%g' "$HA_CONFIG/configuration.yaml" 2>/dev/null || true)"
if [[ -n "$PROP" ]]; then
  chown -R "$PROP" "$DEST" "$HA_CONFIG/lectivo"
fi

echo "Componente instalado en $DEST"

cat <<'TXT'

Tras reiniciar HA: Ajustes > Dispositivos y servicios > Añadir integración > "Día lectivo".
Pon el nombre (p. ej. Lectivo Mateo) y la URL del CSV, o una ruta local
(dentro del contenedor es /config/lectivo/mateo.csv). Repite para cada persona.
Para cambiar la URL más tarde: la integración > Configurar.
TXT

if [[ $REINICIAR -eq 1 ]]; then
  if docker ps -a --format '{{.Names}}' | grep -qx "$HA_CONTAINER"; then
    echo "Validando configuración..."
    if docker exec "$HA_CONTAINER" python -m homeassistant --script check_config -c /config >/dev/null 2>&1; then
      echo "Configuración válida. Reiniciando $HA_CONTAINER..."
      docker restart "$HA_CONTAINER" >/dev/null
      echo "Reiniciado."
    else
      echo "AVISO: check_config falló (o no está disponible). No reinicio."
      echo "Revísalo y reinicia a mano: docker restart $HA_CONTAINER"
    fi
  else
    echo "No encuentro el contenedor '$HA_CONTAINER'. Reinicia HA a mano."
  fi
else
  echo "Sin reinicio: reinicia HA para cargar el componente (docker restart $HA_CONTAINER)."
fi
