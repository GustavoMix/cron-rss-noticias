# Noticias del Mundo — cron de feeds RSS

Agregador automático de noticias internacionales. Lee **feeds RSS** de agencias
y medios de todo el mundo y **páginas públicas de Facebook**, junta la misma
historia contada por varios medios en un solo item, la clasifica por tema y
región, y publica el resultado como **feeds RSS listos para cualquier lector**.

Corre solo, cada hora, con GitHub Actions. No necesita servidor.

```
     RSS (61 fuentes)  ─┐
                        ├─→  normalizar → deduplicar → clasificar  →  feeds/*.xml
     Facebook (80 pág.) ─┘                                             datos/*.json
```

## Lo que genera

| Archivo | Qué es |
|---|---|
| `feeds/mundo.xml` | Todo, lo más reciente primero |
| `feeds/destacadas.xml` | Lo que más medios distintos están publicando |
| `feeds/tema-*.xml` | Un feed por tema: mundo, política, economía, tecnología, ciencia, salud, ambiente, deportes, cultura, sociedad, conflictos |
| `feeds/region-*.xml` | Un feed por región: América Latina, Europa, Asia, África, Medio Oriente… |
| `feeds/idioma-*.xml` | Un feed por idioma (es / en) |
| `feeds/index.html` | Índice navegable de todos los feeds |
| `datos/noticias.json` | Lo mismo en JSON, para consumir desde una app |
| `datos/estado_fuentes.json` | Diagnóstico: **por qué** una fuente trajo 0 items |

Para suscribirse desde un lector, la URL es la del archivo crudo del repo:

```
https://raw.githubusercontent.com/GustavoMix/cron-rss-noticias/<rama-por-defecto>/feeds/mundo.xml
```

**Mientras el repositorio sea privado esa URL pide autenticación**, así que
ningún lector de RSS va a poder abrirla. Para que los feeds sean públicos hay
que hacer público el repo o servir `feeds/` por GitHub Pages o un hosting
estático; en cualquiera de esos casos hay que actualizar `sitio.base_feeds` en
`config/ajustes.yaml`. Ver [`docs/CRON.md`](docs/CRON.md).

## Por qué está partido en tantos jobs

Porque Facebook **deja pasar unas 2 páginas públicas por IP** antes de devolver
la pantalla de bloqueo. Eso no se arregla con pausas más largas, otro
User-Agent ni más reintentos: el límite lo lleva la IP, no el patrón de
tráfico.

La única palanca real es **más IPs y grupos más chicos**. Un job de GitHub
Actions es un runner, y un runner es una IP. Así que:

- 80 páginas ÷ 2 por grupo = **40 grupos de trabajo**; el workflow ejecuta **hasta 16 a la vez** y el resto queda en cola.
- Detrás de una página bloqueada queda **como mucho una sola** página más.
- La rotación guardada en el repo le da el primer turno de cada grupo —el que
  casi siempre pasa— a la fuente que lleva más tiempo sin traer datos.

El detalle completo, con los números y lo que ya se probó y no funcionó, está
en [`docs/ESTRATEGIA_FACEBOOK.md`](docs/ESTRATEGIA_FACEBOOK.md).

## Uso

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium   # solo si vas a usar Facebook

python main.py fuentes                 # ver todo lo configurado
python main.py probar rss_bbc_mundo    # probar una fuente y ver qué trae
python main.py todo --sin-facebook     # corrida completa solo con RSS
python main.py todo                    # corrida completa (ojo: una sola IP)
```

`todo` sirve para probar en local. En producción va siempre el camino de tres
etapas, que es lo que hace el workflow:

```bash
python main.py planificar --tipo facebook          # arma los grupos
python main.py traer-rss --fuentes a,b --salida crudo/rss_r01.json
python main.py traer-facebook --fuentes x,y --orden 0 --salida crudo/fb_g01.json
python main.py construir                            # junta todo y publica
```

## Agregar o sacar fuentes

Las fuentes viven en `config/fuentes/`, un archivo por familia:

```
config/fuentes/agencias.yaml    agencias y organismos (ONU, OMS…)
config/fuentes/mundo_en.yaml    medios globales en inglés
config/fuentes/mundo_es.yaml    prensa en español
config/fuentes/temas.yaml       tecnología, ciencia, economía, deportes, cultura
config/fuentes/facebook.yaml    páginas públicas de Facebook
```

Una fuente RSS es una entrada más en el YAML:

```yaml
  - id: rss_mi_medio
    nombre: Mi Medio
    tipo: rss
    url: https://mimedio.com/feed/
    idioma: es
    categoria: mundo
    region: América Latina
    peso: 3          # 1-5; decide qué versión gana cuando hay duplicados
```

Para Facebook vale lo mismo con `tipo: facebook`. Con `tamano_grupo: 2`, cada
dos páginas forman un grupo. `facebook.max_paralelo` en `config/ajustes.yaml`
es el tope de grupos que genera el planificador; hoy está en 40 para las 80
páginas. El workflow mantiene `max-parallel: 16`, por lo que GitHub ejecuta 16
grupos a la vez y deja los demás en cola sin agrandar los grupos.

Después de tocar la lista:

```bash
python -m pytest tests -q      # valida ids repetidos, URLs, cupo de jobs
python main.py fuentes         # muestra cuántos jobs pide Facebook ahora
```

## Cuando algo no aparece en los feeds

Mirá `datos/estado_fuentes.json`. La diferencia importante:

| Estado | Qué significa | Qué hacer |
|---|---|---|
| `ok` | Trajo publicaciones | — |
| `sin_novedades` | Cargó bien, no había nada nuevo (o RSS respondió 304) | Nada |
| `bloqueada` | Facebook cortó por cupo de IP | **Más jobs/IPs**, no más reintentos |
| `error` | La fuente está rota: feed movido, página borrada o privada | Corregir la URL o desactivarla |

`bloqueada` y `error` son problemas distintos y se arreglan distinto; por eso
el sistema no los mezcla en ninguna parte.

## Cómo está organizado el código

```
main.py                     punto de entrada, tres líneas
noticias/
  cli.py                    un subcomando por job de CI
  config.py                 carga y valida config/ (falla temprano y con nombre)
  modelos.py                ItemCrudo y Noticia: la frontera entre etapas
  planificador.py           el reparto en grupos: acá vive la estrategia
  pipeline.py               orquestación de las tres etapas
  fuentes/rss.py            lector RSS: paralelo, con ETag
  fuentes/facebook.py       lector Facebook: secuencial, una IP por grupo
  proceso/normalizador.py   limpiar, fechar, filtrar
  proceso/deduplicador.py   agrupar la misma historia de varios medios
  proceso/clasificador.py   tema, región e importancia
  salida/feed_rss.py        generación del XML
  salida/json_salida.py     JSON de consumo y de diagnóstico
  estado/historial.py       memoria de noticias entre corridas
  estado/rotacion.py        memoria de turnos de Facebook
docs/                       estrategia, arquitectura, cron y lista de fuentes
tests/                      73 tests, sin red
```

La regla que mantiene todo esto separado: los lectores no saben nada de
categorías ni de RSS de salida, y el proceso no sabe de dónde vino el dato.
Entre medio solo viajan `ItemCrudo` y `Noticia`.
