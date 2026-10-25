"""Lógica pura (sin dependencias de Home Assistant) para saber si un día es lectivo.

Reglas:
- Sábados y domingos NUNCA son lectivos.
- Sin CSV, con CSV vacío o ilegible: todos los días de lunes a viernes son lectivos.
- Si el CSV tiene filas "curso", solo es lectivo lo que cae dentro de algún curso.
- Los "festivo" (día o rango) no son lectivos.

Formato del CSV (cabecera obligatoria, separador coma, fechas ISO AAAA-MM-DD):

    inicio,fin,tipo,descripcion
    2026-09-09,2027-06-21,curso,Periodo lectivo
    2026-10-12,,festivo,Fiesta nacional
    2026-12-22,2026-12-25,festivo,Navidad

- tipo "curso": rango en el que hay clase (inicio y fin incluidos). Opcional; puede haber varios.
- tipo "festivo": día o rango sin clase. Si "fin" está vacío es un único día.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Rango:
    inicio: date
    fin: date
    descripcion: str = ""

    def contiene(self, dia: date) -> bool:
        return self.inicio <= dia <= self.fin


class CalendarioLectivo:
    def __init__(self, cursos: list[Rango], festivos: list[Rango]) -> None:
        self.cursos = cursos
        self.festivos = festivos

    @classmethod
    def vacio(cls) -> "CalendarioLectivo":
        """Sin datos: solo se excluyen los fines de semana."""
        return cls([], [])

    @property
    def esta_vacio(self) -> bool:
        return not self.cursos and not self.festivos

    @classmethod
    def desde_texto(cls, texto: str, origen: str = "csv") -> "CalendarioLectivo":
        texto = (texto or "").lstrip("﻿")
        if not texto.strip():
            return cls.vacio()
        lector = csv.DictReader(io.StringIO(texto))
        lector.fieldnames = [(c or "").strip().lower() for c in (lector.fieldnames or [])]
        if "inicio" not in lector.fieldnames:
            raise ValueError(f"{origen}: falta la cabecera 'inicio,fin,tipo,descripcion'")
        cursos: list[Rango] = []
        festivos: list[Rango] = []
        for n, fila in enumerate(lector, start=2):
            if not fila or not (fila.get("inicio") or "").strip():
                continue
            try:
                ini = date.fromisoformat(fila["inicio"].strip())
                fin_txt = (fila.get("fin") or "").strip()
                fin = date.fromisoformat(fin_txt) if fin_txt else ini
            except ValueError as err:
                raise ValueError(f"{origen}: fecha inválida en la línea {n}: {err}") from err
            if fin < ini:
                raise ValueError(f"{origen}: línea {n}: 'fin' anterior a 'inicio'")
            tipo = (fila.get("tipo") or "").strip().lower()
            rango = Rango(ini, fin, (fila.get("descripcion") or "").strip())
            if tipo == "curso":
                cursos.append(rango)
            elif tipo == "festivo":
                festivos.append(rango)
            else:
                raise ValueError(f"{origen}: línea {n}: tipo '{tipo}' no válido (curso|festivo)")
        return cls(cursos, festivos)

    def es_lectivo(self, dia: date) -> bool:
        return self.motivo_no_lectivo(dia) is None

    def proximo(self, desde: date, lectivo: bool, max_dias: int = 800) -> date | None:
        """Primer día POSTERIOR a `desde` que sea lectivo (o no lectivo, según `lectivo`)."""
        dia = desde
        for _ in range(max_dias):
            dia += timedelta(days=1)
            if self.es_lectivo(dia) == lectivo:
                return dia
        return None

    def motivo_no_lectivo(self, dia: date) -> str | None:
        """Devuelve por qué no es lectivo, o None si lo es."""
        if dia.weekday() >= 5:
            return "fin de semana"
        if self.cursos and not any(c.contiene(dia) for c in self.cursos):
            return "fuera del curso"
        for f in self.festivos:
            if f.contiene(dia):
                return f.descripcion or "festivo"
        return None
