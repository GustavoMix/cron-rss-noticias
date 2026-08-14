"""Limpieza y comparación de texto. Sin dependencias externas a propósito:
esto lo usan todas las etapas y no debería poder romperse por una librería."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from typing import Iterable, Set
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_ETIQUETAS_HTML = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")

# Parámetros de campaña/analítica: sacarlos es lo que hace que la misma nota
# compartida por Facebook y por RSS colapse en una sola URL.
_PARAMS_BASURA = (
    "utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ncid",
    "cmpid", "smid", "ref_src", "ref_url", "at_medium", "at_campaign",
    "__twitter_impression", "guccounter", "srnd", "leadSource",
)

# Palabras que no aportan a la comparación de titulares.
_VACIAS = {
    "the", "and", "for", "with", "from", "that", "this", "was", "were", "has",
    "have", "will", "you", "your", "are", "but", "not", "its", "his", "her",
    "los", "las", "del", "una", "unos", "unas", "por", "para", "con", "sin",
    "que", "como", "mas", "sus", "sobre", "entre", "tras", "ante", "desde",
    "este", "esta", "estos", "estas", "hay", "fue", "son", "ser", "muy",
}


def limpiar_html(valor: str | None) -> str:
    """Quita etiquetas y entidades; deja un texto plano de una sola línea."""
    if not valor:
        return ""
    sin_etiquetas = _ETIQUETAS_HTML.sub(" ", valor)
    return _ESPACIOS.sub(" ", html.unescape(sin_etiquetas)).strip()


def compactar(valor: str | None) -> str:
    return _ESPACIOS.sub(" ", (valor or "")).strip()


def recortar(valor: str, maximo: int) -> str:
    """Recorta en el último espacio antes del límite para no partir palabras."""
    valor = compactar(valor)
    if len(valor) <= maximo:
        return valor
    corte = valor[:maximo].rsplit(" ", 1)[0].rstrip(" ,;:.-")
    return f"{corte}…" if corte else valor[:maximo]


def normalizar(valor: str | None) -> str:
    """Minúsculas, sin acentos y sin puntuación: la forma canónica para comparar."""
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return _ESPACIOS.sub(" ", texto).strip()


def tokens(valor: str | None, minimo: int = 4) -> Set[str]:
    """Tokens significativos de un texto, ya normalizados."""
    return {
        t for t in normalizar(valor).split()
        if len(t) >= minimo and t not in _VACIAS
    }


def similitud(a: str | None, b: str | None) -> float:
    """Jaccard entre los tokens de dos textos. 0 = nada en común, 1 = iguales."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def canonizar_url(url: str | None) -> str:
    """La URL que se publica: sin tracking ni fragmento, pero navegable.

    A diferencia de `clave_url`, esta conserva el host tal cual (con `www.` si
    lo tenía): es el enlace que va a abrir el lector, y algunos sitios sirven
    distinto según el subdominio.
    """
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return url
    partes = urlsplit(url)
    consulta = [
        (k, v) for k, v in parse_qsl(partes.query, keep_blank_values=False)
        if not any(k.lower().startswith(p.lower()) for p in _PARAMS_BASURA)
    ]
    host = partes.netloc.lower().replace("m.facebook.com", "www.facebook.com")
    return urlunsplit((partes.scheme, host, partes.path, urlencode(consulta), ""))


def clave_url(url: str | None) -> str:
    """La forma de la URL que se usa para comparar, no para abrir.

    Además de lo que hace `canonizar_url`, borra `www.` y la barra final: dos
    enlaces a la misma nota que solo difieren en eso tienen que colapsar en una
    sola noticia, y de esta clave sale también el id estable del item.
    """
    canonica = canonizar_url(url)
    if not canonica.startswith(("http://", "https://")):
        return canonica
    partes = urlsplit(canonica)
    host = partes.netloc[4:] if partes.netloc.startswith("www.") else partes.netloc
    camino = partes.path.rstrip("/") or "/"
    return urlunsplit((partes.scheme, host, camino, partes.query, ""))


def id_estable(*partes: str | None) -> str:
    """Identificador determinista: la misma nota da el mismo id en cada corrida.

    Sin esto los feeds mostrarían todo como nuevo en cada ejecución, porque el
    guid cambiaría.
    """
    semilla = "|".join(normalizar(p) for p in partes if p)
    return hashlib.sha1(semilla.encode("utf-8")).hexdigest()[:16]


# Heurística de idioma: contar marcadores frecuentes. No pretende ser un
# detector serio, solo separar español de inglés, que es lo que necesitamos
# para elegir en qué feed va cada nota.
_MARCAS_ES = {"de", "que", "en", "el", "la", "los", "las", "un", "una", "por",
              "con", "para", "del", "se", "su", "al", "es", "y", "no", "mas"}
_MARCAS_EN = {"the", "of", "to", "in", "and", "for", "on", "with", "at", "by",
              "from", "is", "as", "it", "that", "was", "has", "after", "says"}


def detectar_idioma(texto: str | None, predeterminado: str = "es") -> str:
    palabras = normalizar(texto).split()
    if len(palabras) < 4:
        return predeterminado
    conjunto = palabras[:60]
    es = sum(1 for p in conjunto if p in _MARCAS_ES)
    en = sum(1 for p in conjunto if p in _MARCAS_EN)
    if es == en:
        return predeterminado
    return "es" if es > en else "en"


def contiene_alguna(texto: str | None, palabras: Iterable[str]) -> bool:
    normal = normalizar(texto)
    return any(normalizar(p) in normal for p in palabras)
