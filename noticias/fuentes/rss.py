"""Lector de fuentes RSS/Atom.

Un feed RSS es un archivo estático servido por CDN: no hay límite por IP, no
hay navegador, no hay bloqueo. Por eso acá sí se pide en paralelo y con
concurrencia alta — todo lo contrario a Facebook, que vive en su propio módulo
justamente para que estas dos políticas no se contaminen entre sí.

Se usa caché condicional (ETag / Last-Modified): si el feed no cambió desde la
corrida anterior, el servidor contesta 304 sin cuerpo. Con ~60 fuentes cada
hora eso es la diferencia entre ser un lector normal y ser una molestia.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Tuple

import feedparser
import httpx

from ..config import Fuente
from ..modelos import ItemCrudo, ResultadoFuente
from ..util import fechas, texto as t

# Campos donde los distintos generadores de feeds esconden la imagen principal.
_CLAVES_IMAGEN = ("media_content", "media_thumbnail", "links", "enclosures")


class ErrorDeFeed(RuntimeError):
    """El feed no se pudo descargar o no se pudo interpretar."""


def _cabeceras(ajustes_red: Dict[str, Any], cache: Dict[str, str] | None) -> Dict[str, str]:
    cabeceras = {
        "User-Agent": str(ajustes_red.get("user_agent", "NoticiasMundoBot/1.0")),
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        "Accept-Language": "es,en;q=0.8",
    }
    if cache:
        if cache.get("etag"):
            cabeceras["If-None-Match"] = cache["etag"]
        if cache.get("last_modified"):
            cabeceras["If-Modified-Since"] = cache["last_modified"]
    return cabeceras


def _descargar(
    cliente: httpx.Client,
    fuente: Fuente,
    ajustes_red: Dict[str, Any],
    cache: Dict[str, str] | None,
) -> Tuple[bytes | None, Dict[str, str]]:
    """Devuelve (cuerpo, cache_nueva). cuerpo None significa 304: sin cambios."""
    reintentos = max(0, int(ajustes_red.get("reintentos", 2)))
    espera = float(ajustes_red.get("espera_reintento_segundos", 3))
    ultimo_error: Exception | None = None

    for intento in range(reintentos + 1):
        try:
            respuesta = cliente.get(
                fuente.url,
                headers=_cabeceras(ajustes_red, cache),
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            ultimo_error = exc
            if intento < reintentos:
                time.sleep(espera * (intento + 1))
            continue

        if respuesta.status_code == 304:
            return None, dict(cache or {})

        if respuesta.status_code >= 400:
            ultimo_error = ErrorDeFeed(f"HTTP {respuesta.status_code}")
            # 4xx no mejora reintentando; 5xx y 429 sí pueden ser pasajeros.
            if respuesta.status_code < 500 and respuesta.status_code != 429:
                break
            if intento < reintentos:
                time.sleep(espera * (intento + 1))
            continue

        cache_nueva = {}
        if respuesta.headers.get("etag"):
            cache_nueva["etag"] = respuesta.headers["etag"]
        if respuesta.headers.get("last-modified"):
            cache_nueva["last_modified"] = respuesta.headers["last-modified"]
        return respuesta.content, cache_nueva

    raise ErrorDeFeed(str(ultimo_error) if ultimo_error else "descarga fallida")


def _imagen_de_entrada(entrada: Any) -> List[str]:
    urls: List[str] = []
    for clave in _CLAVES_IMAGEN:
        for elemento in entrada.get(clave, []) or []:
            if not isinstance(elemento, dict):
                continue
            tipo = str(elemento.get("type", ""))
            url = elemento.get("url") or elemento.get("href")
            if not url:
                continue
            es_imagen = tipo.startswith("image/") or elemento.get("medium") == "image"
            if clave in ("media_content", "media_thumbnail"):
                es_imagen = es_imagen or not tipo
            if es_imagen and url not in urls:
                urls.append(url)
    return urls[:6]


def _fecha_de_entrada(entrada: Any) -> str | None:
    for clave in ("published", "updated", "created", "pubDate"):
        valor = entrada.get(clave)
        momento = fechas.parsear(valor)
        if momento:
            return fechas.a_iso(momento)
    for clave in ("published_parsed", "updated_parsed"):
        estructura = entrada.get(clave)
        if estructura:
            try:
                import calendar
                from datetime import datetime

                marca = calendar.timegm(estructura)
                return fechas.a_iso(datetime.fromtimestamp(marca, fechas.UTC))
            except Exception:
                continue
    return None


def _item_desde_entrada(entrada: Any, fuente: Fuente) -> ItemCrudo | None:
    titulo = t.limpiar_html(entrada.get("title"))
    enlace = (entrada.get("link") or "").strip()
    if not titulo or not enlace:
        return None

    resumen_bruto = entrada.get("summary") or entrada.get("description") or ""
    contenido = ""
    for bloque in entrada.get("content", []) or []:
        if isinstance(bloque, dict) and bloque.get("value"):
            contenido = bloque["value"]
            break

    etiquetas = [
        t.compactar(x.get("term"))
        for x in (entrada.get("tags") or [])
        if isinstance(x, dict) and x.get("term")
    ]

    return ItemCrudo(
        fuente_id=fuente.id,
        fuente_nombre=fuente.nombre,
        fuente_url=fuente.url,
        url=enlace,
        titulo=titulo,
        resumen=t.limpiar_html(resumen_bruto),
        texto=t.limpiar_html(contenido or resumen_bruto),
        publicado_en=_fecha_de_entrada(entrada),
        autor=t.compactar(entrada.get("author")) or None,
        idioma=fuente.idioma,
        categoria_fuente=fuente.categoria,
        region_fuente=fuente.region,
        tipo_fuente="rss",
        peso_fuente=fuente.peso,
        imagenes=_imagen_de_entrada(entrada),
        etiquetas=etiquetas[:8],
    )


def leer_una(
    cliente: httpx.Client,
    fuente: Fuente,
    ajustes_rss: Dict[str, Any],
    ajustes_red: Dict[str, Any],
    cache: Dict[str, str] | None = None,
) -> Tuple[List[ItemCrudo], ResultadoFuente, Dict[str, str]]:
    inicio = time.monotonic()
    usar_cache = bool(ajustes_rss.get("usar_cache_condicional", True))
    cuerpo, cache_nueva = _descargar(cliente, fuente, ajustes_red, cache if usar_cache else None)
    duracion = int((time.monotonic() - inicio) * 1000)

    if cuerpo is None:
        return [], ResultadoFuente(fuente.id, "sin_novedades", 0, None, duracion), cache_nueva

    analizado = feedparser.parse(cuerpo)
    # bozo indica XML mal formado; feedparser igual suele recuperar entradas,
    # así que solo es error si además no sacó ninguna.
    if analizado.bozo and not analizado.entries:
        motivo = getattr(analizado, "bozo_exception", "XML ilegible")
        raise ErrorDeFeed(f"feed ilegible: {motivo}")

    maximo = int(ajustes_rss.get("max_items_por_fuente", 40))
    items: List[ItemCrudo] = []
    for entrada in analizado.entries[:maximo]:
        item = _item_desde_entrada(entrada, fuente)
        if item:
            items.append(item)

    estado = "ok" if items else "sin_novedades"
    return items, ResultadoFuente(fuente.id, estado, len(items), None, duracion), cache_nueva


async def leer_fuentes(
    fuentes: List[Fuente],
    ajustes_rss: Dict[str, Any],
    ajustes_red: Dict[str, Any],
    cache: Dict[str, Dict[str, str]] | None = None,
) -> Tuple[List[ItemCrudo], List[ResultadoFuente], Dict[str, Dict[str, str]]]:
    """Lee todas las fuentes RSS en paralelo, con un tope de concurrencia.

    Una fuente que falla no arrastra al resto: su error queda registrado en el
    ResultadoFuente correspondiente y la corrida sigue.
    """
    if not fuentes:
        return [], [], dict(cache or {})

    cache = dict(cache or {})
    limite = asyncio.Semaphore(max(1, int(ajustes_rss.get("concurrencia", 8))))
    timeout = float(ajustes_red.get("timeout_segundos", 20))

    items: List[ItemCrudo] = []
    resultados: List[ResultadoFuente] = []
    cache_nueva: Dict[str, Dict[str, str]] = {}

    with httpx.Client(timeout=timeout, http2=False) as cliente:

        async def trabajar(fuente: Fuente) -> None:
            async with limite:
                try:
                    propios, resultado, entrada_cache = await asyncio.to_thread(
                        leer_una, cliente, fuente, ajustes_rss, ajustes_red, cache.get(fuente.id)
                    )
                    items.extend(propios)
                    resultados.append(resultado)
                    if entrada_cache:
                        cache_nueva[fuente.id] = entrada_cache
                except Exception as exc:
                    resultados.append(
                        ResultadoFuente(fuente.id, "error", 0, t.compactar(str(exc))[:300])
                    )
                    # Sin caché nueva: la próxima corrida vuelve a pedir completo.
                    if fuente.id in cache:
                        cache_nueva[fuente.id] = cache[fuente.id]

        await asyncio.gather(*(trabajar(f) for f in fuentes))

    return items, resultados, cache_nueva
