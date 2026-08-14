"""Normalización, deduplicación y clasificación."""

from noticias.proceso import clasificador, deduplicador, normalizador
from noticias.util import texto as t

AJUSTES = {"antiguedad_maxima_horas": 96, "titulo_minimo_caracteres": 18}
AHORA = "2026-08-14T12:00:00+00:00"


def normalizar_uno(item):
    return normalizador.normalizar_item(item, AJUSTES, AHORA)


# --- normalización --------------------------------------------------------

def test_la_url_se_canoniza_al_normalizar(item):
    noticia = normalizar_uno(item(url="https://demo.test/nota-1?utm_source=fb&fbclid=abc"))
    assert noticia.url == "https://demo.test/nota-1"


def test_titulo_demasiado_corto_se_descarta(item):
    assert normalizar_uno(item(titulo="Video", texto="")) is None


def test_titulo_de_interfaz_de_facebook_se_descarta(item):
    assert normalizar_uno(item(titulo="Iniciar sesión", texto="")) is None


def test_sin_fecha_se_usa_el_momento_de_deteccion(item):
    noticia = normalizar_uno(item(publicado_en=None))
    assert noticia.publicado_en == AHORA


def test_fecha_relativa_de_facebook_se_entiende(item):
    noticia = normalizar_uno(item(publicado_en="hace 3 h"))
    assert noticia.publicado_en.startswith("2026-08-14T")


def test_las_notas_muy_viejas_no_pasan(item):
    noticias, descartes = normalizador.normalizar(
        [item(publicado_en="2026-01-01T00:00:00+00:00")], AJUSTES, AHORA
    )
    assert noticias == []
    assert descartes["muy_vieja"] == 1


def test_el_id_es_estable_entre_corridas(item):
    a = normalizar_uno(item())
    b = normalizar_uno(item(publicado_en="2026-08-14T11:00:00+00:00"))
    assert a.id == b.id  # misma URL, mismo id


# --- deduplicación --------------------------------------------------------

def test_misma_url_desde_dos_fuentes_colapsa(item):
    noticias = [
        normalizar_uno(item(fuente_id="rss_a", fuente_nombre="A", peso_fuente=5)),
        normalizar_uno(item(fuente_id="fb_b", fuente_nombre="B", tipo_fuente="facebook")),
    ]
    agrupadas = deduplicador.agrupar(noticias)
    assert len(agrupadas) == 1
    assert agrupadas[0].cantidad_fuentes == 2
    assert agrupadas[0].fuente_id == "rss_a"  # gana el de más peso


def test_titulares_parecidos_de_medios_distintos_colapsan(item):
    noticias = [
        normalizar_uno(item(
            fuente_id="rss_a", fuente_nombre="A", url="https://a.test/1",
            titulo="El banco central sube la tasa de interés al ocho por ciento",
        )),
        normalizar_uno(item(
            fuente_id="rss_b", fuente_nombre="B", url="https://b.test/9",
            titulo="El banco central sube la tasa de interés hasta el ocho por ciento",
        )),
    ]
    agrupadas = deduplicador.agrupar(noticias, umbral=0.5)
    assert len(agrupadas) == 1
    assert [f.nombre for f in agrupadas[0].tambien_en] == ["B"]


def test_dos_notas_del_mismo_medio_no_se_fusionan(item):
    """Un medio siguiendo su propia historia publica títulos parecidos a
    propósito; fusionarlos escondería la actualización."""
    noticias = [
        normalizar_uno(item(url="https://a.test/1", titulo="Sube la tasa de interés al ocho por ciento")),
        normalizar_uno(item(url="https://a.test/2", titulo="Sube la tasa de interés al ocho por ciento hoy")),
    ]
    assert len(deduplicador.agrupar(noticias, umbral=0.5)) == 2


def test_titulares_distintos_no_se_fusionan(item):
    noticias = [
        normalizar_uno(item(fuente_id="a", url="https://a.test/1",
                            titulo="Terremoto de magnitud siete sacude la costa del Pacífico")),
        normalizar_uno(item(fuente_id="b", url="https://b.test/1",
                            titulo="El festival de cine premia una película documental argentina")),
    ]
    assert len(deduplicador.agrupar(noticias, umbral=0.5)) == 2


def test_fuera_de_la_ventana_de_tiempo_no_se_fusionan(item):
    noticias = [
        normalizar_uno(item(fuente_id="a", url="https://a.test/1",
                            titulo="La cumbre climática cierra con un acuerdo sobre emisiones",
                            publicado_en="2026-08-14T10:00:00+00:00")),
        normalizar_uno(item(fuente_id="b", url="https://b.test/1",
                            titulo="La cumbre climática cierra con un acuerdo sobre las emisiones",
                            publicado_en="2026-08-10T10:00:00+00:00")),
    ]
    assert len(deduplicador.agrupar(noticias, umbral=0.5, ventana_horas=36)) == 2


# --- clasificación --------------------------------------------------------

def test_el_texto_puede_ganarle_a_la_categoria_de_la_fuente(item):
    noticia = clasificador.clasificar_una(normalizar_uno(item(
        categoria_fuente="mundo",
        titulo="El Real Madrid gana la final de la Champions con un gol en el descuento",
        resumen="El equipo se consagró tras la definición del partido de fútbol.",
    )))
    assert noticia.categoria == "deportes"


def test_sin_señales_se_respeta_la_categoria_de_la_fuente(item):
    noticia = clasificador.clasificar_una(normalizar_uno(item(
        categoria_fuente="cultura",
        titulo="Una jornada tranquila en la ciudad según los vecinos consultados",
        resumen="Sin novedades relevantes durante la mañana.",
    )))
    assert noticia.categoria == "cultura"


def test_la_region_sale_del_texto(item):
    noticia = clasificador.clasificar_una(normalizar_uno(item(
        titulo="El gobierno de Japón anuncia un plan de inversión en Tokio",
        resumen="La medida fue confirmada por el primer ministro.",
    )))
    assert "Asia" in noticia.regiones


def test_mas_medios_significa_mas_importancia(item):
    sola = clasificador.clasificar_una(normalizar_uno(item()))
    coral = normalizar_uno(item())
    coral.cantidad_fuentes = 4
    coral = clasificador.clasificar_una(coral)
    assert coral.importancia > sola.importancia


# --- utilidades de texto --------------------------------------------------

def test_la_url_publicada_conserva_el_host_tal_cual():
    assert t.canonizar_url("https://www.demo.test/nota?utm_source=x") == "https://www.demo.test/nota"


def test_la_clave_de_comparacion_ignora_www_y_barra_final():
    assert t.clave_url("https://www.demo.test/nota/") == t.clave_url("https://demo.test/nota")


def test_la_misma_nota_con_y_sin_www_es_un_solo_item(item):
    noticias = [
        normalizar_uno(item(fuente_id="a", url="https://www.demo.test/nota/")),
        normalizar_uno(item(fuente_id="b", url="https://demo.test/nota")),
    ]
    assert len(deduplicador.agrupar(noticias)) == 1


def test_similitud_reconoce_titulares_equivalentes():
    a = "La cumbre climática cierra con acuerdo sobre emisiones"
    b = "Cierra la cumbre climática con un acuerdo sobre las emisiones"
    assert t.similitud(a, b) > 0.5


def test_limpiar_html_saca_etiquetas_y_entidades():
    assert t.limpiar_html("<p>Uno &amp; dos</p>") == "Uno & dos"
