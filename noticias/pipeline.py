"""Orquestación: las tres operaciones que ejecuta el cron.

    traer_rss()       lee un lote de feeds RSS        -> crudo/rss_*.json
    traer_facebook()  lee un grupo de páginas FB      -> crudo/fb_*.json
    construir()       junta los crudos y arma la salida -> feeds/ + datos/

Están separadas porque en CI cada una corre en un job distinto: los de
Facebook necesitan una IP propia cada uno (ver `planificador.py`), los de RSS
solo necesitan red, y el de construcción no necesita red en absoluto. Esa
separación también es lo que permite reprocesar todo sin volver a golpear
ninguna fuente: los crudos quedan en disco.

`correr_completo()` hace las tres cosas en un solo proceso. Sirve para probar
en local, pero desde una sola IP Facebook corta a la segunda o tercera página:
en producción va siempre el camino de tres jobs.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .config import Configuracion, Fuente
from .estado import historial as historial_estado, rotacion as rotacion_estado
from .fuentes import facebook as lector_facebook, rss as lector_rss
from .modelos import ItemCrudo, Noticia, ResultadoFuente
from .proceso import clasificador, deduplicador, normalizador
from .salida import feed_rss, indice, json_salida
from .util import fechas

RAIZ = Path(__file__).resolve().parents[1]


@dataclass
class Rutas:
    """Dónde escribe cada cosa. Agrupadas para poder redirigirlas en los tests."""

    datos: Path = RAIZ / "datos"
    feeds: Path = RAIZ / "feeds"
    crudo: Path = RAIZ / "crudo"

    @property
    def interno(self) -> Path:
        return self.datos / "_interno"

    @property
    def historial(self) -> Path:
        return self.interno / "historial.json"

    @property
    def rotacion(self) -> Path:
        return self.interno / "rotacion_facebook.json"

    @property
    def cache_rss(self) -> Path:
        return self.interno / "cache_rss.json"


# --------------------------------------------------------------------------
# Etapa 1: traer datos
# --------------------------------------------------------------------------

def _cargar_cache(ruta: Path) -> Dict[str, Dict[str, str]]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def _guardar_cache(ruta: Path, cache: Dict[str, Dict[str, str]]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


async def traer_rss(
    config: Configuracion,
    fuentes: List[Fuente],
    rutas: Rutas,
    salida: Path | None = None,
    etiqueta: str = "rss",
) -> Tuple[List[ItemCrudo], List[ResultadoFuente]]:
    momento = fechas.ahora_iso()
    cache = _cargar_cache(rutas.cache_rss)

    items, resultados, cache_nueva = await lector_rss.leer_fuentes(
        fuentes, config.bloque("rss"), config.bloque("red"), cache
    )

    # La caché condicional solo sirve si sobrevive entre corridas, y el único
    # job que escribe en el repo es el final. Por eso en modo fan-out los ETag
    # viajan dentro del crudo y los persiste `construir()`.
    if salida:
        json_salida.escribir_crudo(
            salida, items, resultados, momento, etiqueta,
            extra={"cache_rss": cache_nueva},
        )
    else:
        cache.update(cache_nueva)
        _guardar_cache(rutas.cache_rss, cache)

    return items, resultados


async def traer_facebook(
    config: Configuracion,
    fuentes: List[Fuente],
    rutas: Rutas,
    orden_grupo: int = 0,
    salida: Path | None = None,
    etiqueta: str = "facebook",
) -> Tuple[List[ItemCrudo], List[ResultadoFuente]]:
    momento = fechas.ahora_iso()
    items, resultados = await lector_facebook.scrapear_grupo(
        fuentes, config.bloque("facebook"), orden_grupo
    )
    if salida:
        json_salida.escribir_crudo(salida, items, resultados, momento, etiqueta)
    return items, resultados


# --------------------------------------------------------------------------
# Etapa 2: construir la salida
# --------------------------------------------------------------------------

def leer_crudos(
    rutas_crudo: Iterable[Path],
) -> Tuple[List[ItemCrudo], List[ResultadoFuente], Dict[str, Dict[str, str]]]:
    """Junta los archivos que dejaron los jobs de fan-out.

    Un archivo que falta o está roto se salta con aviso: que un job de CI se
    haya caído no puede impedir que se publique lo que sí llegó.
    """
    items: List[ItemCrudo] = []
    resultados: List[ResultadoFuente] = []
    cache_rss: Dict[str, Dict[str, str]] = {}

    for ruta in rutas_crudo:
        try:
            datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  aviso: no se pudo leer {ruta}: {exc}")
            continue
        for bruto in datos.get("items", []):
            try:
                items.append(ItemCrudo.desde_dict(bruto))
            except Exception:
                continue
        for bruto in datos.get("resultados", []):
            try:
                resultados.append(ResultadoFuente(**bruto))
            except Exception:
                continue
        entrada = (datos.get("extra") or {}).get("cache_rss")
        if isinstance(entrada, dict):
            cache_rss.update(entrada)

    return items, resultados, cache_rss


def procesar(
    items: Iterable[ItemCrudo],
    config: Configuracion,
    momento: str,
) -> Tuple[List[Noticia], Dict[str, int]]:
    """ItemCrudo -> Noticia lista para publicar. Sin tocar disco ni red."""
    ajustes = config.bloque("proceso")
    noticias, descartes = normalizador.normalizar(items, ajustes, momento)
    referencia = fechas.parsear(momento) or fechas.ahora()

    agrupadas = deduplicador.agrupar(
        noticias,
        umbral=float(ajustes.get("umbral_similitud", 0.5)),
        ventana_horas=float(ajustes.get("ventana_agrupado_horas", 36)),
    )
    descartes["agrupadas_como_duplicado"] = len(noticias) - len(agrupadas)

    return clasificador.clasificar(agrupadas, referencia), descartes


def construir(
    config: Configuracion,
    rutas_crudo: List[Path],
    rutas: Rutas,
) -> Dict[str, Any]:
    """Etapa final: crudos -> historial -> feeds + JSON. No usa red."""
    momento = fechas.ahora_iso()
    items, resultados, cache_rss = leer_crudos(rutas_crudo)
    print(f"Crudos leídos: {len(items)} publicaciones de {len(resultados)} fuentes.")

    if cache_rss:
        cache = _cargar_cache(rutas.cache_rss)
        cache.update(cache_rss)
        _guardar_cache(rutas.cache_rss, cache)

    noticias, descartes = procesar(items, config, momento)
    print(f"Procesadas: {len(noticias)} noticias únicas. Descartes: {descartes}")

    ajustes_salida = config.bloque("salida")
    previas = historial_estado.cargar(rutas.historial)
    acumuladas, estrenos = historial_estado.combinar(
        previas, noticias,
        dias=float(ajustes_salida.get("historial_dias", 7)),
        maximo=int(ajustes_salida.get("historial_max_items", 4000)),
    )
    historial_estado.guardar(rutas.historial, acumuladas, momento)
    print(f"Historial: {len(acumuladas)} noticias vigentes ({estrenos} nuevas en esta corrida).")

    feeds = feed_rss.generar_conjunto(
        acumuladas, config.bloque("sitio"), ajustes_salida, rutas.feeds, momento
    )
    indice.escribir_json(rutas.feeds / "indice.json", feeds, momento)
    indice.escribir_html(
        rutas.feeds / "index.html", feeds,
        str(config.bloque("sitio").get("titulo", "Noticias del Mundo")), momento,
    )
    print(f"Feeds generados: {len(feeds)} en {rutas.feeds}")

    json_salida.escribir_noticias(rutas.datos / "noticias.json", acumuladas, momento, feeds)
    json_salida.escribir_estado(
        rutas.datos / "estado_fuentes.json", config.fuentes, resultados, momento, descartes
    )

    # La rotación solo mira Facebook: es el único lector con cupo por IP.
    ids_facebook = {f.id for f in config.por_tipo("facebook", incluir_inactivas=True)}
    resultados_fb = [r for r in resultados if r.fuente_id in ids_facebook]
    if resultados_fb:
        rotacion_estado.actualizar(rutas.rotacion, resultados_fb, momento)

    resumen = {
        "momento": momento,
        "items_crudos": len(items),
        "noticias": len(noticias),
        "nuevas": estrenos,
        "historial": len(acumuladas),
        "feeds": len(feeds),
        "fuentes_ok": sum(1 for r in resultados if r.estado == "ok"),
        "fuentes_bloqueadas": sum(1 for r in resultados if r.estado == "bloqueada"),
        "fuentes_con_error": sum(1 for r in resultados if r.estado == "error"),
    }
    _imprimir_resumen(resumen, resultados)
    return resumen


def _imprimir_resumen(resumen: Dict[str, Any], resultados: List[ResultadoFuente]) -> None:
    print("\n" + "=" * 58)
    print("CORRIDA TERMINADA")
    print("=" * 58)
    print(f"  Publicaciones crudas : {resumen['items_crudos']}")
    print(f"  Noticias únicas      : {resumen['noticias']} ({resumen['nuevas']} nuevas)")
    print(f"  En el historial      : {resumen['historial']}")
    print(f"  Feeds generados      : {resumen['feeds']}")
    print(f"  Fuentes OK           : {resumen['fuentes_ok']}")
    print(f"  Fuentes bloqueadas   : {resumen['fuentes_bloqueadas']}")
    print(f"  Fuentes con error    : {resumen['fuentes_con_error']}")

    problemas = [r for r in resultados if r.estado in ("error", "bloqueada")]
    if problemas:
        print("\n  Revisar (detalle completo en datos/estado_fuentes.json):")
        for resultado in problemas[:15]:
            print(f"    [{resultado.estado}] {resultado.fuente_id}: {(resultado.error or '')[:110]}")
    if resumen["fuentes_bloqueadas"]:
        print(
            "\n  Bloqueadas = cupo de IP agotado, no fuentes rotas. "
            "Se corrige con más jobs/IPs o grupos más chicos, no con reintentos."
        )


# --------------------------------------------------------------------------
# Modo todo-en-uno (solo para pruebas locales)
# --------------------------------------------------------------------------

async def correr_completo(
    config: Configuracion,
    rutas: Rutas,
    con_facebook: bool = True,
) -> Dict[str, Any]:
    momento = fechas.ahora_iso()
    rutas.crudo.mkdir(parents=True, exist_ok=True)

    items_rss, resultados_rss = await traer_rss(config, config.por_tipo("rss"), rutas)

    items_fb: List[ItemCrudo] = []
    resultados_fb: List[ResultadoFuente] = []
    if con_facebook:
        fuentes_fb = config.por_tipo("facebook")
        print(
            f"\nAviso: leyendo {len(fuentes_fb)} páginas de Facebook desde una sola IP. "
            "Facebook corta cerca de la segunda; en CI cada grupo va en su propio job."
        )
        items_fb, resultados_fb = await traer_facebook(config, fuentes_fb, rutas)

    json_salida.escribir_crudo(
        rutas.crudo / "local.json", items_rss + items_fb,
        resultados_rss + resultados_fb, momento, "local",
    )
    return construir(config, [rutas.crudo / "local.json"], rutas)


def correr_completo_sync(config: Configuracion, rutas: Rutas, con_facebook: bool = True) -> Dict[str, Any]:
    return asyncio.run(correr_completo(config, rutas, con_facebook))
