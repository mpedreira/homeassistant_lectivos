import sys
from datetime import date
sys.path.insert(0, "custom_components/lectivo")
from lectivo_core import CalendarioLectivo
c = CalendarioLectivo.desde_texto(open("test/ejemplo.csv", encoding="utf-8").read())
casos = {
    date(2026, 9, 14): False,  # antes del curso
    date(2026, 9, 15): True,
    date(2026, 9, 19): False,  # sábado
    date(2026, 10, 12): False, # festivo suelto
    date(2026, 10, 13): True,
    date(2026, 12, 22): True,
    date(2026, 12, 23): False, # inicio rango
    date(2027, 1, 6): False,   # fin rango
    date(2027, 1, 7): True,
    date(2027, 6, 22): True,
    date(2027, 6, 23): False,  # después del curso
}
for d, esperado in casos.items():
    assert c.es_lectivo(d) == esperado, (d, esperado)
print("OK", len(casos), "casos")

# --- calendario vacío / sin CSV: todo lectivo salvo fines de semana ---
for texto in ["", "   \n", "inicio,fin,tipo,descripcion\n"]:
    v = CalendarioLectivo.desde_texto(texto)
    assert v.esta_vacio
    assert v.es_lectivo(date(2026, 10, 26))        # lunes
    assert v.es_lectivo(date(2030, 1, 4))          # viernes, cualquier año
    assert not v.es_lectivo(date(2026, 10, 24))    # sábado
    assert not v.es_lectivo(date(2026, 10, 25))    # domingo
assert CalendarioLectivo.vacio().es_lectivo(date(2026, 10, 27))

# solo festivos, sin filas "curso": todos lectivos salvo festivos y fines de semana
f = CalendarioLectivo.desde_texto("inicio,fin,tipo,descripcion\n2026-10-12,,festivo,Pilar\n")
assert not f.es_lectivo(date(2026, 10, 12)) and f.es_lectivo(date(2026, 10, 13))
assert not f.es_lectivo(date(2026, 10, 17))        # sábado

# contenido sin cabecera válida: error (no se confunde con vacío)
try:
    CalendarioLectivo.desde_texto("<html>404</html>")
    raise SystemExit("debería fallar")
except ValueError:
    pass
print("OK vacíos")

# --- proximo(): siguiente día lectivo / no lectivo (estrictamente posterior) ---
c = CalendarioLectivo.desde_texto(open("test/ejemplo.csv", encoding="utf-8").read())
assert c.proximo(date(2026, 10, 9), True) == date(2026, 10, 13)    # vie -> salta fin de semana y festivo 12
assert c.proximo(date(2026, 10, 9), False) == date(2026, 10, 10)   # sábado
assert c.proximo(date(2026, 12, 22), False) == date(2026, 12, 23)  # empieza Navidad
assert c.proximo(date(2026, 12, 23), True) == date(2027, 1, 7)     # fin de Navidad
assert c.proximo(date(2027, 6, 22), True) is None                  # tras fin de curso, nunca más lectivo
assert CalendarioLectivo.vacio().proximo(date(2026, 10, 26), False) == date(2026, 10, 31)
assert CalendarioLectivo.vacio().proximo(date(2026, 10, 30), True) == date(2026, 11, 2)
print("OK proximo")
