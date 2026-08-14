"""Historial y rotación: la memoria entre corridas.

Si el historial pierde items, el feed se vacía para quien lo lee cada varias
horas. Si la rotación castiga a las fuentes bloqueadas, esas fuentes no vuelven
a aparecer nunca.
"""

import json
from datetime import timedelta

from noticias.estado import historial, rotacion
from noticias.modelos import FuenteEnNoticia, Noticia, ResultadoFuente
from noticias.util import fechas


def noticia(id_, horas_atras=1.0, **kwargs):
    publicado = fechas.a_iso(fechas.ahora() - timedelta(hours=horas_atras))
    base = dict(
        id=id_, titulo=f"Titular {id_}", resumen="Resumen", url=f"https://demo.test/{id_}",
        fuente_id="rss_a", fuente_nombre="A", fuente_url="https://demo.test/",
        tipo_fuente="rss", peso_fuente=3, publicado_en=publicado,
        detectado_en=fechas.ahora_iso(), idioma="es", categoria="mundo",
    )
    base.update(kwargs)
    return Noticia(**base)


# --- historial ------------------------------------------------------------

def test_las_noticias_previas_siguen_en_el_feed():
    previas = [noticia("vieja", horas_atras=20)]
    acumuladas, nuevas = historial.combinar(previas, [noticia("nueva", horas_atras=1)])
    assert {n.id for n in acumuladas} == {"vieja", "nueva"}
    assert nuevas == 1


def test_una_nota_repetida_no_cuenta_como_nueva():
    previas = [noticia("misma", horas_atras=5)]
    _, nuevas = historial.combinar(previas, [noticia("misma", horas_atras=5)])
    assert nuevas == 0


def test_republicar_no_rejuvenece_una_nota():
    """Si un medio vuelve a publicar algo de ayer, no debe saltar al tope."""
    previas = [noticia("x", horas_atras=30)]
    acumuladas, _ = historial.combinar(previas, [noticia("x", horas_atras=0)])
    assert fechas.horas_desde(acumuladas[0].publicado_en) > 25


def test_las_fuentes_nuevas_se_acumulan_en_la_nota_ya_guardada():
    previas = [noticia("x")]
    entrante = noticia("x", tambien_en=[
        FuenteEnNoticia(id="rss_b", nombre="B", url="https://b.test/x", tipo="rss", peso=4)
    ])
    acumuladas, _ = historial.combinar(previas, [entrante])
    assert acumuladas[0].cantidad_fuentes == 2


def test_lo_viejo_se_poda():
    acumuladas, _ = historial.combinar([noticia("antigua", horas_atras=24 * 30)], [], dias=7)
    assert acumuladas == []


def test_el_historial_se_guarda_y_se_relee(tmp_path):
    ruta = tmp_path / "h.json"
    historial.guardar(ruta, [noticia("x")], fechas.ahora_iso())
    recuperadas = historial.cargar(ruta)
    assert [n.id for n in recuperadas] == ["x"]


def test_un_historial_corrupto_no_rompe_la_corrida(tmp_path):
    ruta = tmp_path / "h.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert historial.cargar(ruta) == []


# --- rotación -------------------------------------------------------------

def test_el_exito_se_registra_y_limpia_los_fallos(tmp_path):
    ruta = tmp_path / "r.json"
    rotacion.actualizar(ruta, [ResultadoFuente("fb_a", "error", 0, "boom")], fechas.ahora_iso())
    estado = rotacion.actualizar(ruta, [ResultadoFuente("fb_a", "ok", 5)], fechas.ahora_iso())
    assert estado["fb_a"]["fallos_seguidos"] == 0
    assert estado["fb_a"]["ultimo_exito"]


def test_un_bloqueo_no_marca_exito_ni_fallo_propio(tmp_path):
    ruta = tmp_path / "r.json"
    estado = rotacion.actualizar(
        ruta, [ResultadoFuente("fb_a", "bloqueada", 0, "IP quemada")], fechas.ahora_iso()
    )
    assert estado["fb_a"]["bloqueos"] == 1
    assert "ultimo_exito" not in estado["fb_a"]
    assert estado["fb_a"].get("fallos_seguidos", 0) == 0


def test_una_fuente_omitida_no_se_penaliza(tmp_path):
    ruta = tmp_path / "r.json"
    estado = rotacion.actualizar(ruta, [ResultadoFuente("fb_a", "omitida")], fechas.ahora_iso())
    assert estado["fb_a"]["ultimo_estado"] == "omitida"
    assert "bloqueos" not in estado["fb_a"]


def test_sin_novedades_igual_gasta_el_turno(tmp_path):
    """La página cargó: el cupo de la IP se usó, aunque no hubiera posts."""
    ruta = tmp_path / "r.json"
    estado = rotacion.actualizar(ruta, [ResultadoFuente("fb_a", "sin_novedades")], fechas.ahora_iso())
    assert estado["fb_a"]["ultimo_exito"]


def test_la_prioridad_sube_con_el_tiempo_sin_exito():
    vieja = {"fb_vieja": {"ultimo_exito": fechas.a_iso(fechas.ahora() - timedelta(hours=48))}}
    reciente = {"fb_reciente": {"ultimo_exito": fechas.ahora_iso()}}
    combinada = {**vieja, **reciente}
    assert (rotacion.prioridad("fb_vieja", 3, combinada)
            > rotacion.prioridad("fb_reciente", 3, combinada))


def test_una_fuente_nunca_vista_va_primero():
    assert rotacion.prioridad("desconocida", 3, {}) >= rotacion.HORAS_NUNCA_VISTA


def test_el_archivo_de_rotacion_queda_legible(tmp_path):
    ruta = tmp_path / "r.json"
    rotacion.actualizar(ruta, [ResultadoFuente("fb_a", "ok", 3)], fechas.ahora_iso())
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["fuentes"]["fb_a"]["ultimo_estado"] == "ok"
