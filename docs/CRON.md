# El cron en GitHub Actions

## Qué corre y cuándo

Workflow: `.github/workflows/noticias.yml`

- **Automático:** cada hora, `17 * * * *` (UTC). El minuto 17 y no el 0 porque
  a las en punto dispara medio GitHub y los runners tardan más en asignarse.
- **Manual:** pestaña *Actions* → *Actualizar noticias* → *Run workflow*.
  Acepta dos parámetros: `tamano_grupo` (páginas de Facebook por job) y
  `saltar_facebook` (correr solo RSS).

## Las cuatro etapas

```
planificar ──┬──→ rss        (3 jobs)   ──┐
             └──→ facebook  (15 jobs)  ──┴──→ construir → commit
```

1. **planificar** — lee la rotación guardada y reparte las fuentes en grupos.
   Imprime dos matrices para `fromJSON()`. No toca la red.
2. **rss** — 3 jobs en paralelo, ~20 feeds cada uno. Reparto solo para no
   depender de un job lento.
3. **facebook** — 15 jobs, 2 páginas cada uno. **Cada job es una IP**: es la
   razón de ser de todo el fan-out. Ver
   [`ESTRATEGIA_FACEBOOK.md`](ESTRATEGIA_FACEBOOK.md).
4. **construir** — baja los artefactos de todos los jobs, arma feeds y JSON, y
   commitea. Corre con `always()`: lo que llegó se publica aunque algún job
   haya fallado.

Duración típica: 6-9 minutos, casi todo en los jobs de Facebook (instalar
Chromium y las pausas entre páginas).

## Qué se commitea en cada corrida

```
feeds/                        los XML y el índice
datos/noticias.json           salida para consumir
datos/estado_fuentes.json     diagnóstico
datos/_interno/historial.json         memoria de noticias
datos/_interno/rotacion_facebook.json memoria de turnos de Facebook
datos/_interno/cache_rss.json         ETag/Last-Modified de cada feed
```

Los dos archivos de `_interno` con memoria son **importantes**: sin ellos el
feed se reinicia en cada corrida y la rotación de Facebook pierde el hilo.

`crudo/` está en `.gitignore`: se regenera en cada corrida.

## Antes de confiar en el cron

1. Subí el proyecto.
2. *Actions* → *Actualizar noticias* → *Run workflow*, una vez a mano.
3. Que termine en verde.
4. Revisá el **Summary** del run: dice cuántas fuentes dieron ok, bloqueada y
   error.
5. Abrí `feeds/index.html` (o `feeds/mundo.xml`) y confirmá que hay items.
6. Corregí en `config/fuentes/*.yaml` las URLs que aparezcan en `error`.

El paso 6 es esperable en la primera corrida: las URLs de feeds RSS cambian con
el tiempo y algunos medios responden 403 a clientes automatizados. Lo que está
en `error` se corrige o se marca `activa: false`; lo que está en `bloqueada`
**no** es un problema de configuración.

## Permisos, rama por defecto y repositorio privado

El workflow usa el `GITHUB_TOKEN` del propio repo con `contents: write`.

**El cron programado solo se dispara en la rama por defecto del repositorio.**
Como este repo se creó vacío, GitHub dejó como rama por defecto la primera que
recibió: `claude/cron-rss-news-feed-hwyv4o`. Es decir que el cron funciona tal
como está. Si preferís renombrarla a `main` (Settings → Branches), acordate de
actualizar `sitio.base_feeds` en `config/ajustes.yaml`, que lleva el nombre de
la rama en la URL.

El repositorio es **privado** hoy. Eso implica dos cosas:

- Las URLs `raw.githubusercontent.com/...` de los feeds piden autenticación, así
  que **ningún lector de RSS puede suscribirse todavía**. Para publicarlos:
  hacer público el repo, o servir `feeds/` por GitHub Pages / hosting estático.
- Los minutos de Actions se descuentan del cupo mensual (ver *Costo*, abajo).

Si la rama tiene reglas de protección que bloquean pushes directos de Actions,
el paso de guardar va a fallar: hay que permitir a `github-actions[bot]` o
apuntar el workflow a otra rama.

## Publicar los feeds

Tres opciones, de menos a más:

1. **Crudo del repo** (ya funciona, repo público):
   `https://raw.githubusercontent.com/<usuario>/cron-rss-noticias/main/feeds/mundo.xml`
2. **GitHub Pages**: activalo sobre la rama y la carpeta `feeds/`. Queda una
   URL más linda y `feeds/index.html` como portada.
3. **Dominio propio**: cualquier hosting estático sirviendo `feeds/`.

En los casos 2 y 3, actualizá `sitio.base_feeds` en `config/ajustes.yaml`: es
lo que se escribe en `<atom:link rel="self">`, que un lector usa para saber si
el feed se mudó.

## Costo

Con 19 jobs por corrida y ~7 minutos de reloj, una corrida por hora consume del
orden de 20-25 minutos-runner, casi todo en los jobs de Facebook.

**En un repositorio público los minutos de Actions son gratis.** En uno privado
—como está hoy— se descuentan del cupo mensual, y a una corrida por hora ese
cupo se agota rápido. Tres formas de bajarlo, de menos a más agresiva:

1. Bajar la frecuencia del cron a cada 3 o 6 horas (`0 */3 * * *`). La rotación
   sigue funcionando, solo tarda más vueltas en cubrir todas las páginas.
2. Correr solo RSS en las corridas intermedias: los jobs de RSS son 3 y rápidos
   (no instalan Chromium), y son los que traen la mayor parte del volumen.
3. Hacer público el repositorio, que además resuelve la publicación de los
   feeds.
