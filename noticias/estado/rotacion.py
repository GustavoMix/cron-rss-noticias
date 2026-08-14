"""Memoria de rotación de Facebook: a quién le toca el turno bueno.

Dentro de un grupo, el **primer** turno es el que casi siempre pasa: la IP
todavía tiene su cupo intacto. El segundo ya es una apuesta. Esa asimetría es
un recurso escaso y hay que repartirlo, no dejarlo fijo.

Lo que se guarda por fuente:

    ultimo_exito      cuándo trajo datos por última vez
    ultimo_intento    cuándo se la intentó por última vez
    ultimo_estado     ok | sin_novedades | bloqueada | error | omitida
    fallos_seguidos   errores propios (página renombrada, borrada, privada)
    bloqueos          veces que la cortó Facebook (no es culpa de la fuente)

La distinción entre *bloqueada* y *error* es el corazón del archivo. Una fuente
bloqueada no hizo nada mal: le tocó una IP quemada, así que sigue envejeciendo
y sube sola en la próxima corrida. Una fuente con error propio sí baja de
prioridad, para que no acapare turnos buenos corrida tras corrida.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from ..modelos import ResultadoFuente
from ..util import fechas

# Una fuente que nunca funcionó tiene que ganarle a cualquiera que sí, por
# vieja que sea. Solo necesita ser mayor a cualquier antigüedad real en horas.
HORAS_NUNCA_VISTA = 10_000.0


def cargar(ruta: Path) -> Dict[str, Dict[str, Any]]:
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return {}
    fuentes = datos.get("fuentes")
    return fuentes if isinstance(fuentes, dict) else {}


def horas_sin_exito(estado: Dict[str, Any], referencia=None) -> float:
    valor = fechas.horas_desde(estado.get("ultimo_exito"), referencia)
    return HORAS_NUNCA_VISTA if valor == float("inf") else valor


def prioridad(
    fuente_id: str,
    peso: int,
    rotacion: Dict[str, Dict[str, Any]],
    referencia=None,
) -> float:
    """Cuánto merece esta fuente el primer turno de un grupo. Más alto, antes."""
    estado = rotacion.get(fuente_id, {})
    valor = horas_sin_exito(estado, referencia) * (1.0 + 0.12 * max(0, peso - 3))

    fallos = int(estado.get("fallos_seguidos", 0))
    if fallos >= 3:
        valor *= 0.35
    elif fallos == 2:
        valor *= 0.70

    return valor


def actualizar(
    ruta: Path,
    resultados: Iterable[ResultadoFuente],
    momento: str,
    conservar_dias: int = 30,
) -> Dict[str, Dict[str, Any]]:
    rotacion = cargar(ruta)

    for resultado in resultados:
        estado = dict(rotacion.get(resultado.fuente_id, {}))
        estado["ultimo_intento"] = momento
        estado["ultimo_estado"] = resultado.estado

        if resultado.estado == "omitida":
            # Nunca llegó a intentarse: ni éxito ni fallo propio.
            rotacion[resultado.fuente_id] = estado
            continue

        if resultado.estado == "bloqueada":
            estado["bloqueos"] = int(estado.get("bloqueos", 0)) + 1
            # A propósito NO se toca ultimo_exito: la fuente sigue envejeciendo
            # y sube de prioridad para la próxima corrida.
        elif resultado.estado == "error":
            estado["fallos_seguidos"] = int(estado.get("fallos_seguidos", 0)) + 1
            estado["ultimo_error"] = (resultado.error or "")[:200]
        else:
            # ok y sin_novedades: la página cargó, el turno se usó.
            estado["ultimo_exito"] = momento
            estado["fallos_seguidos"] = 0
            estado["exitos"] = int(estado.get("exitos", 0)) + 1
            estado.pop("ultimo_error", None)

        rotacion[resultado.fuente_id] = estado

    referencia = fechas.parsear(momento) or fechas.ahora()
    vigentes = {
        fuente_id: estado
        for fuente_id, estado in rotacion.items()
        if fechas.horas_desde(estado.get("ultimo_intento"), referencia) <= conservar_dias * 24
    }

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(
            {"actualizado": momento, "fuentes": vigentes},
            ensure_ascii=False, indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )
    return vigentes
