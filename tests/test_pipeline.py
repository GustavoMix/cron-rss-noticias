"""Prueba de extremo a extremo del camino que corre en CI, sin red:
crudos de dos jobs -> construir() -> feeds + JSON.
"""

import json
import xml.etree.ElementTree as ET

import pytest

from noticias.config import cargar
from noticias.modelos import ResultadoFuente
from noticias.pipeline import Rutas, construir, leer_crudos
from noticias.salida import json_salida
from noticias.util import fechas


@pytest.fixture
def entorno(tmp_path):
    rutas = Rutas(datos=tmp_path / "datos", feeds=tmp_path / "feeds", crudo=tmp_path / "crudo")
    return cargar(), rutas


def escribir_crudo(rutas, nombre, items, resultados, extra=None):
    return json_salida.escribir_crudo(
        rutas.crudo / nombre, items, resultados, fechas.ahora_iso(), nombre, extra
    )


def test_corrida_completa_desde_dos_jobs(entorno, item):
    config, rutas = entorno

    # Job de RSS: dos medios distintos con la misma historia.
    crudo_rss = escribir_crudo(
        rutas, "rss_r01.json",
        [
            item(fuente_id="rss_bbc_world", fuente_nombre="BBC", url="https://bbc.test/1",
                 titulo="El banco central europeo sube la tasa de interés de referencia",
                 peso_fuente=5, publicado_en=fechas.ahora_iso()),
            item(fuente_id="rss_dw_es", fuente_nombre="DW", url="https://dw.test/9",
                 titulo="El banco central europeo sube la tasa de interés de referencia hoy",
                 peso_fuente=4, publicado_en=fechas.ahora_iso()),
        ],
        [ResultadoFuente("rss_bbc_world", "ok", 1), ResultadoFuente("rss_dw_es", "ok", 1)],
        extra={"cache_rss": {"rss_bbc_world": {"etag": "W/\"abc\""}}},
    )

    # Job de Facebook: una fuente OK y otra bloqueada por cupo de IP.
    crudo_fb = escribir_crudo(
        rutas, "fb_g01.json",
        [item(fuente_id="fb_bbc_news", fuente_nombre="BBC News", tipo_fuente="facebook",
              url="https://www.facebook.com/bbcnews/posts/123",
              titulo="Un terremoto de magnitud siete sacude la costa de Japón esta madrugada",
              peso_fuente=5, publicado_en=fechas.ahora_iso())],
        [ResultadoFuente("fb_bbc_news", "ok", 1),
         ResultadoFuente("fb_cnn", "bloqueada", 0, "IP sin cupo")],
    )

    resumen = construir(config, [crudo_rss, crudo_fb], rutas)

    # La misma historia contada por dos medios sale una sola vez.
    assert resumen["items_crudos"] == 3
    assert resumen["noticias"] == 2
    assert resumen["fuentes_bloqueadas"] == 1

    # Feeds escritos y bien formados.
    assert (rutas.feeds / "mundo.xml").exists()
    canal = ET.parse(rutas.feeds / "mundo.xml").getroot().find("channel")
    assert len(canal.findall("item")) == 2

    # Índice, JSON de consumo y diagnóstico.
    assert (rutas.feeds / "index.html").exists()
    indice = json.loads((rutas.feeds / "indice.json").read_text(encoding="utf-8"))
    assert indice["total"] >= 1

    noticias = json.loads((rutas.datos / "noticias.json").read_text(encoding="utf-8"))
    assert noticias["resumen"]["noticias"] == 2

    estado = json.loads((rutas.datos / "estado_fuentes.json").read_text(encoding="utf-8"))
    assert estado["resumen"]["bloqueadas"] == 1
    bloqueada = next(f for f in estado["fuentes"] if f["id"] == "fb_cnn")
    assert bloqueada["error"] == "IP sin cupo"

    # La rotación quedó registrada solo para Facebook.
    rot = json.loads(rutas.rotacion.read_text(encoding="utf-8"))["fuentes"]
    assert set(rot) == {"fb_bbc_news", "fb_cnn"}
    assert "ultimo_exito" not in rot["fb_cnn"]  # bloqueada no pierde prioridad

    # Los ETag que descubrió el job de RSS los persistió el job final.
    cache = json.loads(rutas.cache_rss.read_text(encoding="utf-8"))
    assert cache["rss_bbc_world"]["etag"]


def test_la_segunda_corrida_acumula_en_vez_de_reemplazar(entorno, item):
    config, rutas = entorno

    primero = escribir_crudo(
        rutas, "a.json",
        [item(fuente_id="rss_bbc_world", url="https://bbc.test/1",
              titulo="Primera noticia de la primera corrida del agregador",
              publicado_en=fechas.ahora_iso())],
        [ResultadoFuente("rss_bbc_world", "ok", 1)],
    )
    construir(config, [primero], rutas)

    segundo = escribir_crudo(
        rutas, "b.json",
        [item(fuente_id="rss_bbc_world", url="https://bbc.test/2",
              titulo="Segunda noticia, publicada en la corrida siguiente",
              publicado_en=fechas.ahora_iso())],
        [ResultadoFuente("rss_bbc_world", "ok", 1)],
    )
    resumen = construir(config, [segundo], rutas)

    assert resumen["noticias"] == 1      # esta corrida trajo una
    assert resumen["historial"] == 2     # el feed muestra las dos
    canal = ET.parse(rutas.feeds / "mundo.xml").getroot().find("channel")
    assert len(canal.findall("item")) == 2


def test_un_crudo_roto_no_frena_la_corrida(entorno, item, capsys):
    config, rutas = entorno
    roto = rutas.crudo / "roto.json"
    roto.parent.mkdir(parents=True, exist_ok=True)
    roto.write_text("{ no soy json", encoding="utf-8")

    bueno = escribir_crudo(
        rutas, "bueno.json",
        [item(fuente_id="rss_bbc_world", url="https://bbc.test/1",
              publicado_en=fechas.ahora_iso())],
        [ResultadoFuente("rss_bbc_world", "ok", 1)],
    )

    resumen = construir(config, [roto, bueno], rutas)
    assert resumen["noticias"] == 1
    assert "aviso" in capsys.readouterr().out


def test_leer_crudos_ignora_archivos_inexistentes():
    from pathlib import Path

    items, resultados, cache = leer_crudos([Path("/no/existe.json")])
    assert (items, resultados, cache) == ([], [], {})
