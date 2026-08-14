"""Regenera docs/FUENTES.md a partir de config/fuentes/*.yaml.

    python herramientas/generar_doc_fuentes.py

Se corre a mano después de tocar la lista de fuentes. La configuración es la
verdad; este documento es solo una vista legible de ella.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from noticias.config import cargar  # noqa: E402

TITULOS = {
    "agencias.yaml": "Agencias y organismos internacionales",
    "mundo_en.yaml": "Medios globales en inglés",
    "mundo_es.yaml": "Prensa en español",
    "temas.yaml": "Fuentes por tema",
    "facebook.yaml": "Páginas públicas de Facebook",
}


def main() -> int:
    config = cargar()
    por_archivo: dict[str, list] = defaultdict(list)
    for fuente in config.fuentes:
        por_archivo[fuente.archivo].append(fuente)

    facebook = config.por_tipo("facebook")
    ajustes = config.bloque("facebook")
    tamano = int(ajustes.get("tamano_grupo", 2))
    jobs = -(-len(facebook) // tamano)

    lineas = [
        "# Fuentes configuradas",
        "",
        "> Generado con `python herramientas/generar_doc_fuentes.py`.",
        "> La verdad está en `config/fuentes/*.yaml`.",
        "",
        f"**Total: {len(config.fuentes)} fuentes** — "
        f"{len(config.por_tipo('rss'))} RSS y {len(facebook)} páginas de Facebook.",
        "",
        f"Las {len(facebook)} páginas de Facebook se reparten en grupos de {tamano}, "
        f"o sea **{jobs} grupos de CI** por corrida "
        f"(tope del planificador: {ajustes.get('max_paralelo')}; "
        f"el workflow limita la concurrencia por separado).",
        "",
        "`peso` (1-5) decide qué versión gana cuando varios medios traen la misma "
        "historia, y suma a la importancia del item.",
        "",
    ]

    for archivo in sorted(por_archivo, key=lambda a: (a != "agencias.yaml", a)):
        fuentes = sorted(por_archivo[archivo], key=lambda f: f.id)
        lineas += [
            f"## {TITULOS.get(archivo, archivo)}",
            "",
            f"`config/fuentes/{archivo}` — {len(fuentes)} fuentes",
            "",
            "| id | nombre | tema | región | idioma | peso |",
            "|---|---|---|---|---|---|",
        ]
        for f in fuentes:
            marca = "" if f.activa else " *(inactiva)*"
            lineas.append(
                f"| `{f.id}` | [{f.nombre}]({f.url}){marca} | {f.categoria} | "
                f"{f.region} | {f.idioma} | {f.peso} |"
            )
        lineas.append("")

    destino = RAIZ / "docs" / "FUENTES.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Escrito {destino} ({len(config.fuentes)} fuentes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
