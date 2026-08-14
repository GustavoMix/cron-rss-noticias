"""Lector RSS, con la red simulada.

Se prueba contra XML real de los dos formatos que llegan en la práctica (RSS
2.0 y Atom) y contra las respuestas HTTP que importan: 304, 404 y 5xx.
"""

import asyncio

import httpx
import pytest

from noticias.config import Fuente
from noticias.fuentes.rss import ErrorDeFeed, leer_fuentes, leer_una

AJUSTES_RSS = {"max_items_por_fuente": 40, "concurrencia": 4, "usar_cache_condicional": True}
AJUSTES_RED = {"timeout_segundos": 5, "reintentos": 0, "user_agent": "TestBot/1.0"}

RSS_2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Medio de prueba</title>
    <link>https://medio.test/</link>
    <description>Noticias</description>
    <item>
      <title>Sube la tensi&#243;n entre A &amp; B tras la cumbre</title>
      <link>https://medio.test/nota-1?utm_source=rss</link>
      <description>&lt;p&gt;Resumen con &lt;b&gt;HTML&lt;/b&gt; adentro.&lt;/p&gt;</description>
      <pubDate>Thu, 14 Aug 2026 09:30:00 GMT</pubDate>
      <author>redaccion@medio.test</author>
      <category>Internacional</category>
      <media:content url="https://medio.test/foto.jpg" type="image/jpeg"/>
    </item>
    <item>
      <title>Segunda nota</title>
      <link>https://medio.test/nota-2</link>
      <pubDate>Thu, 14 Aug 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Medio Atom</title>
  <entry>
    <title>Una nota en Atom</title>
    <link href="https://atom.test/nota"/>
    <updated>2026-08-14T09:00:00Z</updated>
    <summary>Resumen atom.</summary>
  </entry>
</feed>
"""


def fuente(url="https://medio.test/rss.xml", **kwargs):
    base = dict(id="rss_test", nombre="Medio de prueba", tipo="rss", url=url,
                idioma="es", categoria="mundo", region="Global", peso=4)
    base.update(kwargs)
    return Fuente(**base)


def cliente_que_responde(manejador):
    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_parsea_rss_2_con_todos_los_campos():
    cliente = cliente_que_responde(lambda p: httpx.Response(200, content=RSS_2))
    items, resultado, _ = leer_una(cliente, fuente(), AJUSTES_RSS, AJUSTES_RED)

    assert resultado.estado == "ok"
    assert len(items) == 2

    primero = items[0]
    assert primero.titulo == "Sube la tensión entre A & B tras la cumbre"
    assert primero.resumen == "Resumen con HTML adentro."   # sin etiquetas
    assert primero.publicado_en.startswith("2026-08-14T09:30:00")
    assert primero.imagenes == ["https://medio.test/foto.jpg"]
    assert primero.etiquetas == ["Internacional"]
    assert primero.peso_fuente == 4 and primero.tipo_fuente == "rss"


def test_parsea_atom():
    cliente = cliente_que_responde(lambda p: httpx.Response(200, content=ATOM))
    items, resultado, _ = leer_una(cliente, fuente(), AJUSTES_RSS, AJUSTES_RED)
    assert resultado.estado == "ok"
    assert items[0].titulo == "Una nota en Atom"
    assert items[0].publicado_en.startswith("2026-08-14T09:00:00")


def test_respeta_el_maximo_por_fuente():
    cliente = cliente_que_responde(lambda p: httpx.Response(200, content=RSS_2))
    items, _, _ = leer_una(cliente, fuente(), {**AJUSTES_RSS, "max_items_por_fuente": 1}, AJUSTES_RED)
    assert len(items) == 1


def test_un_304_no_trae_items_y_conserva_la_cache():
    """Es el camino barato: el feed no cambió desde la corrida anterior."""
    cliente = cliente_que_responde(lambda p: httpx.Response(304))
    cache = {"etag": 'W/"abc"'}
    items, resultado, cache_nueva = leer_una(cliente, fuente(), AJUSTES_RSS, AJUSTES_RED, cache)

    assert items == []
    assert resultado.estado == "sin_novedades"
    assert cache_nueva == cache


def test_manda_las_cabeceras_condicionales_que_tenia_guardadas():
    vistas = {}

    def manejador(peticion):
        vistas.update(peticion.headers)
        return httpx.Response(200, content=RSS_2)

    leer_una(cliente_que_responde(manejador), fuente(), AJUSTES_RSS, AJUSTES_RED,
             {"etag": 'W/"abc"', "last_modified": "Thu, 14 Aug 2026 09:00:00 GMT"})

    assert vistas["if-none-match"] == 'W/"abc"'
    assert vistas["if-modified-since"] == "Thu, 14 Aug 2026 09:00:00 GMT"
    assert vistas["user-agent"] == "TestBot/1.0"


def test_guarda_el_etag_que_devuelve_el_servidor():
    cliente = cliente_que_responde(
        lambda p: httpx.Response(200, content=RSS_2, headers={"ETag": 'W/"nuevo"'})
    )
    _, _, cache_nueva = leer_una(cliente, fuente(), AJUSTES_RSS, AJUSTES_RED)
    assert cache_nueva["etag"] == 'W/"nuevo"'


def test_un_404_es_error_de_feed():
    cliente = cliente_que_responde(lambda p: httpx.Response(404))
    with pytest.raises(ErrorDeFeed, match="404"):
        leer_una(cliente, fuente(), AJUSTES_RSS, AJUSTES_RED)


def test_xml_ilegible_es_error():
    cliente = cliente_que_responde(lambda p: httpx.Response(200, content=b"no soy xml"))
    with pytest.raises(ErrorDeFeed):
        leer_una(cliente, fuente(), AJUSTES_RSS, AJUSTES_RED)


def test_una_fuente_caida_no_arrastra_a_las_demas():
    """Con 60 fuentes, que una se caiga es lo normal, no la excepción."""

    def manejador(peticion):
        if "rota" in str(peticion.url):
            return httpx.Response(500)
        return httpx.Response(200, content=RSS_2)

    # leer_fuentes abre su propio cliente, así que se parchea el transporte.
    import noticias.fuentes.rss as modulo

    original = httpx.Client

    def cliente_parcheado(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(manejador)
        return original(*args, **kwargs)

    modulo.httpx.Client = cliente_parcheado
    try:
        items, resultados, _ = asyncio.run(leer_fuentes(
            [fuente(id="rss_ok"), fuente(id="rss_rota", url="https://rota.test/rss.xml")],
            AJUSTES_RSS, AJUSTES_RED,
        ))
    finally:
        modulo.httpx.Client = original

    estados = {r.fuente_id: r.estado for r in resultados}
    assert estados == {"rss_ok": "ok", "rss_rota": "error"}
    assert len(items) == 2  # las de la fuente sana llegaron igual
