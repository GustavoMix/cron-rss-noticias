"""Fechas. Todo el sistema trabaja en UTC y con datetimes conscientes de zona.

Las fuentes entregan fechas en cualquier formato imaginable (RFC 822, ISO, y
Facebook directamente en prosa: "hace 3 h", "Ayer a las 14:20"). Acá se
convierte todo a un solo formato y se rechaza lo que no se entiende, en vez de
inventar una fecha: una nota sin fecha confiable se ordena por el momento en
que la vimos, no por una fecha falsa.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime
from typing import Optional

from dateutil import parser as _parser

UTC = timezone.utc

# "hace 3 h", "3 h", "hace 25 min", "2 d" — lo que muestra Facebook en el feed.
_RELATIVO = re.compile(
    r"(?:hace\s+)?(\d+)\s*(min(?:uto)?s?|h(?:ora)?s?|d(?:[ií]a)?s?|sem(?:ana)?s?)\b",
    re.IGNORECASE,
)
_UNIDADES = {"min": "minutes", "h": "hours", "d": "days", "sem": "weeks"}


def ahora() -> datetime:
    return datetime.now(UTC)


def ahora_iso() -> str:
    return ahora().isoformat(timespec="seconds")


def _con_zona(valor: datetime) -> datetime:
    """Una fecha sin zona se interpreta como UTC: es el supuesto menos dañino
    (a lo sumo desplaza la nota unas horas dentro de su propio día)."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC)


def parsear(valor: str | datetime | None, referencia: datetime | None = None) -> Optional[datetime]:
    """Devuelve un datetime en UTC, o None si no se pudo entender el valor."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return _con_zona(valor)

    texto = str(valor).strip()
    if not texto:
        return None

    # Formatos estándar primero: son los que traen los RSS.
    for intento in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            return _con_zona(intento(texto))
        except Exception:
            pass

    relativo = _fecha_relativa(texto, referencia or ahora())
    if relativo is not None:
        return relativo

    try:
        # dateutil acepta casi todo, incluso prosa; puede equivocarse, así que
        # va último y con fuzzy apagado para no aceptar cualquier cosa.
        return _con_zona(_parser.parse(texto))
    except Exception:
        return None


def _fecha_relativa(texto: str, referencia: datetime) -> Optional[datetime]:
    bajo = texto.lower()
    if "ahora" in bajo or "just now" in bajo:
        return referencia

    coincidencia = _RELATIVO.search(bajo)
    if coincidencia:
        cantidad = int(coincidencia.group(1))
        unidad_bruta = coincidencia.group(2).lower()
        for prefijo, unidad in _UNIDADES.items():
            if unidad_bruta.startswith(prefijo):
                return referencia - timedelta(**{unidad: cantidad})

    if "ayer" in bajo or "yesterday" in bajo:
        return referencia - timedelta(days=1)
    return None


def a_iso(valor: datetime | None) -> Optional[str]:
    return valor.astimezone(UTC).isoformat(timespec="seconds") if valor else None


def a_rfc2822(valor: datetime | None) -> str:
    """Formato de fecha que exige RSS 2.0 en <pubDate> y <lastBuildDate>."""
    return format_datetime((valor or ahora()).astimezone(UTC))


def horas_desde(valor: str | datetime | None, referencia: datetime | None = None) -> float:
    """Antigüedad en horas. Una fecha ilegible o futura cuenta como 0."""
    momento = parsear(valor)
    if momento is None:
        return float("inf")
    delta = (referencia or ahora()) - momento
    return max(0.0, delta.total_seconds() / 3600.0)


def es_reciente(valor: str | datetime | None, horas: float, referencia: datetime | None = None) -> bool:
    antiguedad = horas_desde(valor, referencia)
    return antiguedad != float("inf") and antiguedad <= horas
