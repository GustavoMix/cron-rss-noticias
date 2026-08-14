"""Agrupado de la misma historia publicada por varios medios.

Sin esto, un feed mundial se vuelve inusable: veinte medios publican la misma
cumbre y el lector ve veinte líneas casi idénticas.

Dos pasadas, de la más barata y segura a la más cara:

1. **Misma URL canónica.** Una nota compartida en Facebook y también publicada
   en el RSS del mismo medio llega dos veces con la misma URL. Colapsan sin
   discusión.
2. **Titulares parecidos dentro de una ventana de tiempo.** Jaccard sobre los
   tokens del titular. Es un O(n·k) sobre grupos con al menos un token en
   común -no O(n²) sobre todo el corpus-, porque con ~2.000 notas por corrida
   la comparación de todos contra todos ya se nota.

La versión que sobrevive es la de la fuente con más peso editorial; las otras
quedan adjuntas en `tambien_en`, que además sube la importancia del grupo.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from ..modelos import FuenteEnNoticia, Noticia
from ..util import fechas, texto as t


def _clave_fuente(noticia: Noticia) -> FuenteEnNoticia:
    return FuenteEnNoticia(
        id=noticia.fuente_id,
        nombre=noticia.fuente_nombre,
        url=noticia.url,
        tipo=noticia.tipo_fuente,
        peso=noticia.peso_fuente,
        publicado_en=noticia.publicado_en,
    )


def _mejor(a: Noticia, b: Noticia) -> Noticia:
    """Cuál de las dos versiones se queda como canónica.

    Orden: más peso editorial, luego RSS sobre Facebook (el permalink de un
    post envejece peor que la URL de la nota), luego la más antigua -quien
    publicó primero-, y por último la de resumen más largo.
    """
    if a.peso_fuente != b.peso_fuente:
        return a if a.peso_fuente > b.peso_fuente else b
    if a.tipo_fuente != b.tipo_fuente:
        return a if a.tipo_fuente == "rss" else b
    antiguedad_a = fechas.horas_desde(a.publicado_en)
    antiguedad_b = fechas.horas_desde(b.publicado_en)
    if antiguedad_a != antiguedad_b:
        return a if antiguedad_a > antiguedad_b else b
    return a if len(a.resumen) >= len(b.resumen) else b


def _fusionar(principal: Noticia, secundaria: Noticia) -> Noticia:
    """Mete `secundaria` dentro de `principal` como fuente adicional."""
    ya_estan = {f.id for f in principal.tambien_en} | {principal.fuente_id}
    if secundaria.fuente_id not in ya_estan:
        principal.tambien_en.append(_clave_fuente(secundaria))

    if not principal.imagen_url and secundaria.imagen_url:
        principal.imagen_url = secundaria.imagen_url
        principal.imagenes = principal.imagenes or secundaria.imagenes
    if len(secundaria.resumen) > len(principal.resumen):
        principal.resumen = secundaria.resumen
    for etiqueta in secundaria.etiquetas:
        if etiqueta not in principal.etiquetas and len(principal.etiquetas) < 8:
            principal.etiquetas.append(etiqueta)
    for region in secundaria.regiones:
        if region not in principal.regiones:
            principal.regiones.append(region)

    principal.cantidad_fuentes = 1 + len(principal.tambien_en)
    return principal


def _agrupar_por_url(noticias: Iterable[Noticia]) -> List[Noticia]:
    por_url: Dict[str, Noticia] = {}
    for noticia in noticias:
        clave = t.clave_url(noticia.url)
        existente = por_url.get(clave)
        if existente is None:
            por_url[clave] = noticia
            continue
        ganadora = _mejor(existente, noticia)
        perdedora = noticia if ganadora is existente else existente
        por_url[clave] = _fusionar(ganadora, perdedora)
    return list(por_url.values())


def _candidatas(noticias: List[Noticia]) -> Dict[str, List[int]]:
    """Índice token -> posiciones. Solo se comparan pares que comparten al
    menos un token significativo; el resto no puede superar ningún umbral."""
    indice: Dict[str, List[int]] = defaultdict(list)
    for posicion, noticia in enumerate(noticias):
        for token in list(t.tokens(noticia.titulo))[:12]:
            indice[token].append(posicion)
    return indice


def agrupar(
    noticias: Iterable[Noticia],
    umbral: float = 0.5,
    ventana_horas: float = 36.0,
) -> List[Noticia]:
    """Devuelve una lista sin duplicados, con `tambien_en` y `cantidad_fuentes`
    ya calculados. Ordenada por fecha de publicación descendente."""
    unicas = _agrupar_por_url(noticias)
    if len(unicas) < 2:
        return unicas

    # Más nuevas primero: la primera de cada grupo termina siendo la referencia
    # y conviene que sea la versión más fresca.
    unicas.sort(key=lambda n: n.publicado_en or "", reverse=True)

    indice = _candidatas(unicas)
    absorbidas: set[int] = set()
    resultado: List[Noticia] = []

    for posicion, noticia in enumerate(unicas):
        if posicion in absorbidas:
            continue

        vecinas: set[int] = set()
        for token in list(t.tokens(noticia.titulo))[:12]:
            vecinas.update(p for p in indice.get(token, ()) if p > posicion)

        for otra_posicion in sorted(vecinas):
            if otra_posicion in absorbidas:
                continue
            otra = unicas[otra_posicion]
            if otra.fuente_id == noticia.fuente_id:
                # Un mismo medio publicando dos notas parecidas suele ser
                # seguimiento de una historia, no un duplicado.
                continue
            if _distancia_horas(noticia, otra) > ventana_horas:
                continue
            if t.similitud(noticia.titulo, otra.titulo) < umbral:
                continue
            absorbidas.add(otra_posicion)
            noticia = _fusionar(noticia, otra)

        resultado.append(noticia)

    resultado.sort(key=lambda n: (n.publicado_en or "", n.importancia), reverse=True)
    return resultado


def _distancia_horas(a: Noticia, b: Noticia) -> float:
    momento_a = fechas.parsear(a.publicado_en)
    momento_b = fechas.parsear(b.publicado_en)
    if not momento_a or not momento_b:
        return 0.0
    return abs((momento_a - momento_b).total_seconds()) / 3600.0
