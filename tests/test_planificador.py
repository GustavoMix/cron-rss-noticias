"""El planificador es donde vive la estrategia de IPs, así que es lo que más
vale la pena blindar: si un cambio rompe el round-robin o agranda los grupos,
se pierden fuentes en silencio y solo se nota días después."""

from noticias.config import Fuente
from noticias.planificador import a_matriz, planificar_facebook, planificar_rss

import json


def fuentes(cantidad, tipo="facebook"):
    return [
        Fuente(id=f"f{i:02d}", nombre=f"F{i}", tipo=tipo, url=f"https://x.test/{i}")
        for i in range(cantidad)
    ]


def test_grupos_de_dos_no_pierden_ninguna_fuente():
    grupos = planificar_facebook(fuentes(30), {}, tamano_grupo=2)
    assert len(grupos) == 15
    assert all(g["cantidad"] == 2 for g in grupos)

    repartidas = [f for g in grupos for f in g["fuentes"].split(",")]
    assert sorted(repartidas) == sorted(f.id for f in fuentes(30))


def test_cantidad_impar_deja_un_grupo_incompleto_pero_no_descarta():
    grupos = planificar_facebook(fuentes(7), {}, tamano_grupo=2)
    assert len(grupos) == 4
    assert sum(g["cantidad"] for g in grupos) == 7


def test_las_mas_urgentes_caen_cada_una_en_un_grupo_distinto():
    """El primer turno de cada grupo es el que esquiva el bloqueo. Las dos
    fuentes más urgentes tienen que quedar en grupos separados, no juntas."""
    todas = fuentes(6)
    rotacion = {
        "f00": {"ultimo_exito": "2026-08-14T12:00:00+00:00"},  # recién vista
        "f01": {"ultimo_exito": "2026-08-14T12:00:00+00:00"},
        "f02": {"ultimo_exito": "2026-08-14T12:00:00+00:00"},
        "f03": {"ultimo_exito": "2026-08-14T12:00:00+00:00"},
        # f04 y f05 no tienen historial: son las que más tiempo llevan sin datos.
    }
    grupos = planificar_facebook(todas, rotacion, tamano_grupo=2)

    primeras = [g["fuentes"].split(",")[0] for g in grupos]
    assert "f04" in primeras and "f05" in primeras


def test_entre_dos_igual_de_atrasadas_va_primero_la_que_no_falla_sola():
    """Las dos llevan lo mismo sin traer datos, pero una viene fallando por su
    cuenta -página renombrada, borrada o privada-. El turno bueno es escaso:
    se lo lleva la que tiene chance de aprovecharlo."""
    todas = fuentes(2)
    rotacion = {"f00": {"fallos_seguidos": 5}, "f01": {}}
    grupos = planificar_facebook(todas, rotacion, tamano_grupo=1)
    assert [g["fuentes"] for g in grupos][0] == "f01"


def test_bloqueada_no_pierde_prioridad():
    """Un bloqueo es culpa de la IP, no de la fuente: tiene que seguir arriba."""
    todas = fuentes(2)
    rotacion = {
        "f00": {"ultimo_estado": "bloqueada", "bloqueos": 4},
        "f01": {"ultimo_exito": "2026-08-14T12:00:00+00:00"},
    }
    grupos = planificar_facebook(todas, rotacion, tamano_grupo=1)
    assert grupos[0]["fuentes"] == "f00"


def test_tope_de_jobs_agranda_grupos_en_vez_de_descartar_fuentes():
    grupos = planificar_facebook(fuentes(40), {}, tamano_grupo=2, max_grupos=10)
    assert len(grupos) == 10
    assert sum(g["cantidad"] for g in grupos) == 40


def test_rss_se_reparte_en_lotes_parejos():
    lotes = planificar_rss(fuentes(10, tipo="rss"), lotes=3)
    assert len(lotes) == 3
    assert sum(l["cantidad"] for l in lotes) == 10
    assert max(l["cantidad"] for l in lotes) - min(l["cantidad"] for l in lotes) <= 1


def test_matriz_es_json_de_una_linea_para_actions():
    grupos = planificar_facebook(fuentes(4), {}, tamano_grupo=2)
    matriz = a_matriz(grupos)
    assert "\n" not in matriz
    incluidos = json.loads(matriz)["include"]
    assert {"nombre", "orden", "fuentes", "cantidad"} <= set(incluidos[0])


def test_sin_fuentes_no_hay_grupos():
    assert planificar_facebook([], {}, tamano_grupo=2) == []
    assert planificar_rss([], lotes=3) == []
