"""Clasificación por tema y por región, y puntaje de importancia.

Reglas por palabras clave, no modelos: tiene que correr en un runner de CI en
segundos, ser explicable ("¿por qué esta nota está en deportes?") y no depender
de ninguna API externa que pueda caerse o cobrar.

La categoría de la fuente es el punto de partida, pero no manda: The Guardian
publica ciencia y la BBC publica deportes. Si el texto coincide claramente con
otro tema, gana el texto.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from ..modelos import Noticia
from ..util import fechas, texto as t

# Palabras por categoría, en español e inglés. Ordenadas de más específica a
# más genérica: las genéricas suman poco justamente porque aparecen en todos
# lados.
PALABRAS_POR_CATEGORIA: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "conflictos": (
        ("guerra", 3), ("war", 3), ("bombardeo", 3), ("airstrike", 3),
        ("ofensiva", 2), ("offensive", 2), ("alto el fuego", 3), ("ceasefire", 3),
        ("tropas", 2), ("troops", 2), ("misil", 3), ("missile", 3),
        ("ataque", 2), ("attack", 2), ("rehenes", 3), ("hostages", 3),
        ("frontera", 1), ("militar", 2), ("military", 2), ("otan", 3), ("nato", 3),
    ),
    "politica": (
        ("elecciones", 3), ("election", 3), ("presidente", 2), ("president", 2),
        ("parlamento", 3), ("parliament", 3), ("congreso", 2), ("congress", 2),
        ("ministro", 2), ("minister", 2), ("gobierno", 1), ("government", 1),
        ("senado", 3), ("senate", 3), ("primer ministro", 3), ("prime minister", 3),
        ("referendo", 3), ("referendum", 3), ("candidato", 2), ("candidate", 2),
        ("cumbre", 2), ("summit", 2), ("sanciones", 2), ("sanctions", 2),
    ),
    "economia": (
        ("inflacion", 3), ("inflation", 3), ("mercados", 2), ("markets", 2),
        ("bolsa", 3), ("stocks", 3), ("dolar", 2), ("dollar", 2),
        ("banco central", 3), ("central bank", 3), ("recesion", 3), ("recession", 3),
        ("aranceles", 3), ("tariffs", 3), ("desempleo", 3), ("unemployment", 3),
        ("pib", 3), ("gdp", 3), ("petroleo", 2), ("oil prices", 3),
        ("criptomoneda", 3), ("bitcoin", 3), ("inversion", 1), ("earnings", 3),
    ),
    "tecnologia": (
        ("inteligencia artificial", 3), ("artificial intelligence", 3),
        ("software", 2), ("hardware", 2), ("chip", 2), ("semiconductor", 3),
        ("aplicacion movil", 3), ("smartphone", 3), ("startup", 2),
        ("ciberataque", 3), ("cyberattack", 3), ("hackers", 3),
        ("algoritmo", 2), ("algorithm", 2), ("openai", 3), ("google", 2),
        ("apple", 2), ("microsoft", 2), ("robot", 2), ("datos personales", 2),
    ),
    "ciencia": (
        ("investigadores", 3), ("researchers", 3), ("estudio", 1), ("study finds", 3),
        ("nasa", 3), ("espacial", 3), ("space", 2), ("cohete", 3), ("rocket", 3),
        ("astronomia", 3), ("astronomy", 3), ("fosil", 3), ("fossil", 3),
        ("genetica", 3), ("genetic", 3), ("universidad", 1), ("nature", 2),
        ("descubrimiento", 2), ("discovery", 2), ("telescopio", 3), ("telescope", 3),
    ),
    "salud": (
        ("virus", 3), ("vacuna", 3), ("vaccine", 3), ("brote", 3), ("outbreak", 3),
        ("pandemia", 3), ("pandemic", 3), ("hospital", 2), ("cancer", 3),
        ("epidemia", 3), ("epidemic", 3), ("oms", 3), ("who says", 3),
        ("salud mental", 3), ("mental health", 3), ("farmaco", 3), ("drug trial", 3),
    ),
    "ambiente": (
        ("cambio climatico", 3), ("climate change", 3), ("sequia", 3), ("drought", 3),
        ("inundacion", 3), ("flood", 3), ("huracan", 3), ("hurricane", 3),
        ("terremoto", 3), ("earthquake", 3), ("incendio forestal", 3), ("wildfire", 3),
        ("deforestacion", 3), ("deforestation", 3), ("emisiones", 3), ("emissions", 3),
        ("biodiversidad", 3), ("biodiversity", 3), ("contaminacion", 2), ("pollution", 2),
    ),
    "deportes": (
        ("futbol", 3), ("football", 2), ("soccer", 3), ("mundial", 2),
        ("world cup", 3), ("liga", 2), ("league", 2), ("gol", 2), ("goal", 1),
        ("olimpicos", 3), ("olympics", 3), ("tenis", 3), ("tennis", 3),
        ("nba", 3), ("formula 1", 3), ("champions", 3), ("entrenador", 2),
        ("basquet", 3), ("basketball", 3), ("atleta", 2), ("athlete", 2),
    ),
    "cultura": (
        ("pelicula", 3), ("film", 2), ("cine", 3), ("museo", 3), ("museum", 3),
        ("album", 2), ("concierto", 3), ("concert", 3), ("festival", 2),
        ("oscar", 3), ("grammy", 3), ("novela", 2), ("literatura", 3),
        ("artista", 2), ("artist", 2), ("serie", 2), ("streaming", 2),
    ),
    "sociedad": (
        ("migrantes", 3), ("migrants", 3), ("refugiados", 3), ("refugees", 3),
        ("protesta", 2), ("protest", 2), ("huelga", 3), ("strike", 2),
        ("derechos humanos", 3), ("human rights", 3), ("educacion", 2),
        ("femicidio", 3), ("violencia de genero", 3), ("pobreza", 2), ("poverty", 2),
    ),
}

# Gazetteer mínimo: alcanza para etiquetar por continente/región, que es la
# granularidad que tiene sentido en un agregador mundial.
PAISES_POR_REGION: Dict[str, Tuple[str, ...]] = {
    "América Latina": (
        "argentina", "bolivia", "brasil", "brazil", "chile", "colombia",
        "costa rica", "cuba", "ecuador", "el salvador", "guatemala", "haiti",
        "honduras", "mexico", "nicaragua", "panama", "paraguay", "peru",
        "republica dominicana", "uruguay", "venezuela", "latinoamerica",
        "america latina", "latin america", "buenos aires", "bogota", "lima",
        "santiago", "caracas", "la paz", "santa cruz", "cochabamba",
    ),
    "América del Norte": (
        "estados unidos", "united states", "washington", "new york",
        "nueva york", "california", "texas", "florida", "canada", "ottawa",
        "toronto", "white house", "casa blanca", "trump", "biden", "pentagon",
    ),
    "Europa": (
        "europa", "europe", "union europea", "european union", "reino unido",
        "united kingdom", "londres", "london", "francia", "france", "paris",
        "alemania", "germany", "berlin", "espana", "spain", "madrid",
        "italia", "italy", "roma", "rome", "ucrania", "ukraine", "kiev",
        "rusia", "russia", "moscu", "moscow", "polonia", "poland", "bruselas",
        "brussels", "portugal", "lisboa", "suecia", "noruega", "grecia",
    ),
    "Medio Oriente": (
        "israel", "gaza", "palestina", "palestine", "iran", "teheran",
        "iraq", "irak", "siria", "syria", "libano", "lebanon", "beirut",
        "arabia saudi", "saudi arabia", "emiratos", "qatar", "yemen",
        "jerusalen", "jerusalem", "tel aviv", "hamas", "hezbola",
    ),
    "Asia": (
        "china", "beijing", "pekin", "shanghai", "japon", "japan", "tokio",
        "tokyo", "corea del sur", "south korea", "corea del norte",
        "north korea", "seul", "india", "nueva delhi", "new delhi",
        "pakistan", "indonesia", "vietnam", "filipinas", "philippines",
        "taiwan", "hong kong", "tailandia", "thailand", "bangladesh",
        "afganistan", "afghanistan", "myanmar",
    ),
    "África": (
        "africa", "nigeria", "egipto", "egypt", "el cairo", "cairo",
        "sudafrica", "south africa", "etiopia", "ethiopia", "kenia", "kenya",
        "sudan", "somalia", "congo", "marruecos", "morocco", "argelia",
        "algeria", "libia", "libya", "mali", "senegal", "ghana", "sahel",
    ),
    "Oceanía": (
        "australia", "sidney", "sydney", "melbourne", "nueva zelanda",
        "new zealand", "fiyi", "fiji", "papua",
    ),
}

# Señales de que una nota es de las importantes del día.
_PALABRAS_URGENTES = (
    "última hora", "ultima hora", "breaking", "urgente", "en vivo", "live",
    "muertos", "killed", "dead", "emergencia", "emergency", "crisis",
    "renuncia", "resigns", "histórico", "historic", "récord", "record",
)


def _puntajes_por_categoria(texto_completo: str) -> Dict[str, int]:
    normal = t.normalizar(texto_completo)
    puntajes: Dict[str, int] = {}
    for categoria, palabras in PALABRAS_POR_CATEGORIA.items():
        total = sum(peso for palabra, peso in palabras if t.normalizar(palabra) in normal)
        if total:
            puntajes[categoria] = total
    return puntajes


def _regiones(texto_completo: str, region_fuente: Iterable[str]) -> List[str]:
    normal = t.normalizar(texto_completo)
    encontradas = [
        region for region, lugares in PAISES_POR_REGION.items()
        if any(t.normalizar(lugar) in normal for lugar in lugares)
    ]
    for region in region_fuente:
        if region and region not in encontradas and region != "Global":
            encontradas.append(region)
    return encontradas or ["Global"]


def clasificar_una(noticia: Noticia, referencia=None) -> Noticia:
    texto_completo = f"{noticia.titulo}. {noticia.resumen}"
    puntajes = _puntajes_por_categoria(texto_completo)

    categoria_fuente = noticia.categoria or "mundo"
    # La categoría declarada por la fuente arranca con ventaja: es cierta la
    # mayoría de las veces y evita que una palabra suelta se lleve la nota.
    if categoria_fuente in PALABRAS_POR_CATEGORIA:
        puntajes[categoria_fuente] = puntajes.get(categoria_fuente, 0) + 3

    if puntajes:
        ordenadas = sorted(puntajes.items(), key=lambda x: (-x[1], x[0]))
        mejor, mejor_puntaje = ordenadas[0]
        # Solo se cambia de categoría con evidencia clara, no por un empate.
        noticia.categoria = mejor if mejor_puntaje >= 3 else categoria_fuente
        noticia.categorias = [nombre for nombre, puntaje in ordenadas if puntaje >= 3][:4]
    else:
        noticia.categoria = categoria_fuente
        noticia.categorias = [categoria_fuente]

    if noticia.categoria not in noticia.categorias:
        noticia.categorias.insert(0, noticia.categoria)

    noticia.regiones = _regiones(texto_completo, noticia.regiones)
    noticia.importancia = calcular_importancia(noticia, referencia)
    return noticia


def calcular_importancia(noticia: Noticia, referencia=None) -> int:
    """0-100. Ordena los feeds cuando dos notas comparten la misma hora.

    Se compone de: peso editorial de la fuente, cuántos medios la trajeron,
    qué tan fresca es, y si el titular tiene marcas de urgencia.
    """
    puntaje = 0

    # Cuántos medios distintos publicaron la misma historia es la señal más
    # fuerte que tenemos, y la más difícil de falsear desde una sola fuente.
    puntaje += min(40, 12 * max(0, noticia.cantidad_fuentes - 1))

    peso_maximo = max([noticia.peso_fuente] + [f.peso for f in noticia.tambien_en])
    puntaje += peso_maximo * 5  # 5..25

    antiguedad = fechas.horas_desde(noticia.publicado_en, referencia)
    if antiguedad <= 2:
        puntaje += 20
    elif antiguedad <= 6:
        puntaje += 14
    elif antiguedad <= 12:
        puntaje += 8
    elif antiguedad <= 24:
        puntaje += 4

    if t.contiene_alguna(noticia.titulo, _PALABRAS_URGENTES):
        puntaje += 8
    if noticia.imagen_url:
        puntaje += 2

    return max(0, min(100, puntaje))


def clasificar(noticias: Iterable[Noticia], referencia=None) -> List[Noticia]:
    return [clasificar_una(n, referencia) for n in noticias]
