import sys
from pathlib import Path

# Los tests corren contra el árbol del repo, sin instalarlo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from noticias.modelos import ItemCrudo


@pytest.fixture
def item():
    """Constructor de ItemCrudo con valores por defecto razonables."""

    def crear(**kwargs):
        base = dict(
            fuente_id="rss_demo",
            fuente_nombre="Demo",
            fuente_url="https://demo.test/",
            url="https://demo.test/nota-1",
            titulo="Un titular suficientemente largo para pasar el filtro",
            resumen="Resumen de la nota de prueba con algo de contenido.",
            texto="Texto completo de la nota de prueba con algo de contenido.",
            publicado_en="2026-08-14T10:00:00+00:00",
            idioma="es",
            categoria_fuente="mundo",
            region_fuente="Global",
            tipo_fuente="rss",
            peso_fuente=3,
        )
        base.update(kwargs)
        return ItemCrudo(**base)

    return crear
