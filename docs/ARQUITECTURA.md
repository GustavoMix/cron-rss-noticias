# Arquitectura

## La idea en una línea

Tres etapas que no se conocen entre sí, unidas por dos estructuras de datos y
por archivos en disco.

```
  FUENTES                PROCESO                     SALIDA
  ───────                ───────                     ──────
  rss.py       ─┐                                 ┌→ feed_rss.py   → feeds/*.xml
                ├→ ItemCrudo → normalizador  ─┐   │
  facebook.py  ─┘                             ├──→┼→ json_salida.py → datos/*.json
                              deduplicador ───┤   │
                              clasificador ───┘   └→ indice.py      → feeds/index.html
                                    ↓
                                 Noticia
```

- Los **lectores** no saben qué es una categoría ni qué es un feed de salida.
- El **proceso** no sabe si el dato vino de un XML o de un navegador.
- La **salida** no sabe nada de red.

Entre etapas viajan solo `ItemCrudo` y `Noticia` (`noticias/modelos.py`).

## Por qué las etapas también están separadas en el tiempo

Cada etapa corre en un job de CI distinto, y no por prolijidad:

| Etapa | Necesita | Restricción |
|---|---|---|
| `traer-rss` | Red | Ninguna: son archivos estáticos en CDN |
| `traer-facebook` | Red + navegador | **Una IP por grupo**, ~2 páginas de cupo |
| `construir` | Nada | Es el único que escribe en el repo |

Esa tercera columna es la que fuerza la separación. Si Facebook y RSS
compartieran proceso, no habría forma de darle a cada grupo de Facebook su
propia IP. Ver [`ESTRATEGIA_FACEBOOK.md`](ESTRATEGIA_FACEBOOK.md).

El formato de intercambio entre jobs son los archivos de `crudo/`:

```json
{
  "etiqueta": "g01",
  "momento": "2026-08-14T03:17:00+00:00",
  "items":      [ ... ItemCrudo ... ],
  "resultados": [ {"fuente_id": "fb_cnn", "estado": "bloqueada", ...} ],
  "extra":      {"cache_rss": {"rss_bbc_world": {"etag": "..."}}}
}
```

Efecto secundario útil: se puede reprocesar todo —cambiar el clasificador,
arreglar el deduplicador— **sin volver a tocar ninguna fuente**. Los crudos
están en disco.

## Los dos tipos de memoria

Ambos viven en `datos/_interno/` y se commitean, porque son estado que tiene
que sobrevivir a un runner efímero.

### `historial.json` — noticias acumuladas

Los feeds se arman con esto, no solo con lo de la última corrida. Un lector que
consulta cada seis horas vería un feed casi vacío si no existiera.

También es lo que hace que el `guid` sea estable y que republicar una nota
vieja no la devuelva al tope del feed.

### `rotacion_facebook.json` — turnos de Facebook

Cuándo trajo datos por última vez cada página. Decide a quién le toca el primer
turno de cada grupo, que es el que casi siempre esquiva el bloqueo.

## Decisiones que parecen raras y no lo son

**El bloqueo se chequea solo cuando no se encontró ningún post.**
Facebook incluye el formulario de login en el DOM de cualquier página pública
para visitantes sin sesión, incluso cuando el feed real cargó bien. Chequear
antes daba falsos positivos constantes.

**Un job de Facebook con fuentes bloqueadas termina en verde.**
El bloqueo es un estado esperado del sistema, no un fallo. Marcarlo rojo haría
fallar corridas perfectamente sanas y entrenaría a ignorar el CI.

**`construir` corre con `always()`.**
Un grupo bloqueado o un feed caído no puede impedir que se publique todo lo que
sí llegó. Con ~90 fuentes, que algo falle es lo normal, no la excepción.

**Una nota sin fecha usa el momento de detección, no una fecha inventada.**
Facebook entrega fechas en prosa ("hace 3 h", "Ayer"). Cuando no se entienden,
la nota se ordena por cuándo la vimos: es honesto y no la manda a un lugar
arbitrario del feed.

**La clasificación es por palabras clave, no por modelo.**
Tiene que correr en segundos dentro de un runner, ser explicable —"¿por qué
esta nota quedó en deportes?"— y no depender de ninguna API que pueda caerse o
cobrar. Las reglas están en `proceso/clasificador.py`, en tablas legibles.

**La URL publicada y la URL de comparación son distintas.**
`canonizar_url` deja el enlace navegable (conserva `www.`); `clave_url` además
borra `www.` y la barra final para comparar. Sin esa distinción, o se pierden
duplicados o se publican enlaces que redirigen de más.

## Dónde tocar según qué quieras cambiar

| Quiero… | Archivo |
|---|---|
| Agregar o sacar medios | `config/fuentes/*.yaml` |
| Cambiar timeouts, límites, ventanas | `config/ajustes.yaml` |
| Cambiar cómo se reparten los jobs | `noticias/planificador.py` |
| Cambiar qué se considera duplicado | `noticias/proceso/deduplicador.py` |
| Agregar un tema o afinar la clasificación | `noticias/proceso/clasificador.py` |
| Cambiar qué feeds se generan | `noticias/salida/feed_rss.py` |
| Cambiar la frecuencia del cron | `.github/workflows/noticias.yml` |
| Soportar una fuente de otro tipo (p. ej. Telegram) | Nuevo módulo en `noticias/fuentes/` + `tipo` en `config.py` |
