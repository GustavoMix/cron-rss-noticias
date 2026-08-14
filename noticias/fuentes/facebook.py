"""Lector de páginas públicas de Facebook.

Contexto que explica cada decisión de este archivo
--------------------------------------------------
Facebook deja pasar aproximadamente **2 páginas públicas por IP** antes de
devolver la pantalla de bloqueo/login en lugar del contenido. Ese límite lo
lleva la IP de salida, no nuestro patrón de tráfico: no se corre con pausas más
largas, ni con otro User-Agent, ni con más scrolls.

La consecuencia de diseño es que este módulo **no intenta esquivar el bloqueo**.
Solo hace tres cosas:

1. Aprovecha bien los ~2 turnos buenos que tiene la IP del job (nada de abrir
   pestañas en paralelo, que quema los turnos de golpe).
2. Distingue "bloqueada" de "falló" y de "no publicó nada", porque el
   planificador necesita esa diferencia para repartir prioridades.
3. Se rinde rápido y limpio cuando la IP ya está quemada.

Todo lo demás -conseguir más IPs, achicar los grupos- se resuelve afuera, en
`planificador.py` y en el workflow. Ver `docs/ESTRATEGIA_FACEBOOK.md`.

No se inicia sesión, no se usan cookies de usuario y no se descargan streams de
video: solo se leen páginas públicas y se conserva el enlace público del post.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin

from ..config import Fuente
from ..modelos import ItemCrudo, ResultadoFuente
from ..util import fechas, texto as t

# Frases que solo aparecen cuando Facebook cortó el acceso público.
_SENALES_DE_BLOQUEO = (
    "temporarily blocked",
    "you're temporarily blocked",
    "temporalmente bloqueado",
    "olvidaste tu contraseña",
    "forgotten password",
    "correo electrónico o número de celular",
    "correo electronico o numero de celular",
    "email or phone number",
    "log in to continue",
    "inicia sesión para continuar",
)

# Texto de la interfaz que aparece dentro de cada post y no es del post.
_RUIDO_UI = {
    "me gusta", "comentar", "compartir", "enviar", "seguir", "seguidores",
    "reacciones", "todos", "más relevantes", "mas relevantes", "ver más",
    "ver mas", "facebook", "reproducir", "pausar", "silenciar",
    "activar sonido", "crear cuenta", "iniciar sesión", "like", "comment",
    "share", "most relevant", "see more", "log in", "create new account",
}

_PATRONES_PERMALINK = (
    "/posts/", "/videos/", "/reel/", "story_fbid=", "/permalink/", "watch?v=",
)


class BloqueoFacebook(RuntimeError):
    """Facebook devolvió la pantalla de bloqueo/login en vez del contenido.

    Es un estado distinto de un error: la fuente probablemente está bien y hay
    que reintentarla desde otra IP, no despriorizarla.
    """


def _limpiar_imagen(url: str | None) -> str | None:
    if not url or not url.strip().startswith(("http://", "https://")):
        return None
    url = url.strip()
    bajo = url.lower()
    # Sprites, emojis y assets estáticos de la interfaz.
    if any(x in bajo for x in ("emoji.php", "rsrc.php", "static.xx.fbcdn.net", "/images/emoji")):
        return None
    return url


def _limpiar_enlace(href: str | None) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith("/"):
        href = urljoin("https://www.facebook.com", href)
    if not href.startswith(("http://", "https://")):
        return None
    return href.replace("https://m.facebook.com/", "https://www.facebook.com/")


def _unir_fragmentos(fragmentos: List[str], nombre_fuente: str = "") -> str:
    """Arma el texto del post descartando botones, contadores y el nombre de la
    página repetido en cada tarjeta."""
    salida: List[str] = []
    vistos: set[str] = set()
    fuente = (nombre_fuente or "").strip().lower()

    for bruto in fragmentos:
        limpio = t.compactar(bruto)
        if not limpio:
            continue
        clave = limpio.lower().strip(" .:-")
        if clave in _RUIDO_UI or (fuente and clave == fuente):
            continue
        if re.fullmatch(r"\d+[.,]?\d*\s*[KkMm]?", limpio):
            continue
        if len(limpio) <= 3 and not any(c.isalpha() for c in limpio):
            continue
        if clave not in vistos:
            vistos.add(clave)
            salida.append(limpio)

    return "\n".join(salida).strip()


async def _texto_del_post(nodo, nombre_fuente: str) -> str:
    fragmentos: List[str] = []
    for selector in (
        '[data-ad-preview="message"]',
        '[data-ad-comet-preview="message"]',
        'div[dir="auto"]',
        'span[dir="auto"]',
    ):
        try:
            localizador = nodo.locator(selector)
            cantidad = min(await localizador.count(), 60)
            for i in range(cantidad):
                try:
                    valor = (await localizador.nth(i).inner_text(timeout=1200)).strip()
                except Exception:
                    continue
                if valor:
                    fragmentos.append(valor)
        except Exception:
            continue

    unido = _unir_fragmentos(fragmentos, nombre_fuente)
    if len(unido) >= 40:
        return unido

    try:
        completo = (await nodo.inner_text(timeout=3000)).strip()
    except Exception:
        return unido
    return _unir_fragmentos(completo.splitlines(), nombre_fuente)


async def _permalink(nodo, url_pagina: str) -> str:
    try:
        selector = ", ".join(f'a[href*="{p}"]' for p in _PATRONES_PERMALINK)
        enlaces = nodo.locator(selector)
        cantidad = min(await enlaces.count(), 20)
        for i in range(cantidad):
            href = _limpiar_enlace(await enlaces.nth(i).get_attribute("href"))
            if href and any(p in href.lower() for p in _PATRONES_PERMALINK):
                return href
    except Exception:
        pass
    return url_pagina


async def _imagenes_del_post(nodo) -> List[str]:
    urls: List[str] = []
    try:
        imagenes = nodo.locator("img[src]")
        cantidad = min(await imagenes.count(), 40)
        for i in range(cantidad):
            imagen = imagenes.nth(i)
            url = _limpiar_imagen(await imagen.get_attribute("src"))
            if not url or url in urls:
                continue
            alt = ((await imagen.get_attribute("alt")) or "").lower()
            if any(x in alt for x in ("emoji", "profile picture", "foto del perfil", "reaction")):
                continue
            try:
                tamano = await imagen.evaluate(
                    "(e)=>({w:e.naturalWidth||e.width||0,h:e.naturalHeight||e.height||0})"
                )
                ancho, alto = int(tamano.get("w", 0)), int(tamano.get("h", 0))
            except Exception:
                ancho = alto = 0
            # Avatares y iconos: por debajo de esto no es la foto de la nota.
            if ancho and alto and (ancho < 200 or alto < 130):
                continue
            urls.append(url)
    except Exception:
        pass
    return urls[:6]


def _numero_metrica(texto: str | None) -> int | None:
    """Convierte contadores sociales como ``1,2 mil`` / ``3.4K`` / ``2 M``.

    Facebook cambia bastante el marcado, por eso esto es deliberadamente
    tolerante y solo devuelve un valor cuando hay un número reconocible.
    """
    if not texto:
        return None
    bajo = texto.lower().replace("\u00a0", " ")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mil|k|m|mi|mill[oó]n(?:es)?|thousand)?", bajo)
    if not m:
        return None
    bruto = m.group(1)
    sufijo = (m.group(2) or "").lower()
    # Sin sufijo, 1.234 / 1,234 suele ser separador de miles en contadores.
    if not sufijo and re.fullmatch(r"\d{1,3}[.,]\d{3}", bruto):
        return int(bruto.replace(".", "").replace(",", ""))
    # Con sufijo, una sola coma/punto se trata como decimal: 1,2 mil / 1.4K.
    try:
        valor = float(bruto.replace(",", "."))
    except ValueError:
        return None
    if sufijo in {"mil", "k", "thousand"}:
        valor *= 1_000
    elif sufijo in {"m", "mi", "millón", "millon", "millones"}:
        valor *= 1_000_000
    return max(0, int(valor))


async def _metricas_del_post(nodo) -> Tuple[int | None, int | None, int | None]:
    """Recupera reacciones/comentarios/compartidos en modo best-effort.

    Se prefieren aria-label/title porque suelen contener el nombre de la
    métrica aun cuando el texto visible sea solo un número.
    """
    encontrados: Dict[str, int] = {}
    try:
        loc = nodo.locator("[aria-label], [title]")
        cantidad = min(await loc.count(), 100)
        for i in range(cantidad):
            el = loc.nth(i)
            texto = " ".join(filter(None, [
                await el.get_attribute("aria-label"),
                await el.get_attribute("title"),
            ])).strip()
            bajo = texto.lower()
            if not bajo:
                continue
            valor = _numero_metrica(texto)
            if valor is None:
                continue
            if any(x in bajo for x in ("reacci", "reaction", "reaç")):
                encontrados["reacciones"] = max(valor, encontrados.get("reacciones", 0))
            elif any(x in bajo for x in ("coment", "comment")):
                encontrados["comentarios"] = max(valor, encontrados.get("comentarios", 0))
            elif any(x in bajo for x in ("compart", "share")):
                encontrados["compartidos"] = max(valor, encontrados.get("compartidos", 0))
    except Exception:
        pass
    return (
        encontrados.get("reacciones"),
        encontrados.get("comentarios"),
        encontrados.get("compartidos"),
    )


async def _icono_de_pagina(pagina) -> str | None:
    """Intenta obtener una imagen representativa de la página/canal una vez.

    En páginas públicas, ``og:image`` suele ser la imagen que Facebook expone
    para compartir la propia página. Si Facebook cambia ese detalle, el campo
    simplemente queda ``null`` y la app puede usar su placeholder.
    """
    for selector in (
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        'link[rel="image_src"]',
    ):
        try:
            loc = pagina.locator(selector)
            if not await loc.count():
                continue
            atributo = "href" if selector.startswith("link") else "content"
            url = _limpiar_imagen(await loc.first.get_attribute(atributo))
            if url:
                return url
        except Exception:
            continue
    return None


async def _fecha_del_post(nodo) -> str | None:
    try:
        marcas = nodo.locator("abbr, time")
        if await marcas.count():
            primera = marcas.first
            valor = (
                await primera.get_attribute("datetime")
                or await primera.get_attribute("title")
                or (await primera.inner_text(timeout=1000)).strip()
            )
            if valor:
                return valor
    except Exception:
        pass
    # Facebook suele poner la fecha completa en el aria-label del permalink.
    try:
        enlaces = nodo.locator("a[aria-label], a[title]")
        cantidad = min(await enlaces.count(), 25)
        for i in range(cantidad):
            enlace = enlaces.nth(i)
            valor = (await enlace.get_attribute("aria-label")) or (await enlace.get_attribute("title"))
            if valor and fechas.parsear(valor):
                return valor.strip()
    except Exception:
        pass
    return None


async def _detectar_bloqueo(pagina) -> None:
    """Se llama SOLO cuando no se encontró ningún post.

    Chequearlo antes daba falsos positivos: Facebook incluye el formulario de
    login en el DOM de cualquier página pública para visitantes sin sesión,
    incluso cuando el feed real cargó perfectamente más arriba.
    """
    try:
        cuerpo = await pagina.locator("body").inner_text(timeout=7000)
    except Exception:
        return
    bajo = cuerpo.lower()
    if any(senal in bajo for senal in _SENALES_DE_BLOQUEO):
        vista_previa = t.compactar(cuerpo)[:200]
        raise BloqueoFacebook(
            f"Facebook ocultó el contenido público a esta IP. Vista previa: {vista_previa!r}"
        )


async def _enriquecer(contexto, item: ItemCrudo, timeout_ms: int) -> ItemCrudo:
    """Abre el permalink para recuperar el texto completo cuando la tarjeta del
    feed vino cortada. Cada apertura gasta cupo de la IP: se usa con cuentagotas."""
    if not item.url or item.url == item.fuente_url:
        return item

    pagina = await contexto.new_page()
    try:
        await pagina.goto(item.url, wait_until="domcontentloaded", timeout=timeout_ms)
        await pagina.wait_for_timeout(1000)

        partes: List[str] = []
        for selector in ('meta[property="og:description"]', 'meta[name="description"]'):
            try:
                localizador = pagina.locator(selector)
                if await localizador.count():
                    valor = (await localizador.first.get_attribute("content")) or ""
                    if valor:
                        partes.append(valor)
            except Exception:
                continue

        mejor = _unir_fragmentos(partes, item.fuente_nombre)
        if len(mejor) > len(item.texto):
            item.texto = mejor
            if len(mejor) > len(item.resumen):
                item.resumen = t.recortar(mejor, 400)

        try:
            og = pagina.locator('meta[property="og:image"]')
            if await og.count():
                imagen = _limpiar_imagen(await og.first.get_attribute("content"))
                if imagen and imagen not in item.imagenes:
                    item.imagenes.insert(0, imagen)
                    item.imagenes = item.imagenes[:6]
        except Exception:
            pass

        try:
            titulo_meta = pagina.locator('meta[property="og:title"]')
            if await titulo_meta.count():
                titulo = t.compactar((await titulo_meta.first.get_attribute("content")) or "")
                if len(titulo) > len(item.titulo):
                    item.titulo = titulo
        except Exception:
            pass
    except Exception:
        # El enriquecimiento es opcional por definición: si falla, el item
        # original sigue siendo válido.
        pass
    finally:
        await pagina.close()
    return item


async def _leer_pagina(fuente: Fuente, ajustes: Dict[str, Any], contexto) -> List[ItemCrudo]:
    maximo = int(ajustes.get("max_items_por_fuente", 12))
    scrolls = int(ajustes.get("scrolls", 2))
    espera = float(ajustes.get("espera_carga_segundos", 2.5))

    pagina = await contexto.new_page()
    try:
        await pagina.goto(fuente.url, wait_until="domcontentloaded", timeout=30000)
        await pagina.wait_for_timeout(int(espera * 1000))
        fuente_icono = await _icono_de_pagina(pagina)

        for _ in range(scrolls):
            try:
                if await pagina.locator('[role="article"]').count() >= maximo:
                    break
                await pagina.mouse.wheel(0, 2200)
                await pagina.wait_for_timeout(450)
            except Exception:
                break

        articulos = pagina.locator('[role="article"]')
        cantidad = min(await articulos.count(), maximo)

        items: List[ItemCrudo] = []
        for i in range(cantidad):
            nodo = articulos.nth(i)
            cuerpo = await _texto_del_post(nodo, fuente.nombre)
            if len(cuerpo) < 30:
                continue

            enlace = await _permalink(nodo, fuente.url)
            publicado = await _fecha_del_post(nodo)
            imagenes = await _imagenes_del_post(nodo)
            reacciones, comentarios, compartidos = await _metricas_del_post(nodo)

            primera_linea = cuerpo.split("\n", 1)[0]
            items.append(ItemCrudo(
                fuente_id=fuente.id,
                fuente_nombre=fuente.nombre,
                fuente_url=fuente.url,
                url=enlace,
                titulo=t.recortar(primera_linea, 180),
                resumen=t.recortar(cuerpo, 400),
                texto=cuerpo,
                publicado_en=fechas.a_iso(fechas.parsear(publicado)),
                idioma=fuente.idioma,
                categoria_fuente=fuente.categoria,
                region_fuente=fuente.region,
                tipo_fuente="facebook",
                peso_fuente=fuente.peso,
                fuente_icono_url=fuente_icono,
                imagenes=imagenes,
                video_url=enlace if any(x in enlace.lower() for x in ("/videos/", "/reel/", "watch?v=")) else None,
                reacciones=reacciones,
                comentarios=comentarios,
                compartidos=compartidos,
            ))

        if not items:
            await _detectar_bloqueo(pagina)
            return []

        if ajustes.get("enriquecer_posts", True):
            limite = int(ajustes.get("enriquecer_max_por_fuente", 2))
            timeout_ms = int(ajustes.get("enriquecer_timeout_ms", 12000))
            usados = 0
            for i, item in enumerate(items):
                if usados >= limite:
                    break
                if len(item.texto) < 140 and item.url != fuente.url:
                    items[i] = await _enriquecer(contexto, item, timeout_ms)
                    usados += 1

        # Dedup dentro de la propia página: Facebook repite el post fijado.
        vistos: set[Tuple[str, str]] = set()
        unicos: List[ItemCrudo] = []
        for item in items:
            clave = (item.url, item.texto[:200])
            if clave not in vistos:
                vistos.add(clave)
                unicos.append(item)
        return unicos[:maximo]
    finally:
        await pagina.close()


def proxy_para_grupo(orden: int) -> Dict[str, str] | None:
    """Elige un proxy de la lista NOTICIAS_PROXIES según el índice del grupo.

    Esta es la única palanca de "más IPs" que no depende de agregar jobs: si la
    variable trae N proxies, cada grupo sale por uno distinto y el cupo de ~2
    páginas por IP se multiplica por N. Si la variable está vacía -el caso
    normal- se usa la IP propia del runner, que ya es distinta en cada job.

    Formato: URLs separadas por coma, p. ej.
        http://usuario:clave@host1:8080,http://usuario:clave@host2:8080
    """
    bruto = os.environ.get("NOTICIAS_PROXIES", "").strip()
    if not bruto:
        return None
    lista = [x.strip() for x in bruto.split(",") if x.strip()]
    if not lista:
        return None
    elegido = lista[orden % len(lista)]
    return {"server": elegido}


async def scrapear_grupo(
    fuentes: List[Fuente],
    ajustes: Dict[str, Any],
    orden_grupo: int = 0,
) -> Tuple[List[ItemCrudo], List[ResultadoFuente]]:
    """Lee un grupo chico de páginas, una tras otra, en un solo navegador.

    Un grupo = un job de CI = una IP. Todo lo de acá adentro comparte ese cupo
    de ~2 páginas, así que el grupo tiene que ser chico; agrandarlo no hace más
    lento el bloqueo, solo pone más fuentes detrás de él.
    """
    if not fuentes:
        return [], []

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Falta Playwright. Instalá con: pip install -r requirements.txt && "
            "python -m playwright install --with-deps chromium"
        ) from exc

    pausa = float(ajustes.get("pausa_entre_fuentes_segundos", 9))
    pausa_bloqueo = float(ajustes.get("pausa_tras_bloqueo_segundos", 35))
    intentos = max(1, int(ajustes.get("intentos_por_fuente", 2)))
    seguir_tras_bloqueo = bool(ajustes.get("seguir_tras_bloqueo", True))

    items: List[ItemCrudo] = []
    resultados: List[ResultadoFuente] = []

    async with async_playwright() as motor:
        navegador = await motor.chromium.launch(
            headless=True,
            proxy=proxy_para_grupo(orden_grupo),
            args=[
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-renderer-backgrounding",
            ],
        )
        # Un solo contexto para todo el grupo: las cookies persisten de una
        # página a la siguiente, como en una navegación normal. Sin User-Agent
        # propio (el de Chromium real ya sirve) y con el viewport variado: que
        # los 15 jobs reporten exactamente 1280x900 agrupa la flota entera bajo
        # una misma huella aunque las IPs sean distintas.
        contexto = await navegador.new_context(
            locale="es-ES",
            timezone_id="UTC",
            viewport={
                "width": random.choice([1280, 1366, 1440, 1512, 1600]),
                "height": random.choice([800, 864, 900, 960]),
            },
            service_workers="block",
        )

        async def filtrar(ruta):
            tipo = ruta.request.resource_type
            url = ruta.request.url.lower()
            if tipo in {"font", "media"}:
                await ruta.abort()
                return
            if any(x in url for x in ("doubleclick.net", "google-analytics.com", "googletagmanager.com")):
                await ruta.abort()
                return
            await ruta.continue_()

        await contexto.route("**/*", filtrar)

        ip_quemada = False
        for indice, fuente in enumerate(fuentes):
            if ip_quemada and not seguir_tras_bloqueo:
                resultados.append(ResultadoFuente(
                    fuente.id, "omitida", 0,
                    "Omitida: Facebook ya había bloqueado a esta IP en esta corrida.",
                ))
                continue

            inicio = time.monotonic()
            bloqueo: BloqueoFacebook | None = None
            resultado: ResultadoFuente | None = None

            for intento in range(intentos):
                try:
                    propios = await _leer_pagina(fuente, ajustes, contexto)
                except BloqueoFacebook as exc:
                    bloqueo = exc
                    if intento < intentos - 1:
                        # Un bloqueo aislado puede ser la IP que le tocó al
                        # runner, no algo que hicimos: una espera larga y otro
                        # intento a veces alcanza.
                        await asyncio.sleep(pausa_bloqueo)
                    continue
                except Exception as exc:
                    resultado = ResultadoFuente(
                        fuente.id, "error", 0, t.compactar(str(exc))[:300],
                        int((time.monotonic() - inicio) * 1000),
                    )
                    break

                items.extend(propios)
                resultado = ResultadoFuente(
                    fuente.id,
                    "ok" if propios else "sin_novedades",
                    len(propios),
                    None,
                    int((time.monotonic() - inicio) * 1000),
                )
                bloqueo = None
                break

            if bloqueo is not None:
                ip_quemada = True
                resultado = ResultadoFuente(
                    fuente.id, "bloqueada", 0, t.compactar(str(bloqueo))[:300],
                    int((time.monotonic() - inicio) * 1000),
                )

            resultados.append(resultado)

            if indice < len(fuentes) - 1:
                # Tras un bloqueo conviene esperar más antes de la siguiente:
                # el job ya está levantado, esos segundos no cuestan nada y son
                # la única chance que le queda a la fuente que viene atrás.
                base = pausa_bloqueo if ip_quemada else pausa
                await asyncio.sleep(base * random.uniform(0.8, 1.4))

        await contexto.close()
        await navegador.close()

    return items, resultados
