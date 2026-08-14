"""Interfaz de línea de comandos.

Cada subcomando corresponde a un job del workflow, y ninguno hace más de una
cosa:

    planificar     decide el reparto en grupos     (no toca la red)
    traer-rss      lee un lote de feeds            (red, sin estado)
    traer-facebook lee un grupo de páginas         (red + navegador, una IP)
    construir      arma feeds y JSON               (no toca la red)
    fuentes        lista lo configurado
    probar         prueba una fuente y muestra lo que trae
    todo           las tres etapas en un proceso (solo para probar en local)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

from . import planificador as plan
from .config import Configuracion, ErrorDeConfiguracion, cargar
from .estado import rotacion as rotacion_estado
from .pipeline import RAIZ, Rutas, construir, traer_facebook, traer_rss, correr_completo_sync


def _rutas(args: argparse.Namespace) -> Rutas:
    return Rutas(
        datos=Path(args.datos),
        feeds=Path(args.feeds),
        crudo=Path(args.crudo),
    )


def _config(args: argparse.Namespace) -> Configuracion:
    return cargar(args.ajustes, args.fuentes_dir)


def _ids(valor: str | None) -> List[str]:
    return [x.strip() for x in (valor or "").split(",") if x.strip()]


def _seleccionar(config: Configuracion, tipo: str, ids: List[str]):
    if not ids:
        return config.por_tipo(tipo)
    elegidas = [f for f in config.por_ids(ids) if f.tipo == tipo]
    faltantes = set(ids) - {f.id for f in elegidas}
    if faltantes:
        raise SystemExit(
            f"No hay fuentes de tipo '{tipo}' con estos ids: {sorted(faltantes)}"
        )
    return elegidas


# --------------------------------------------------------------------------

def cmd_planificar(args: argparse.Namespace) -> int:
    config = _config(args)
    rutas = _rutas(args)

    if args.tipo == "facebook":
        fuentes = config.por_tipo("facebook")
        ajustes = config.bloque("facebook")
        grupos = plan.planificar_facebook(
            fuentes,
            rotacion_estado.cargar(rutas.rotacion),
            tamano_grupo=args.tamano_grupo or int(ajustes.get("tamano_grupo", 2)),
            max_grupos=args.max_grupos or int(ajustes.get("max_paralelo", 16)),
        )
        etiqueta = "Facebook"
        nota = "Un job = una IP; Facebook deja pasar ~2 páginas por IP."
    else:
        fuentes = config.por_tipo("rss")
        grupos = plan.planificar_rss(
            fuentes, lotes=args.lotes or int(config.bloque("rss").get("lotes", 3))
        )
        etiqueta = "RSS"
        nota = "Sin límite por IP: se reparte solo para no depender de un job lento."

    if not grupos:
        raise SystemExit(f"No hay fuentes activas de tipo '{args.tipo}' en la configuración")

    # El resumen va a stderr para que stdout quede limpio y se pueda redirigir
    # entero a $GITHUB_OUTPUT.
    print(plan.resumen(grupos, etiqueta, nota), file=sys.stderr)
    print(f"matriz={plan.a_matriz(grupos)}")
    return 0


def cmd_traer_rss(args: argparse.Namespace) -> int:
    config = _config(args)
    rutas = _rutas(args)
    fuentes = _seleccionar(config, "rss", _ids(args.fuentes))
    print(f"Leyendo {len(fuentes)} feeds RSS (lote {args.lote or 'único'})...")

    _, resultados = asyncio.run(
        traer_rss(config, fuentes, rutas, Path(args.salida) if args.salida else None,
                  etiqueta=args.lote or "rss")
    )
    for resultado in resultados:
        marca = "ok " if resultado.estado in ("ok", "sin_novedades") else "ERR"
        print(f"  [{marca}] {resultado.fuente_id}: {resultado.estado} "
              f"({resultado.items} items, {resultado.duracion_ms} ms)"
              + (f" {resultado.error}" if resultado.error else ""))
    return 0


def cmd_traer_facebook(args: argparse.Namespace) -> int:
    config = _config(args)
    rutas = _rutas(args)
    fuentes = _seleccionar(config, "facebook", _ids(args.fuentes))
    if not fuentes:
        raise SystemExit("Este grupo no tiene ninguna fuente de Facebook")

    print(
        f"Grupo {args.grupo or '-'} (orden {args.orden}): "
        f"{len(fuentes)} páginas -> {[f.id for f in fuentes]}"
    )
    _, resultados = asyncio.run(
        traer_facebook(config, fuentes, rutas, args.orden,
                       Path(args.salida) if args.salida else None,
                       etiqueta=args.grupo or "facebook")
    )
    for resultado in resultados:
        print(f"  [{resultado.estado}] {resultado.fuente_id}: {resultado.items} publicaciones"
              + (f" — {resultado.error}" if resultado.error else ""))

    bloqueadas = sum(1 for r in resultados if r.estado == "bloqueada")
    if bloqueadas:
        # No es un fallo del job: es el cupo de la IP. El job termina en verde
        # a propósito, porque marcarlo rojo haría fallar corridas sanas.
        print(f"  {bloqueadas} fuente(s) bloqueadas por cupo de IP; la rotación las prioriza mañana.")
    return 0


def cmd_construir(args: argparse.Namespace) -> int:
    config = _config(args)
    rutas = _rutas(args)

    crudos: List[Path] = []
    for patron in args.crudos or []:
        ruta = Path(patron)
        if ruta.exists() and ruta.is_file():
            crudos.append(ruta)
        else:
            # Permite pasar comodines sin depender de que los expanda el shell.
            crudos.extend(sorted(Path(ruta.parent or ".").glob(ruta.name)))
    if not crudos:
        crudos = sorted(rutas.crudo.glob("*.json"))
    if not crudos:
        raise SystemExit(
            f"No hay archivos crudos para construir (busqué en {rutas.crudo}). "
            "Corré primero traer-rss / traer-facebook."
        )

    print(f"Construyendo desde {len(crudos)} archivo(s) crudo(s).")
    construir(config, crudos, rutas)
    return 0


def cmd_fuentes(args: argparse.Namespace) -> int:
    config = _config(args)
    fuentes = config.fuentes
    if args.tipo:
        fuentes = [f for f in fuentes if f.tipo == args.tipo]

    ancho = max((len(f.id) for f in fuentes), default=10)
    for fuente in sorted(fuentes, key=lambda f: (f.tipo, f.archivo, f.id)):
        estado = "" if fuente.activa else "  [INACTIVA]"
        print(f"{fuente.id.ljust(ancho)}  {fuente.tipo:9} p{fuente.peso}  "
              f"{fuente.categoria:11} {fuente.region:18} {fuente.nombre}{estado}")

    facebook = [f for f in config.fuentes if f.tipo == "facebook" and f.activa]
    tamano = int(config.bloque("facebook").get("tamano_grupo", 2))
    grupos = -(-len(facebook) // max(1, tamano)) if facebook else 0
    print(f"\nTotal: {len(fuentes)} fuentes listadas.")
    print(f"Facebook: {len(facebook)} páginas / grupos de {tamano} = {grupos} jobs (IPs) por corrida.")
    return 0


def cmd_probar(args: argparse.Namespace) -> int:
    config = _config(args)
    rutas = _rutas(args)
    fuente = config.obtener(args.fuente)
    if fuente is None:
        raise SystemExit(f"No existe la fuente '{args.fuente}'. Probá: fuentes")

    print(f"Probando {fuente.id} ({fuente.tipo}) -> {fuente.url}\n")
    if fuente.tipo == "facebook":
        items, resultados = asyncio.run(traer_facebook(config, [fuente], rutas))
    else:
        items, resultados = asyncio.run(traer_rss(config, [fuente], rutas))

    for resultado in resultados:
        print(f"Estado: {resultado.estado} ({resultado.duracion_ms} ms)")
        if resultado.error:
            print(f"Error: {resultado.error}")

    for item in items[:args.limite]:
        print("\n---")
        print(f"  título    : {item.titulo[:160]}")
        print(f"  fecha     : {item.publicado_en}")
        print(f"  url       : {item.url}")
        print(f"  imagen    : {item.imagenes[0] if item.imagenes else '-'}")
        print(f"  resumen   : {item.resumen[:200]}")
    print(f"\n{len(items)} publicaciones traídas.")
    return 0


def cmd_todo(args: argparse.Namespace) -> int:
    config = _config(args)
    correr_completo_sync(config, _rutas(args), con_facebook=not args.sin_facebook)
    return 0


# --------------------------------------------------------------------------

def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="noticias",
        description="Agregador de noticias del mundo: lee RSS y Facebook, y publica feeds RSS.",
    )
    parser.add_argument("--ajustes", default=str(RAIZ / "config" / "ajustes.yaml"))
    parser.add_argument("--fuentes-dir", default=str(RAIZ / "config" / "fuentes"))
    parser.add_argument("--datos", default=str(RAIZ / "datos"))
    parser.add_argument("--feeds", default=str(RAIZ / "feeds"))
    parser.add_argument("--crudo", default=str(RAIZ / "crudo"))

    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("planificar", help="Imprime la matrix de grupos para CI")
    p.add_argument("--tipo", choices=["facebook", "rss"], default="facebook")
    p.add_argument("--tamano-grupo", type=int, default=None,
                   help="Fuentes de Facebook por job. Default: el de ajustes.yaml (2). "
                        "Cada job es una IP y Facebook deja pasar ~2 páginas por IP.")
    p.add_argument("--max-grupos", type=int, default=None,
                   help="Tope de jobs en paralelo (límite del plan de CI).")
    p.add_argument("--lotes", type=int, default=None, help="Lotes para RSS.")
    p.set_defaults(func=cmd_planificar)

    p = sub.add_parser("traer-rss", help="Lee un lote de feeds RSS")
    p.add_argument("--fuentes", default=None, help="IDs separados por coma (default: todas)")
    p.add_argument("--lote", default=None)
    p.add_argument("--salida", default=None, help="Archivo crudo de salida")
    p.set_defaults(func=cmd_traer_rss)

    p = sub.add_parser("traer-facebook", help="Lee un grupo de páginas de Facebook")
    p.add_argument("--fuentes", default=None, help="IDs separados por coma (default: todas)")
    p.add_argument("--grupo", default=None)
    p.add_argument("--orden", type=int, default=0,
                   help="Índice del grupo. Decide el escalonado y qué proxy le toca.")
    p.add_argument("--salida", default=None, help="Archivo crudo de salida")
    p.set_defaults(func=cmd_traer_facebook)

    p = sub.add_parser("construir", help="Arma feeds y JSON a partir de los crudos")
    p.add_argument("--crudos", nargs="*", default=None,
                   help="Archivos crudos (acepta comodines). Default: todos los de crudo/")
    p.set_defaults(func=cmd_construir)

    p = sub.add_parser("fuentes", help="Lista las fuentes configuradas")
    p.add_argument("--tipo", choices=["facebook", "rss"], default=None)
    p.set_defaults(func=cmd_fuentes)

    p = sub.add_parser("probar", help="Prueba una sola fuente y muestra lo que trae")
    p.add_argument("fuente")
    p.add_argument("--limite", type=int, default=5)
    p.set_defaults(func=cmd_probar)

    p = sub.add_parser("todo", help="Corre todo en un proceso (solo para local)")
    p.add_argument("--sin-facebook", action="store_true")
    p.set_defaults(func=cmd_todo)

    return parser


def main(argv: List[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return args.func(args)
    except ErrorDeConfiguracion as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrumpido.", file=sys.stderr)
        return 130
