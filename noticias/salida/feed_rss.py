"""Generación de los feeds RSS 2.0 de salida.

Se arma con ElementTree y no con plantillas de texto: el escapado correcto de
`&`, `<` y comillas dentro de titulares es exactamente el tipo de detalle que
rompe un feed entero, y un titular con un `&` sin escapar es cuestión de horas.

Extensiones usadas, todas estándar y entendidas por cualquier lector:
    atom:  <atom:link rel="self">   — a dónde volver a buscar el feed
    media: <media:content>          — la imagen de la nota
    dc:    <dc:creator>             — autor
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List

from ..modelos import Noticia
from ..util import fechas, texto as t

NS_ATOM = "http://www.w3.org/2005/Atom"
NS_MEDIA = "http://search.yahoo.com/mrss/"
NS_DC = "http://purl.org/dc/elements/1.1/"

ET.register_namespace("atom", NS_ATOM)
ET.register_namespace("media", NS_MEDIA)
ET.register_namespace("dc", NS_DC)

GENERADOR = "cron-rss-noticias"


def _texto(padre: ET.Element, etiqueta: str, valor: str | None) -> ET.Element | None:
    if valor is None or valor == "":
        return None
    hijo = ET.SubElement(padre, etiqueta)
    hijo.text = str(valor)
    return hijo


def _descripcion(noticia: Noticia) -> str:
    """Cuerpo del item: resumen + de dónde salió.

    La atribución va en el cuerpo y no solo en <source> porque muchos lectores
    no muestran <source>, y en un agregador saber qué medio publicó qué es
    parte de la información, no un adorno.
    """
    partes = [noticia.resumen] if noticia.resumen else []

    medios = [noticia.fuente_nombre] + [f.nombre for f in noticia.tambien_en]
    vistos: List[str] = []
    for medio in medios:
        if medio and medio not in vistos:
            vistos.append(medio)

    if len(vistos) > 1:
        partes.append(f"Publicado también por: {', '.join(vistos[1:])}.")
    partes.append(f"Fuente: {vistos[0]}.")
    return " ".join(partes).strip()


def _item(canal: ET.Element, noticia: Noticia) -> None:
    item = ET.SubElement(canal, "item")
    _texto(item, "title", noticia.titulo)
    _texto(item, "link", noticia.url)
    _texto(item, "description", _descripcion(noticia))

    # guid estable e independiente de la URL: si un medio cambia el enlace, el
    # lector no vuelve a mostrar la nota como nueva.
    guid = ET.SubElement(item, "guid", {"isPermaLink": "false"})
    guid.text = f"{GENERADOR}:{noticia.id}"

    _texto(item, "pubDate", fechas.a_rfc2822(fechas.parsear(noticia.publicado_en)))

    for categoria in dict.fromkeys([noticia.categoria] + noticia.categorias):
        _texto(item, "category", categoria)
    for region in noticia.regiones[:3]:
        _texto(item, "category", region)

    if noticia.autor:
        creador = ET.SubElement(item, f"{{{NS_DC}}}creator")
        creador.text = noticia.autor

    fuente = ET.SubElement(item, "source", {"url": noticia.fuente_url})
    fuente.text = noticia.fuente_nombre

    if noticia.imagen_url:
        ET.SubElement(item, f"{{{NS_MEDIA}}}content", {
            "url": noticia.imagen_url,
            "medium": "image",
        })
        # enclosure es lo que entienden los lectores viejos. Sin `length` real
        # no se puede saber el tamaño sin descargar la imagen; 0 es el valor
        # convencional para "desconocido".
        ET.SubElement(item, "enclosure", {
            "url": noticia.imagen_url,
            "type": "image/jpeg",
            "length": "0",
        })


def construir(
    noticias: Iterable[Noticia],
    titulo: str,
    descripcion: str,
    enlace: str,
    url_propia: str,
    idioma: str = "es",
    generado_en: str | None = None,
) -> bytes:
    raiz = ET.Element("rss", {"version": "2.0"})
    canal = ET.SubElement(raiz, "channel")

    _texto(canal, "title", titulo)
    _texto(canal, "link", enlace)
    _texto(canal, "description", t.compactar(descripcion))
    _texto(canal, "language", idioma)
    _texto(canal, "generator", GENERADOR)
    _texto(canal, "docs", "https://www.rssboard.org/rss-specification")
    _texto(canal, "lastBuildDate", fechas.a_rfc2822(fechas.parsear(generado_en)))
    _texto(canal, "ttl", "30")

    ET.SubElement(canal, f"{{{NS_ATOM}}}link", {
        "href": url_propia,
        "rel": "self",
        "type": "application/rss+xml",
    })

    for noticia in noticias:
        _item(canal, noticia)

    ET.indent(raiz, space="  ")
    return ET.tostring(raiz, encoding="utf-8", xml_declaration=True)


def escribir(ruta: Path, contenido: bytes) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    return destino


def nombre_archivo(prefijo: str, valor: str) -> str:
    """Nombre de archivo seguro a partir de una categoría o región."""
    limpio = t.normalizar(valor).replace(" ", "-")
    return f"{prefijo}-{limpio}.xml" if prefijo else f"{limpio}.xml"


def generar_conjunto(
    noticias: List[Noticia],
    ajustes_sitio: Dict[str, Any],
    ajustes_salida: Dict[str, Any],
    directorio: Path,
    generado_en: str,
) -> List[Dict[str, Any]]:
    """Escribe todos los feeds y devuelve el índice de lo generado.

    Siempre se genera `mundo.xml` (todo) y `destacadas.xml`; los feeds por
    categoría y por región dependen de los ajustes y de tener material
    suficiente -un feed con dos notas es ruido, no un feed-.
    """
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)

    base = str(ajustes_sitio.get("base_feeds", "")).rstrip("/")
    enlace = str(ajustes_sitio.get("enlace", ""))
    idioma = str(ajustes_sitio.get("idioma", "es"))
    titulo_sitio = str(ajustes_sitio.get("titulo", "Noticias del Mundo"))
    descripcion_sitio = str(ajustes_sitio.get("descripcion", ""))

    por_feed = int(ajustes_salida.get("items_por_feed", 120))
    minimo = int(ajustes_salida.get("minimo_items_por_feed", 3))

    generados: List[Dict[str, Any]] = []

    def escribir_feed(archivo: str, titulo: str, descripcion: str, seleccion: List[Noticia]) -> None:
        if not seleccion:
            return
        contenido = construir(
            seleccion[:por_feed],
            titulo=titulo,
            descripcion=descripcion,
            enlace=enlace,
            url_propia=f"{base}/{archivo}" if base else archivo,
            idioma=idioma,
            generado_en=generado_en,
        )
        escribir(directorio / archivo, contenido)
        generados.append({
            "archivo": archivo,
            "titulo": titulo,
            "url": f"{base}/{archivo}" if base else archivo,
            "items": len(seleccion[:por_feed]),
        })

    por_fecha = sorted(noticias, key=lambda n: (n.publicado_en or ""), reverse=True)
    escribir_feed("mundo.xml", titulo_sitio, descripcion_sitio, por_fecha)

    destacadas = sorted(
        noticias, key=lambda n: (n.importancia, n.publicado_en or ""), reverse=True
    )
    escribir_feed(
        "destacadas.xml",
        f"{titulo_sitio} — Destacadas",
        "Las noticias que más medios distintos están publicando ahora mismo.",
        [n for n in destacadas if n.importancia >= 45] or destacadas[:40],
    )

    if ajustes_salida.get("generar_feeds_por_categoria", True):
        for categoria in sorted({n.categoria for n in noticias}):
            seleccion = [n for n in por_fecha if n.categoria == categoria]
            if len(seleccion) >= minimo:
                escribir_feed(
                    nombre_archivo("tema", categoria),
                    f"{titulo_sitio} — {categoria.capitalize()}",
                    f"Noticias de {categoria} de todas las fuentes configuradas.",
                    seleccion,
                )

    if ajustes_salida.get("generar_feeds_por_region", True):
        regiones = sorted({r for n in noticias for r in n.regiones})
        for region in regiones:
            seleccion = [n for n in por_fecha if region in n.regiones]
            if len(seleccion) >= minimo:
                escribir_feed(
                    nombre_archivo("region", region),
                    f"{titulo_sitio} — {region}",
                    f"Noticias sobre {region}.",
                    seleccion,
                )

    for idioma_feed in sorted({n.idioma for n in noticias}):
        seleccion = [n for n in por_fecha if n.idioma == idioma_feed]
        if len(seleccion) >= minimo:
            escribir_feed(
                nombre_archivo("idioma", idioma_feed),
                f"{titulo_sitio} — {idioma_feed.upper()}",
                f"Noticias en {idioma_feed}.",
                seleccion,
            )

    if ajustes_salida.get("generar_feed_por_fuente", False):
        for fuente_id in sorted({n.fuente_id for n in noticias}):
            seleccion = [n for n in por_fecha if n.fuente_id == fuente_id]
            if len(seleccion) >= minimo:
                escribir_feed(
                    nombre_archivo("fuente", fuente_id),
                    f"{titulo_sitio} — {seleccion[0].fuente_nombre}",
                    f"Noticias de {seleccion[0].fuente_nombre}.",
                    seleccion,
                )

    return generados
