# JSON para Android / Kotlin

`datos/noticias.json` usa el esquema **1.1**. Conserva los campos planos del
formato anterior y agrega bloques estables para que la app no tenga que inferir
canal, horario, multimedia ni métricas desde texto libre.

## Estructura recomendada

Cada noticia mantiene `id`, `titulo`, `resumen`, `url`, `fuente_*`,
`publicado_en`, etc. Además incorpora:

- `plataforma`: `facebook` o `rss`.
- `collector`: `public_web` para Facebook y `rss` para feeds.
- `post_id`: id del post/video/reel de Facebook cuando puede extraerse del permalink.
- `contenido`: texto más completo disponible de la publicación.
- `canal`: id, nombre, URL, usuario, icono, idioma, región, categoría y peso.
- `fecha_hora`: UTC, `epoch_ms` y la misma fecha/hora convertida a `America/La_Paz`.
- `detectado_fecha_hora`: el mismo formato para el momento de detección.
- `media`: imagen principal, lista de imágenes, video y booleanos simples.
- `metricas`: reacciones, comentarios y compartidos; pueden ser `null` si Facebook no los expone.
- `clasificacion`: tema, regiones, etiquetas e importancia.
- `duplicados`: otros medios que publicaron la misma historia.

Los campos que Facebook no publique quedan en `null` o listas vacías; no se
cambian de tipo. Eso permite DTOs Kotlin con valores nullable/default sin lógica
especial por cada medio.

## DTO mínimo con kotlinx.serialization

```kotlin
@Serializable
data class NoticiasPayload(
    val version_esquema: String,
    val generado_en: String,
    val noticias: List<NoticiaDto> = emptyList()
)

@Serializable
data class NoticiaDto(
    val id: String,
    val titulo: String = "",
    val resumen: String = "",
    val contenido: String = "",
    val url: String,
    val plataforma: String,
    val collector: String,
    val post_id: String? = null,
    val canal: CanalDto,
    val fecha_hora: FechaHoraDto,
    val detectado_fecha_hora: FechaHoraDto,
    val media: MediaDto,
    val metricas: MetricasDto,
    val clasificacion: ClasificacionDto
)

@Serializable
data class CanalDto(
    val id: String,
    val nombre: String,
    val tipo: String,
    val pagina_url: String,
    val usuario: String? = null,
    val icono_url: String? = null,
    val idioma: String,
    val region: String? = null,
    val categoria_base: String? = null,
    val peso: Int
)

@Serializable
data class FechaHoraDto(
    val iso_utc: String? = null,
    val epoch_ms: Long? = null,
    val fecha_utc: String? = null,
    val hora_utc: String? = null,
    val iso_bolivia: String? = null,
    val fecha_bolivia: String? = null,
    val hora_bolivia: String? = null,
    val zona_bolivia: String = "America/La_Paz"
)

@Serializable
data class MediaDto(
    val imagen_principal: String? = null,
    val imagenes: List<String> = emptyList(),
    val video_url: String? = null,
    val tiene_imagen: Boolean = false,
    val tiene_video: Boolean = false
)

@Serializable
data class MetricasDto(
    val reacciones: Int? = null,
    val comentarios: Int? = null,
    val compartidos: Int? = null
)

@Serializable
data class ClasificacionDto(
    val categoria_principal: String,
    val categorias: List<String> = emptyList(),
    val regiones: List<String> = emptyList(),
    val etiquetas: List<String> = emptyList(),
    val importancia: Int = 0
)
```

Para tolerar campos nuevos en futuras versiones, configurar el parser con
`Json { ignoreUnknownKeys = true }`.
