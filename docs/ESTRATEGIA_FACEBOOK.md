# Estrategia de Facebook

Este documento existe para que nadie —incluido tu yo de dentro de seis meses—
vuelva a intentar las cosas que ya se probaron y no funcionan.

## El dato

**Facebook deja pasar alrededor de 2 páginas públicas por IP** antes de
devolver la pantalla de bloqueo/login en lugar del contenido.

Es un límite por dirección de salida, no por comportamiento. Se comprobó
corriendo el mismo scraper con distintas configuraciones desde un mismo runner:
el corte llega en la misma posición —la segunda o tercera página— sin importar
qué se cambie dentro del job.

## Lo que NO mueve la aguja

Todo esto se probó. Ninguna de estas cosas hace que la tercera página pase:

| Intento | Resultado |
|---|---|
| Pausas más largas entre páginas (8 s → 30 s → 60 s) | Igual. El corte llega en la misma página, solo que más tarde. |
| Cambiar el User-Agent | Igual, y un UA raro empeora las cosas. |
| Más reintentos sobre la misma página | Igual: la IP ya está marcada. |
| Más scrolls o esperas de carga | No tiene relación con el bloqueo. |
| Grupos más grandes con pausas | Peor: se pierden más fuentes detrás del bloqueo. |

La conclusión no es "hay que insistir mejor". Es que el recurso escaso son las
**IPs**, y hay que administrarlo como tal.

## Lo que sí funciona

### 1. Más IPs: un job de CI por grupo

Cada job de GitHub Actions corre en un runner nuevo, con su propia IP de
salida. Con 80 páginas y grupos de 2, la matriz contiene 40 grupos; el workflow limita la concurrencia a 16.

Está en `.github/workflows/noticias.yml`, en la matriz del job `facebook`.

### 2. Grupos chicos: `tamano_grupo: 2`

Con grupos de 2, detrás de una página bloqueada queda **una sola** página más.
Con grupos de 5 se perdían hasta 4 de un solo golpe.

Agrandar el grupo **no retrasa el bloqueo**; solo pone más fuentes detrás de
él. Es la confusión más fácil de cometer acá.

### 3. Round-robin, no bloques

El primer turno de cada grupo es el que casi siempre pasa: la IP todavía tiene
el cupo intacto. Por eso las fuentes se ordenan por urgencia y se reparten
**una por grupo**:

```
prioridad:  A  B  C  D  E  F
grupos:     g1[A,D]  g2[B,E]  g3[C,F]        ← round-robin: A, B y C tienen turno bueno
NO:         g1[A,B]  g2[C,D]  g3[E,F]        ← bloques: A y B compiten en el mismo job
```

Está en `noticias/planificador.py`.

### 4. Memoria entre corridas

`datos/_interno/rotacion_facebook.json` guarda cuándo fue el último éxito de
cada página. La que lleva más tiempo sin traer datos sube al primer turno en la
corrida siguiente. Con el cron cada hora, en pocas vueltas todas pasan por un
turno bueno aunque en una corrida puntual algunas queden bloqueadas.

Detalle que importa: **una fuente bloqueada no pierde prioridad**. El bloqueo
es de la IP, no de la fuente. Solo baja de prioridad la que falla por su cuenta
—página renombrada, borrada o privada—, y por eso `estado/rotacion.py`
distingue `bloqueada` de `error` en todo el recorrido.

### 5. Proxies (opcional): más IPs sin más jobs

Si definís el secret `NOTICIAS_PROXIES` con una lista separada por comas:

```
http://usuario:clave@host1:8080,http://usuario:clave@host2:8080
```

cada grupo sale por un proxy distinto (`orden % cantidad`) y el cupo por IP se
multiplica por la cantidad de proxies, sin agregar un solo job. Sin el secret,
cada grupo usa la IP de su runner, que ya es distinta por job.

Implementado en `noticias/fuentes/facebook.py`, función `proxy_para_grupo`.

## Higiene dentro del job

No son trucos para esquivar el bloqueo —no lo esquivan—; son decisiones operativas del scraper:

- **Arranque escalonado.** Varios runners golpeando en el mismo segundo desde
  rangos contiguos de Azure es un patrón, aunque las IPs sean distintas.
- **Viewport variado.** Si todos los runners reportan 1280x900 clavado, esa
  medida agrupa la flota entera bajo una misma huella.
- **Un solo contexto de navegador por grupo, sin pestañas en paralelo.** Abrir
  las 2 páginas a la vez quema el cupo de golpe en vez de aprovecharlo.
- **Sin User-Agent propio.** El de Chromium real ya sirve.
- **Pausa con ruido** entre páginas: una espera de exactamente 9.000 s repetida
  igual en todos los jobs delata más que la pausa en sí.

Lo que **no** se hace, y no se va a hacer: iniciar sesión, usar cookies de
usuario, resolver captchas o descargar streams internos de video. Solo se leen
páginas públicas y se conserva el enlace público del post.

## Cómo crecer sin romper esto

La cuenta es directa:

```
jobs necesarios = ceil(cantidad_de_páginas / tamano_grupo)
```

Ese número tiene que quedar por debajo o igual a `facebook.max_paralelo` en
`config/ajustes.yaml`. Hoy el planificador permite 40 grupos para cubrir 80
páginas. La concurrencia real está separada: `.github/workflows/noticias.yml`
usa `max-parallel: 16`, así que los demás grupos esperan su turno.

Si querés sumar páginas y ya no entran:

1. **Subí el tope de grupos del planificador** (`max_paralelo`) si agregás más páginas.
2. **Agregá proxies** con `NOTICIAS_PROXIES`. Multiplica IPs sin tocar jobs.
3. **Bajá la frecuencia del cron** y dejá que la rotación cubra más fuentes en
   más vueltas.
4. Lo que **no** hay que hacer: subir `tamano_grupo`. Es exactamente el cambio
   que devuelve el problema original.

Hay un test que falla si la lista de páginas crece más allá del tope:
`tests/test_config.py::test_la_configuracion_real_no_pide_mas_jobs_de_los_permitidos`.

## Cómo saber si está funcionando

En `datos/estado_fuentes.json`, campo `resumen.bloqueadas`.

- **0-2 por corrida:** normal. La rotación las recupera en la vuelta siguiente.
- **Sube y no baja:** faltan IPs. Más jobs o proxies.
- **Una fuente puntual siempre en `error`** (no `bloqueada`): esa página está
  rota, cambiada o es privada. Corregí la URL o marcala `activa: false`.
