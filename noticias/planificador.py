"""Reparto de fuentes en jobs de CI.

Este archivo es donde vive la estrategia. El resto del código lee fuentes y
arma feeds; acá se decide *cuántas IPs* se usan y *qué fuente cae en cada una*.

El dato duro alrededor del cual gira todo: **Facebook deja pasar ~2 páginas
públicas por IP**. Un job de GitHub Actions = un runner = una IP de salida.
De ahí salen las tres reglas:

1. **Grupos chicos, muchos.** `tamano_grupo=2` significa que detrás de una
   fuente bloqueada queda como mucho una sola fuente más. Con grupos de 5 se
   perdían hasta 4 por un solo bloqueo. Agrandar el grupo no retrasa el
   bloqueo: solo pone más fuentes detrás de él.

2. **Round-robin, no bloques.** Las fuentes se ordenan por urgencia y se
   reparten una por grupo. Así las N más urgentes caen cada una en el *primer*
   turno de un grupo distinto -el turno que casi siempre pasa-. Partirlas en
   bloques haría que la 1ª y la 2ª prioridad compitan dentro del mismo job.

3. **Memoria entre corridas.** La que lleva más tiempo sin traer datos sube al
   primer turno la próxima vez (ver `estado/rotacion.py`). Con el cron cada
   hora, en pocas vueltas todas pasan por un turno bueno aunque en una corrida
   puntual algunas queden bloqueadas.

Las fuentes RSS también se reparten, pero por un motivo distinto y mucho más
aburrido: que la corrida no dependa de un único job lento. No hay límite por IP
en un archivo estático servido por CDN.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .config import Fuente
from .estado import rotacion as rotacion_estado


def planificar_facebook(
    fuentes: List[Fuente],
    rotacion: Dict[str, Dict[str, Any]],
    tamano_grupo: int = 2,
    max_grupos: int | None = None,
    referencia=None,
) -> List[Dict[str, Any]]:
    """Devuelve los grupos listos para la matrix de GitHub Actions.

    `max_grupos` recorta la cantidad de jobs cuando la lista de fuentes crece
    más de lo que el plan de CI permite en paralelo. No se descartan fuentes:
    los grupos quedan un poco más grandes y la rotación se encarga de que las
    que hoy comparten turno malo tengan el bueno mañana.
    """
    if not fuentes:
        return []

    tamano_grupo = max(1, int(tamano_grupo))
    ordenadas = sorted(
        fuentes,
        key=lambda f: (
            -rotacion_estado.prioridad(f.id, f.peso, rotacion, referencia),
            f.orden_preferido,
            f.id,
        ),
    )

    cantidad = -(-len(ordenadas) // tamano_grupo)  # techo de la división
    if max_grupos:
        cantidad = min(cantidad, max(1, int(max_grupos)))

    cubos: List[List[Fuente]] = [[] for _ in range(cantidad)]
    for posicion, fuente in enumerate(ordenadas):
        cubos[posicion % cantidad].append(fuente)

    grupos = []
    for indice, cubo in enumerate(cubos):
        if not cubo:
            continue
        grupos.append({
            "nombre": f"g{indice + 1:02d}",
            "orden": indice,
            "fuentes": ",".join(f.id for f in cubo),
            "cantidad": len(cubo),
        })
    return grupos


def planificar_rss(fuentes: List[Fuente], lotes: int = 3) -> List[Dict[str, Any]]:
    """Reparte las fuentes RSS en lotes parejos, también en round-robin para
    que ningún lote junte todas las fuentes lentas."""
    if not fuentes:
        return []

    lotes = max(1, min(int(lotes), len(fuentes)))
    cubos: List[List[Fuente]] = [[] for _ in range(lotes)]
    for posicion, fuente in enumerate(sorted(fuentes, key=lambda f: f.id)):
        cubos[posicion % lotes].append(fuente)

    return [
        {
            "nombre": f"r{indice + 1:02d}",
            "orden": indice,
            "fuentes": ",".join(f.id for f in cubo),
            "cantidad": len(cubo),
        }
        for indice, cubo in enumerate(cubos)
        if cubo
    ]


def a_matriz(grupos: List[Dict[str, Any]]) -> str:
    """Serializa los grupos como matrix de Actions, en una sola línea, para
    pasar por `$GITHUB_OUTPUT` y leer con `fromJSON()`."""
    return json.dumps({"include": grupos}, ensure_ascii=False, separators=(",", ":"))


def resumen(grupos: List[Dict[str, Any]], etiqueta: str, nota: str = "") -> str:
    total = sum(g["cantidad"] for g in grupos)
    lineas = [f"{etiqueta}: {total} fuentes en {len(grupos)} grupos." + (f" {nota}" if nota else "")]
    lineas += [f"  {g['nombre']}: {g['fuentes']}" for g in grupos]
    return "\n".join(lineas)
