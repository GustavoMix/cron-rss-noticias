"""Salidas en JSON: una para consumir, otra para diagnosticar.

    datos/noticias.json        lo que consumiría una app
    datos/estado_fuentes.json  por qué una fuente trajo 0 items

El segundo archivo existe porque la pregunta que uno se hace a las tres de la
mañana no es "¿cuántas noticias hay?" sino "¿por qué esta fuente está muda?".
Sin él, un feed que quedó bloqueado y uno que simplemente no publicó nada se
ven exactamente igual.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..config import Fuente
from ..modelos import Noticia, ResultadoFuente


def escribir_noticias(
    ruta: Path,
    noticias: List[Noticia],
    generado_en: str,
    feeds: List[Dict[str, Any]],
    maximo: int = 500,
) -> Path:
    seleccion = noticias[:maximo]
    payload = {
        "version_esquema": "1.0",
        "generado_en": generado_en,
        "resumen": {
            "noticias": len(seleccion),
            "en_historial": len(noticias),
            "por_categoria": dict(Counter(n.categoria for n in seleccion).most_common()),
            "por_region": dict(Counter(r for n in seleccion for r in n.regiones).most_common()),
            "por_idioma": dict(Counter(n.idioma for n in seleccion).most_common()),
            "por_tipo_fuente": dict(Counter(n.tipo_fuente for n in seleccion).most_common()),
        },
        "feeds": feeds,
        "noticias": [n.a_dict() for n in seleccion],
    }
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


def escribir_estado(
    ruta: Path,
    fuentes: Iterable[Fuente],
    resultados: Iterable[ResultadoFuente],
    generado_en: str,
    descartes: Dict[str, int] | None = None,
) -> Path:
    por_id = {r.fuente_id: r for r in resultados}
    filas: List[Dict[str, Any]] = []

    for fuente in fuentes:
        resultado = por_id.get(fuente.id)
        filas.append({
            "id": fuente.id,
            "nombre": fuente.nombre,
            "tipo": fuente.tipo,
            "url": fuente.url,
            "archivo": fuente.archivo,
            "categoria": fuente.categoria,
            "region": fuente.region,
            "idioma": fuente.idioma,
            "peso": fuente.peso,
            "activa": fuente.activa,
            "estado": resultado.estado if resultado else "no_ejecutada",
            "items": resultado.items if resultado else 0,
            "duracion_ms": resultado.duracion_ms if resultado else 0,
            "error": resultado.error if resultado else None,
        })

    conteo = Counter(f["estado"] for f in filas)
    payload = {
        "generado_en": generado_en,
        "resumen": {
            "fuentes": len(filas),
            "por_estado": dict(conteo.most_common()),
            # Estas dos son las que hay que mirar primero cuando el feed baja:
            # bloqueadas significa "falta IP", error significa "fuente rota".
            "bloqueadas": conteo.get("bloqueada", 0),
            "con_error": conteo.get("error", 0),
            "descartes_en_proceso": descartes or {},
        },
        "fuentes": sorted(filas, key=lambda x: (x["estado"] != "error", x["tipo"], x["id"])),
    }

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def escribir_crudo(
    ruta: Path,
    items: List[Any],
    resultados: List[ResultadoFuente],
    momento: str,
    etiqueta: str,
    extra: Dict[str, Any] | None = None,
) -> Path:
    """Resultado intermedio de un job de CI, para que el job final lo combine.

    Es el formato de intercambio entre los jobs de fan-out y el de construcción:
    items sin normalizar + cómo le fue a cada fuente. En `extra` viaja lo que el
    job final necesita persistir de vuelta (por ejemplo, los ETag de los feeds
    leídos: cada job los descubre, pero solo el final escribe en el repo).
    """
    payload = {
        "etiqueta": etiqueta,
        "momento": momento,
        "items": [i.a_dict() for i in items],
        "resultados": [r.a_dict() for r in resultados],
        "extra": extra or {},
    }
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino
