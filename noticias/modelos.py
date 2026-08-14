"""Estructuras de datos que viajan entre etapas.

Hay dos y solo dos:

    ItemCrudo  — lo que devuelve un lector de fuente (RSS o Facebook), sin
                 interpretar. Es lo que se serializa a JSON entre jobs de CI.
    Noticia    — lo que sale del proceso: ya normalizada, clasificada y con
                 sus duplicados de otros medios adjuntos. Es lo que se
                 escribe a los feeds.

Mantener esta frontera es lo que permite que los lectores no sepan nada de
categorías ni de RSS de salida, y que el proceso no sepa de dónde vino el dato.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ItemCrudo:
    """Una publicación tal como la entregó su fuente."""

    fuente_id: str
    fuente_nombre: str
    fuente_url: str
    url: str
    titulo: str = ""
    resumen: str = ""
    texto: str = ""
    publicado_en: Optional[str] = None
    autor: Optional[str] = None
    idioma: Optional[str] = None
    categoria_fuente: Optional[str] = None
    region_fuente: Optional[str] = None
    tipo_fuente: str = "rss"
    peso_fuente: int = 3
    imagenes: List[str] = field(default_factory=list)
    video_url: Optional[str] = None
    etiquetas: List[str] = field(default_factory=list)

    def a_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def desde_dict(cls, data: Dict[str, Any]) -> "ItemCrudo":
        campos = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in campos})


@dataclass
class FuenteEnNoticia:
    """Un medio que publicó esta misma historia."""

    id: str
    nombre: str
    url: str
    tipo: str
    peso: int
    publicado_en: Optional[str] = None


@dataclass
class Noticia:
    """Una historia lista para publicarse en un feed."""

    id: str
    titulo: str
    resumen: str
    url: str
    fuente_id: str
    fuente_nombre: str
    fuente_url: str
    tipo_fuente: str
    peso_fuente: int
    publicado_en: Optional[str]
    detectado_en: str
    idioma: str
    categoria: str
    categorias: List[str] = field(default_factory=list)
    regiones: List[str] = field(default_factory=list)
    importancia: int = 0
    autor: Optional[str] = None
    imagen_url: Optional[str] = None
    imagenes: List[str] = field(default_factory=list)
    video_url: Optional[str] = None
    etiquetas: List[str] = field(default_factory=list)
    # Otros medios que trajeron la misma historia en esta corrida.
    tambien_en: List[FuenteEnNoticia] = field(default_factory=list)
    cantidad_fuentes: int = 1

    def a_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def desde_dict(cls, data: Dict[str, Any]) -> "Noticia":
        campos = {f for f in cls.__dataclass_fields__}
        limpio = {k: v for k, v in data.items() if k in campos}
        limpio["tambien_en"] = [
            FuenteEnNoticia(**x) if isinstance(x, dict) else x
            for x in limpio.get("tambien_en", []) or []
        ]
        return cls(**limpio)


@dataclass
class ResultadoFuente:
    """Cómo le fue a una fuente en esta corrida. Alimenta el diagnóstico y la
    memoria de rotación de Facebook."""

    fuente_id: str
    estado: str  # ok | sin_novedades | bloqueada | error | omitida
    items: int = 0
    error: Optional[str] = None
    duracion_ms: int = 0

    def a_dict(self) -> Dict[str, Any]:
        return asdict(self)
