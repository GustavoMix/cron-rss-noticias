"""Carga y validación de la configuración.

La configuración está partida a propósito:

    config/ajustes.yaml        — parámetros (cuánto, cada cuánto, hasta dónde)
    config/fuentes/*.yaml      — la lista de medios, un archivo por familia

Agregar un medio no debería obligar a abrir el archivo de parámetros, y tocar
un timeout no debería obligar a scrollear 300 líneas de fuentes. Esta función
junta las dos mitades y falla temprano y con nombre propio si algo no cuadra:
un id repetido entre dos archivos es el tipo de error que, sin validación, se
descubre recién cuando una fuente desaparece misteriosamente de los feeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

RAIZ = Path(__file__).resolve().parents[1]
AJUSTES_POR_DEFECTO = RAIZ / "config" / "ajustes.yaml"
FUENTES_POR_DEFECTO = RAIZ / "config" / "fuentes"

TIPOS_VALIDOS = {"rss", "facebook"}
CAMPOS_OBLIGATORIOS = ("id", "nombre", "tipo", "url")


class ErrorDeConfiguracion(RuntimeError):
    """La configuración no se puede usar tal como está."""


@dataclass
class Fuente:
    id: str
    nombre: str
    tipo: str
    url: str
    idioma: str = "es"
    categoria: str = "mundo"
    region: str = "Global"
    peso: int = 3
    activa: bool = True
    orden_preferido: int = 100
    archivo: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def es_facebook(self) -> bool:
        return self.tipo == "facebook"


@dataclass
class Configuracion:
    ajustes: Dict[str, Any]
    fuentes: List[Fuente]

    def bloque(self, nombre: str) -> Dict[str, Any]:
        """Un bloque de ajustes (`rss`, `facebook`, ...), siempre como dict."""
        valor = self.ajustes.get(nombre)
        return valor if isinstance(valor, dict) else {}

    def por_tipo(self, tipo: str, incluir_inactivas: bool = False) -> List[Fuente]:
        return [
            f for f in self.fuentes
            if f.tipo == tipo and (incluir_inactivas or f.activa)
        ]

    def por_ids(self, ids: List[str] | set[str]) -> List[Fuente]:
        buscados = {str(x).strip() for x in ids if str(x).strip()}
        return [f for f in self.fuentes if f.id in buscados]

    def obtener(self, fuente_id: str) -> Fuente | None:
        return next((f for f in self.fuentes if f.id == fuente_id), None)


def _leer_yaml(ruta: Path) -> Any:
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ErrorDeConfiguracion(f"No existe el archivo de configuración: {ruta}") from exc
    except yaml.YAMLError as exc:
        raise ErrorDeConfiguracion(f"YAML inválido en {ruta.name}: {exc}") from exc


def _fuente_desde_dict(bruto: Dict[str, Any], archivo: str) -> Fuente:
    faltantes = [c for c in CAMPOS_OBLIGATORIOS if not bruto.get(c)]
    if faltantes:
        raise ErrorDeConfiguracion(
            f"{archivo}: una fuente no tiene {', '.join(faltantes)} "
            f"(id declarado: {bruto.get('id', '¿sin id?')})"
        )

    tipo = str(bruto["tipo"]).strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise ErrorDeConfiguracion(
            f"{archivo}: la fuente '{bruto['id']}' declara tipo '{tipo}'; "
            f"los válidos son {sorted(TIPOS_VALIDOS)}"
        )

    url = str(bruto["url"]).strip()
    if not url.startswith(("http://", "https://")):
        raise ErrorDeConfiguracion(
            f"{archivo}: la URL de '{bruto['id']}' no parece una URL: {url!r}"
        )

    conocidos = {
        "id", "nombre", "tipo", "url", "idioma", "categoria", "region",
        "peso", "activa", "orden_preferido",
    }
    return Fuente(
        id=str(bruto["id"]).strip(),
        nombre=str(bruto["nombre"]).strip(),
        tipo=tipo,
        url=url,
        idioma=str(bruto.get("idioma", "es")).strip().lower(),
        categoria=str(bruto.get("categoria", "mundo")).strip().lower(),
        region=str(bruto.get("region", "Global")).strip(),
        peso=int(bruto.get("peso", 3)),
        activa=bool(bruto.get("activa", True)),
        orden_preferido=int(bruto.get("orden_preferido", 100)),
        archivo=archivo,
        extra={k: v for k, v in bruto.items() if k not in conocidos},
    )


def cargar(
    ajustes_path: Path | str = AJUSTES_POR_DEFECTO,
    fuentes_dir: Path | str = FUENTES_POR_DEFECTO,
) -> Configuracion:
    ajustes = _leer_yaml(Path(ajustes_path))
    if not isinstance(ajustes, dict):
        raise ErrorDeConfiguracion("config/ajustes.yaml debe ser un mapa de bloques")

    directorio = Path(fuentes_dir)
    archivos = sorted(directorio.glob("*.yaml")) + sorted(directorio.glob("*.yml"))
    if not archivos:
        raise ErrorDeConfiguracion(f"No hay archivos de fuentes en {directorio}")

    fuentes: List[Fuente] = []
    vistos: Dict[str, str] = {}

    for archivo in archivos:
        datos = _leer_yaml(archivo)
        brutas = datos.get("fuentes") if isinstance(datos, dict) else None
        if not brutas:
            continue
        if not isinstance(brutas, list):
            raise ErrorDeConfiguracion(f"{archivo.name}: 'fuentes' debe ser una lista")

        for bruto in brutas:
            if not isinstance(bruto, dict):
                raise ErrorDeConfiguracion(f"{archivo.name}: cada fuente debe ser un mapa")
            fuente = _fuente_desde_dict(bruto, archivo.name)
            if fuente.id in vistos:
                raise ErrorDeConfiguracion(
                    f"El id '{fuente.id}' está repetido: aparece en {vistos[fuente.id]} "
                    f"y en {archivo.name}. Los ids tienen que ser únicos porque el "
                    f"planificador y la rotación los usan como clave."
                )
            vistos[fuente.id] = archivo.name
            fuentes.append(fuente)

    if not fuentes:
        raise ErrorDeConfiguracion(f"No se encontró ninguna fuente en {directorio}")

    return Configuracion(ajustes=ajustes, fuentes=fuentes)
