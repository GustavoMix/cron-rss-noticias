import pytest

from noticias.config import ErrorDeConfiguracion, cargar

AJUSTES_MINIMOS = """
sitio:
  titulo: Test
facebook:
  tamano_grupo: 2
"""


def escribir(tmp_path, ajustes: str, archivos: dict[str, str]):
    (tmp_path / "ajustes.yaml").write_text(ajustes, encoding="utf-8")
    directorio = tmp_path / "fuentes"
    directorio.mkdir()
    for nombre, contenido in archivos.items():
        (directorio / nombre).write_text(contenido, encoding="utf-8")
    return tmp_path / "ajustes.yaml", directorio


def test_la_configuracion_real_del_repo_carga():
    config = cargar()
    assert config.fuentes
    assert config.por_tipo("rss")
    assert config.por_tipo("facebook")


def test_la_configuracion_real_no_pide_mas_jobs_de_los_permitidos():
    """Cada grupo de Facebook es un job. Si la lista crece sin subir el tope,
    los grupos se agrandan y vuelve el problema que este diseño evita."""
    config = cargar()
    facebook = config.por_tipo("facebook")
    ajustes = config.bloque("facebook")
    necesarios = -(-len(facebook) // int(ajustes["tamano_grupo"]))
    assert necesarios <= int(ajustes["max_paralelo"]), (
        f"{len(facebook)} páginas en grupos de {ajustes['tamano_grupo']} piden "
        f"{necesarios} jobs, pero max_paralelo es {ajustes['max_paralelo']}"
    )


def test_ids_repetidos_entre_archivos_son_error(tmp_path):
    ajustes, directorio = escribir(tmp_path, AJUSTES_MINIMOS, {
        "a.yaml": "fuentes:\n  - {id: x, nombre: A, tipo: rss, url: 'https://a.test/'}\n",
        "b.yaml": "fuentes:\n  - {id: x, nombre: B, tipo: rss, url: 'https://b.test/'}\n",
    })
    with pytest.raises(ErrorDeConfiguracion, match="repetido"):
        cargar(ajustes, directorio)


def test_tipo_desconocido_es_error(tmp_path):
    ajustes, directorio = escribir(tmp_path, AJUSTES_MINIMOS, {
        "a.yaml": "fuentes:\n  - {id: x, nombre: A, tipo: twitter, url: 'https://a.test/'}\n",
    })
    with pytest.raises(ErrorDeConfiguracion, match="tipo"):
        cargar(ajustes, directorio)


def test_url_invalida_es_error(tmp_path):
    ajustes, directorio = escribir(tmp_path, AJUSTES_MINIMOS, {
        "a.yaml": "fuentes:\n  - {id: x, nombre: A, tipo: rss, url: 'no-es-url'}\n",
    })
    with pytest.raises(ErrorDeConfiguracion, match="URL"):
        cargar(ajustes, directorio)


def test_campo_faltante_es_error(tmp_path):
    ajustes, directorio = escribir(tmp_path, AJUSTES_MINIMOS, {
        "a.yaml": "fuentes:\n  - {id: x, tipo: rss, url: 'https://a.test/'}\n",
    })
    with pytest.raises(ErrorDeConfiguracion, match="nombre"):
        cargar(ajustes, directorio)


def test_fuentes_inactivas_no_se_planifican(tmp_path):
    ajustes, directorio = escribir(tmp_path, AJUSTES_MINIMOS, {
        "a.yaml": (
            "fuentes:\n"
            "  - {id: viva, nombre: A, tipo: rss, url: 'https://a.test/'}\n"
            "  - {id: muerta, nombre: B, tipo: rss, url: 'https://b.test/', activa: false}\n"
        ),
    })
    config = cargar(ajustes, directorio)
    assert [f.id for f in config.por_tipo("rss")] == ["viva"]
    assert len(config.por_tipo("rss", incluir_inactivas=True)) == 2
