"""Los feeds son el producto: si el XML sale mal, no hay error visible en CI,
simplemente ningún lector muestra nada. Por eso se valida el XML de verdad."""

import xml.etree.ElementTree as ET

from noticias.modelos import FuenteEnNoticia, Noticia
from noticias.salida import feed_rss

NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}


def noticia(**kwargs):
    base = dict(
        id="abc123",
        titulo="Un titular de prueba",
        resumen="Resumen de prueba.",
        url="https://demo.test/nota",
        fuente_id="rss_demo",
        fuente_nombre="Demo",
        fuente_url="https://demo.test/",
        tipo_fuente="rss",
        peso_fuente=4,
        publicado_en="2026-08-14T10:00:00+00:00",
        detectado_en="2026-08-14T12:00:00+00:00",
        idioma="es",
        categoria="mundo",
        categorias=["mundo"],
        regiones=["Europa"],
        importancia=50,
    )
    base.update(kwargs)
    return Noticia(**base)


def construir(noticias, **kwargs):
    opciones = dict(
        titulo="Feed de prueba",
        descripcion="Descripción",
        enlace="https://ejemplo.test/",
        url_propia="https://ejemplo.test/feeds/mundo.xml",
        generado_en="2026-08-14T12:00:00+00:00",
    )
    opciones.update(kwargs)
    return ET.fromstring(feed_rss.construir(noticias, **opciones))


def test_el_feed_tiene_los_elementos_que_exige_rss_2():
    canal = construir([noticia()]).find("channel")
    for etiqueta in ("title", "link", "description", "lastBuildDate"):
        assert canal.find(etiqueta) is not None, f"falta <{etiqueta}>"
    assert canal.find("atom:link", NS).get("rel") == "self"


def test_los_caracteres_especiales_del_titular_se_escapan():
    """Un '&' sin escapar rompe el feed entero, no solo ese item."""
    raiz = construir([noticia(titulo='Tensión entre A & B: "el acuerdo" <peligra>')])
    titulo = raiz.find("channel/item/title").text
    assert titulo == 'Tensión entre A & B: "el acuerdo" <peligra>'


def test_la_fecha_va_en_formato_rfc_2822():
    fecha = construir([noticia()]).find("channel/item/pubDate").text
    assert fecha.startswith("Fri, 14 Aug 2026")
    assert fecha.endswith("+0000")


def test_el_guid_no_es_permalink_y_es_estable():
    guid = construir([noticia()]).find("channel/item/guid")
    assert guid.get("isPermaLink") == "false"
    assert guid.text.endswith("abc123")


def test_la_atribucion_de_medios_aparece_en_la_descripcion():
    con_duplicados = noticia(
        tambien_en=[FuenteEnNoticia(id="b", nombre="Otro Medio", url="https://b.test/x",
                                    tipo="rss", peso=3)],
        cantidad_fuentes=2,
    )
    descripcion = construir([con_duplicados]).find("channel/item/description").text
    assert "Otro Medio" in descripcion
    assert "Fuente: Demo" in descripcion


def test_la_imagen_va_como_media_content_y_enclosure():
    item = construir([noticia(imagen_url="https://demo.test/foto.jpg")]).find("channel/item")
    assert item.find("media:content", NS).get("url") == "https://demo.test/foto.jpg"
    assert item.find("enclosure").get("url") == "https://demo.test/foto.jpg"


def test_se_generan_los_feeds_por_tema_region_e_idioma(tmp_path):
    noticias = [
        noticia(id=f"n{i}", url=f"https://demo.test/{i}", categoria="deportes",
                categorias=["deportes"], regiones=["Europa"])
        for i in range(5)
    ]
    generados = feed_rss.generar_conjunto(
        noticias,
        {"titulo": "T", "descripcion": "D", "enlace": "https://e.test/",
         "base_feeds": "https://e.test/feeds", "idioma": "es"},
        {"items_por_feed": 50, "minimo_items_por_feed": 3,
         "generar_feeds_por_categoria": True, "generar_feeds_por_region": True},
        tmp_path, "2026-08-14T12:00:00+00:00",
    )
    archivos = {g["archivo"] for g in generados}
    assert {"mundo.xml", "destacadas.xml", "tema-deportes.xml",
            "region-europa.xml", "idioma-es.xml"} <= archivos
    assert (tmp_path / "tema-deportes.xml").exists()
    # La URL self tiene que ser la pública, no la ruta local.
    assert all(g["url"].startswith("https://e.test/feeds/") for g in generados)


def test_un_tema_con_pocas_notas_no_genera_feed_propio(tmp_path):
    noticias = [noticia(id="n1", url="https://demo.test/1", categoria="cultura",
                        categorias=["cultura"])]
    generados = feed_rss.generar_conjunto(
        noticias,
        {"titulo": "T", "descripcion": "D", "enlace": "https://e.test/", "base_feeds": ""},
        {"items_por_feed": 50, "minimo_items_por_feed": 3},
        tmp_path, "2026-08-14T12:00:00+00:00",
    )
    assert "tema-cultura.xml" not in {g["archivo"] for g in generados}


def test_el_nombre_de_archivo_no_lleva_acentos_ni_espacios():
    assert feed_rss.nombre_archivo("region", "América Latina") == "region-america-latina.xml"
