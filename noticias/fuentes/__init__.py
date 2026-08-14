"""Lectores de fuentes. Uno por familia, con políticas de red opuestas:
`rss` pide en paralelo sin límite; `facebook` va de a una porque comparte el
cupo de ~2 páginas por IP del job que lo ejecuta."""
