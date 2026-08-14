"""Salidas en JSON: una para consumir, otra para diagnosticar.

    datos/noticias.json        lo que consumiría una app
    datos/estado_fuentes.json  por qué una fuente trajo 0 items

El segundo archivo existe porque la pregunta que uno se hace a las tres de la
mañana no es "¿cuántas noticias hay?" sino "¿por qué esta fuente está muda?".
Sin él, un feed que quedó bloqueado y uno que simplemente no publicó nada se
ven exactamente igual.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from ..config import Fuente
from ..modelos import Noticia, ResultadoFuente
from ..util import fechas


ZONA_APP = ZoneInfo("America/La_Paz")


def _usuario_fuente(url: str) -> str | None:
    try:
        partes = [p for p in urlparse(url).path.split("/") if p]
    except Exception:
        return None
    if not partes or partes[0].lower() in {"pages", "groups", "profile.php"}:
        return None
    return partes[0]


def _post_id_facebook(url: str) -> str | None:
    """Extrae un id útil del permalink cuando Facebook lo deja en la URL."""
    try:
        parsed = urlparse(url)
        partes = [p for p in parsed.path.split("/") if p]
        for marca in ("posts", "videos", "reel"):
            if marca in partes:
                i = partes.index(marca)
                if i + 1 < len(partes):
                    return partes[i + 1].split("?")[0] or None
        query = parse_qs(parsed.query)
        for clave in ("story_fbid", "v", "fbid"):
            if query.get(clave):
                return str(query[clave][0])
    except Exception:
        return None
    return None


def _fecha_kotlin(valor: str | None) -> Dict[str, Any]:
    momento = fechas.parsear(valor)
    if momento is None:
        return {
            "iso_utc": valor,
            "epoch_ms": None,
            "fecha_utc": None,
            "hora_utc": None,
            "iso_bolivia": None,
            "fecha_bolivia": None,
            "hora_bolivia": None,
            "zona_bolivia": "America/La_Paz",
        }
    utc = momento.astimezone(timezone.utc)
    local = momento.astimezone(ZONA_APP)
    return {
        "iso_utc": utc.isoformat(timespec="seconds"),
        "epoch_ms": int(utc.timestamp() * 1000),
        "fecha_utc": utc.date().isoformat(),
        "hora_utc": utc.strftime("%H:%M:%S"),
        "iso_bolivia": local.isoformat(timespec="seconds"),
        "fecha_bolivia": local.date().isoformat(),
        "hora_bolivia": local.strftime("%H:%M:%S"),
        "zona_bolivia": "America/La_Paz",
    }


def _noticia_para_app(n: Noticia) -> Dict[str, Any]:
    """JSON estable y redundante a propósito para clientes Android/Kotlin.

    Conserva todos los campos planos históricos y suma bloques anidados. Eso
    permite migrar DTOs sin romper versiones anteriores de la app.
    """
    base = n.a_dict()
    tipo_contenido = "video" if n.video_url else ("imagen" if n.imagen_url else "texto")
    base.update({
        "plataforma": n.tipo_fuente,
        "collector": "public_web" if n.tipo_fuente == "facebook" else "rss",
        "post_id": _post_id_facebook(n.url) if n.tipo_fuente == "facebook" else None,
        "tipo_contenido": tipo_contenido,
        "canal": {
            "id": n.fuente_id,
            "nombre": n.fuente_nombre,
            "tipo": n.tipo_fuente,
            "pagina_url": n.fuente_url,
            "usuario": _usuario_fuente(n.fuente_url) if n.tipo_fuente == "facebook" else None,
            "icono_url": n.fuente_icono_url,
            "idioma": n.idioma,
            "region": n.fuente_region,
            "categoria_base": n.fuente_categoria,
            "peso": n.peso_fuente,
        },
        "fecha_hora": _fecha_kotlin(n.publicado_en),
        "detectado_fecha_hora": _fecha_kotlin(n.detectado_en),
        "media": {
            "imagen_principal": n.imagen_url,
            "imagenes": list(n.imagenes or []),
            "video_url": n.video_url,
            "tiene_imagen": bool(n.imagen_url or n.imagenes),
            "tiene_video": bool(n.video_url),
        },
        "metricas": {
            "reacciones": n.reacciones,
            "comentarios": n.comentarios,
            "compartidos": n.compartidos,
        },
        "clasificacion": {
            "categoria_principal": n.categoria,
            "categorias": list(n.categorias or []),
            "regiones": list(n.regiones or []),
            "etiquetas": list(n.etiquetas or []),
            "importancia": n.importancia,
        },
        "duplicados": {
            "cantidad_fuentes": n.cantidad_fuentes,
            "tambien_en": [
                {
                    "id": f.id,
                    "nombre": f.nombre,
                    "url": f.url,
                    "tipo": f.tipo,
                    "peso": f.peso,
                    "publicado_en": f.publicado_en,
                }
                for f in (n.tambien_en or [])
            ],
        },
    })
    return base


def escribir_noticias(
    ruta: Path,
    noticias: List[Noticia],
    generado_en: str,
    feeds: List[Dict[str, Any]],
    maximo: int = 500,
) -> Path:
    seleccion = noticias[:maximo]
    payload = {
        "version_esquema": "1.1",
        "compatibilidad": {
            "campos_planos_legacy": True,
            "bloques_kotlin": ["canal", "fecha_hora", "media", "metricas", "clasificacion", "duplicados"],
            "zona_horaria_app": "America/La_Paz",
        },
        "generado_en": generado_en,
        "generado_fecha_hora": _fecha_kotlin(generado_en),
        "resumen": {
            "noticias": len(seleccion),
            "en_historial": len(noticias),
            "por_categoria": dict(Counter(n.categoria for n in seleccion).most_common()),
            "por_region": dict(Counter(r for n in seleccion for r in n.regiones).most_common()),
            "por_idioma": dict(Counter(n.idioma for n in seleccion).most_common()),
            "por_tipo_fuente": dict(Counter(n.tipo_fuente for n in seleccion).most_common()),
        },
        "feeds": feeds,
        "noticias": [_noticia_para_app(n) for n in seleccion],
    }
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino


def escribir_estado(
    ruta: Path,
    fuentes: Iterable[Fuente],
    resultados: Iterable[ResultadoFuente],
    generado_en: str,
    descartes: Dict[str, int] | None = None,
) -> Path:
    por_id = {r.fuente_id: r for r in resultados}
    filas: List[Dict[str, Any]] = []

    for fuente in fuentes:
        resultado = por_id.get(fuente.id)
        filas.append({
            "id": fuente.id,
            "nombre": fuente.nombre,
            "tipo": fuente.tipo,
            "url": fuente.url,
            "archivo": fuente.archivo,
            "categoria": fuente.categoria,
            "region": fuente.region,
            "idioma": fuente.idioma,
            "peso": fuente.peso,
            "activa": fuente.activa,
            "estado": resultado.estado if resultado else "no_ejecutada",
            "items": resultado.items if resultado else 0,
            "duracion_ms": resultado.duracion_ms if resultado else 0,
            "error": resultado.error if resultado else None,
        })

    conteo = Counter(f["estado"] for f in filas)
    payload = {
        "generado_en": generado_en,
        "resumen": {
            "fuentes": len(filas),
            "por_estado": dict(conteo.most_common()),
            # Estas dos son las que hay que mirar primero cuando el feed baja:
            # bloqueadas significa "falta IP", error significa "fuente rota".
            "bloqueadas": conteo.get("bloqueada", 0),
            "con_error": conteo.get("error", 0),
            "descartes_en_proceso": descartes or {},
        },
        "fuentes": sorted(filas, key=lambda x: (x["estado"] != "error", x["tipo"], x["id"])),
    }

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def escribir_crudo(
    ruta: Path,
    items: List[Any],
    resultados: List[ResultadoFuente],
    momento: str,
    etiqueta: str,
    extra: Dict[str, Any] | None = None,
) -> Path:
    """Resultado intermedio de un job de CI, para que el job final lo combine.

    Es el formato de intercambio entre los jobs de fan-out y el de construcción:
    items sin normalizar + cómo le fue a cada fuente. En `extra` viaja lo que el
    job final necesita persistir de vuelta (por ejemplo, los ETag de los feeds
    leídos: cada job los descubre, pero solo el final escribe en el repo).
    """
    payload = {
        "etiqueta": etiqueta,
        "momento": momento,
        "items": [i.a_dict() for i in items],
        "resultados": [r.a_dict() for r in resultados],
        "extra": extra or {},
    }
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino
