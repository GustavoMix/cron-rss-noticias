"""Índice de feeds: una página HTML y un JSON.

Cuando hay veinte feeds generados, hace falta un lugar que diga cuáles son y
dónde están. El HTML es para pegar en un navegador; el JSON es para que otra
herramienta descubra los feeds sin scrapear el HTML.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List


def escribir_json(ruta: Path, feeds: List[Dict[str, Any]], generado_en: str) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(
            {"generado_en": generado_en, "total": len(feeds), "feeds": feeds},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    return destino


def escribir_html(
    ruta: Path,
    feeds: List[Dict[str, Any]],
    titulo_sitio: str,
    generado_en: str,
) -> Path:
    filas = "\n".join(
        "      <tr>"
        f"<td><a href=\"{html.escape(f['archivo'])}\">{html.escape(f['titulo'])}</a></td>"
        f"<td class=\"num\">{f['items']}</td>"
        f"<td><code>{html.escape(f['url'])}</code></td>"
        "</tr>"
        for f in feeds
    )

    documento = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo_sitio)} — Feeds</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 60rem; padding: 2rem 1rem; }}
  h1 {{ font-size: 1.5rem; margin-bottom: .25rem; }}
  p.meta {{ color: #6b7280; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #d1d5db55; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{ font-size: .8125rem; word-break: break-all; }}
</style>
</head>
<body>
  <h1>{html.escape(titulo_sitio)}</h1>
  <p class="meta">{len(feeds)} feeds · actualizado {html.escape(generado_en)}</p>
  <table>
    <thead><tr><th>Feed</th><th class="num">Items</th><th>URL para el lector</th></tr></thead>
    <tbody>
{filas}
    </tbody>
  </table>
</body>
</html>
"""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(documento, encoding="utf-8")
    return destino
