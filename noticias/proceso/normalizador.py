"""Primera etapa del proceso: ItemCrudo -> Noticia.

Acá se decide qué entra al sistema. Todo lo que pase de esta etapa tiene:
título usable, URL canónica, id estable e idioma resuelto. Las etapas
siguientes pueden asumir eso y no volver a chequearlo.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from ..modelos import ItemCrudo, Noticia
from ..util import fechas, texto as t

# Titulares que son la interfaz de Facebook, no una noticia.
_TITULOS_INSERVIBLES = {
    "facebook", "inicia sesión", "iniciar sesión", "log in", "watch",
    "reels", "publicación", "post", "video", "en vivo", "live",
}


def _titulo_utilizable(titulo: str, minimo: int) -> bool:
    if len(titulo) < minimo:
        return False
    return t.normalizar(titulo) not in {t.normalizar(x) for x in _TITULOS_INSERVIBLES}


def _resumen(item: ItemCrudo, titulo: str) -> str:
    """El mejor texto disponible que no sea una repetición del título."""
    for candidato in (item.resumen, item.texto):
        limpio = t.compactar(candidato)
        if not limpio:
            continue
        if t.similitud(limpio, titulo) > 0.9 and len(limpio) <= len(titulo) + 20:
            continue
        return t.recortar(limpio, 600)
    return ""


def normalizar_item(
    item: ItemCrudo,
    ajustes: Dict[str, Any],
    detectado_en: str,
) -> Noticia | None:
    """Devuelve None si el item no sirve para publicarse."""
    titulo = t.compactar(item.titulo) or t.recortar(t.compactar(item.texto), 160)
    minimo = int(ajustes.get("titulo_minimo_caracteres", 18))
    if not _titulo_utilizable(titulo, minimo):
        return None

    url = t.canonizar_url(item.url)
    if not url.startswith(("http://", "https://")):
        return None

    momento = fechas.parsear(item.publicado_en)
    # Sin fecha confiable se usa el momento de detección: es lo que hace que la
    # nota aparezca ahora y no en un lugar arbitrario del feed.
    publicado_en = fechas.a_iso(momento) or detectado_en

    resumen = _resumen(item, titulo)
    idioma = item.idioma or t.detectar_idioma(f"{titulo} {resumen}")

    imagenes = [x for x in (item.imagenes or []) if x]

    return Noticia(
        # El id sale de la clave comparable, no de la URL publicada: así la
        # misma nota conserva su guid aunque una fuente la enlace con www y
        # otra sin www.
        id=t.id_estable(t.clave_url(url)),
        titulo=titulo,
        resumen=resumen,
        url=url,
        fuente_id=item.fuente_id,
        fuente_nombre=item.fuente_nombre,
        fuente_url=item.fuente_url,
        tipo_fuente=item.tipo_fuente,
        peso_fuente=int(item.peso_fuente or 3),
        publicado_en=publicado_en,
        detectado_en=detectado_en,
        idioma=idioma,
        categoria=item.categoria_fuente or "mundo",
        categorias=[],
        regiones=[item.region_fuente] if item.region_fuente else [],
        autor=item.autor,
        contenido=t.compactar(item.texto),
        fuente_icono_url=item.fuente_icono_url,
        fuente_region=item.region_fuente,
        fuente_categoria=item.categoria_fuente,
        imagen_url=imagenes[0] if imagenes else None,
        imagenes=imagenes[:6],
        video_url=item.video_url,
        etiquetas=[t.compactar(x) for x in (item.etiquetas or []) if t.compactar(x)][:8],
        reacciones=item.reacciones,
        comentarios=item.comentarios,
        compartidos=item.compartidos,
    )


def normalizar(
    items: Iterable[ItemCrudo],
    ajustes: Dict[str, Any],
    detectado_en: str,
) -> Tuple[List[Noticia], Dict[str, int]]:
    """Normaliza una tanda y devuelve además por qué se descartó cada cosa."""
    antiguedad_maxima = float(ajustes.get("antiguedad_maxima_horas", 96))
    referencia = fechas.parsear(detectado_en) or fechas.ahora()

    noticias: List[Noticia] = []
    descartes = {"sin_titulo_o_url": 0, "muy_vieja": 0}

    for item in items:
        noticia = normalizar_item(item, ajustes, detectado_en)
        if noticia is None:
            descartes["sin_titulo_o_url"] += 1
            continue
        if fechas.horas_desde(noticia.publicado_en, referencia) > antiguedad_maxima:
            descartes["muy_vieja"] += 1
            continue
        noticias.append(noticia)

    return noticias, descartes
