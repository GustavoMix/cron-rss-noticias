"""Memoria de noticias ya vistas.

Un feed RSS no puede contener solo lo que apareció en la última corrida: quien
lo lee cada seis horas vería un feed casi vacío y se perdería todo lo demás.
Por eso los feeds se construyen sobre el historial acumulado.

Además resuelve dos cosas que se notan del lado del lector:

- **guid estable.** La misma nota conserva su id entre corridas, así ningún
  lector la muestra dos veces como nueva.
- **fecha de primera detección.** Si una fuente republica una nota vieja, no se
  la vuelve a poner arriba de todo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..modelos import Noticia
from ..util import fechas


def cargar(ruta: Path) -> List[Noticia]:
    """Historial guardado. Un archivo corrupto no rompe la corrida: se pierde
    la memoria, que se reconstruye sola en las siguientes."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return []
    crudas = datos.get("noticias") if isinstance(datos, dict) else None
    if not isinstance(crudas, list):
        return []
    salida: List[Noticia] = []
    for cruda in crudas:
        try:
            salida.append(Noticia.desde_dict(cruda))
        except Exception:
            continue
    return salida


def _mas_completa(nueva: Noticia, vieja: Noticia) -> Noticia:
    """Actualiza la versión guardada con lo que la nueva corrida agregó.

    Se conserva la fecha original (`publicado_en` y `detectado_en` de la vieja):
    una nota no se vuelve reciente porque otro medio la republique. Lo que sí
    se acumula son las fuentes: es la señal de importancia del sistema.
    """
    conocidas = {f.id for f in vieja.tambien_en}
    for fuente in nueva.tambien_en:
        if fuente.id not in conocidas and fuente.id != vieja.fuente_id:
            vieja.tambien_en.append(fuente)
            conocidas.add(fuente.id)

    vieja.cantidad_fuentes = 1 + len(vieja.tambien_en)
    if len(nueva.resumen) > len(vieja.resumen):
        vieja.resumen = nueva.resumen
    if not vieja.imagen_url and nueva.imagen_url:
        vieja.imagen_url = nueva.imagen_url
        vieja.imagenes = nueva.imagenes
    # La importancia puede haber subido al aparecer en más medios.
    vieja.importancia = max(vieja.importancia, nueva.importancia)
    for region in nueva.regiones:
        if region not in vieja.regiones:
            vieja.regiones.append(region)
    return vieja


def combinar(
    previas: Iterable[Noticia],
    nuevas: Iterable[Noticia],
    dias: float = 7.0,
    maximo: int = 4000,
) -> tuple[List[Noticia], int]:
    """Une historial y corrida actual. Devuelve (historial, cuántas eran nuevas)."""
    por_id: Dict[str, Noticia] = {n.id: n for n in previas}
    estrenos = 0

    for noticia in nuevas:
        existente = por_id.get(noticia.id)
        if existente is None:
            por_id[noticia.id] = noticia
            estrenos += 1
        else:
            por_id[noticia.id] = _mas_completa(noticia, existente)

    referencia = fechas.ahora()
    vigentes = [
        n for n in por_id.values()
        if fechas.horas_desde(n.publicado_en, referencia) <= dias * 24
    ]
    vigentes.sort(key=lambda n: (n.publicado_en or "", n.importancia), reverse=True)
    return vigentes[:maximo], estrenos


def guardar(ruta: Path, noticias: List[Noticia], generado_en: str) -> None:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "generado_en": generado_en,
        "total": len(noticias),
        "noticias": [n.a_dict() for n in noticias],
    }
    destino.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
