# mangrovex.github.io

Sitio personal de **Manuel Vega** con el mapa de desarrollos públicos y privados.

- **Desarrollos:** https://mangrovex.github.io
- **IBO – Icon Builder for Odoo:** https://mangrovex.github.io/ibo/ (basado en el trabajo de [spilymp](https://github.com/spilymp/iob))

## Cómo se actualiza

La página carga `data/projects.json`, que genera la Action **Sincronizar proyectos**
(`.github/workflows/sync-projects.yml`) cada 6 horas, o a mano desde la pestaña *Actions*:

1. Lee `data/projects.yml` (tarjetas, textos, estados y categorías que defines tú).
2. Consulta la API de GitHub con el secreto `GH_PAT` (token de solo lectura) y agrega
   descripción, lenguaje, estrellas y fecha del último push de cada repo.
3. Si hay cambios, hace commit de `data/projects.json`.

Reglas de visibilidad:

- Los repos **privados** solo aparecen si están en `projects.yml` o si les pones el topic
  `portafolio` en GitHub.
- Los repos **públicos** que no estén en una tarjeta pasan a "Archivo y formación",
  salvo los listados en `exclude`.

Para agregar o cambiar un proyecto, edita `data/projects.yml`; la Action se ejecuta sola al guardar.
