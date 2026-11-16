# PAUsible

El examen más PAUsible de la PAU 2027 (selectividad), por comunidad autónoma y materia. Una aplicación web de un solo fichero, gratuita y sin registro.

**Usar la app:** https://fborrasumh.github.io/pausible/

**Idiomas:** español (por defecto), inglés y portugués. Se cambia en la barra superior o con `?lang=en` / `?lang=pt`.

> PAUsible **no es oficial** ni tiene relación con las universidades ni con las comisiones de la PAU. Las predicciones son probabilidades calculadas con exámenes de años anteriores y no anticipan el examen real: hay que estudiar todo el temario.

## Qué hace

1. **Predicción por comunidad y materia.** Calcula la probabilidad de que cada tema aparezca en el examen de 2027 a partir de los exámenes oficiales de 2022 a 2026. Para cada tema muestra cuántas veces salió, cuándo fue la última, su tendencia, un fragmento del enunciado real con enlace al PDF oficial y la probabilidad media en toda España.
2. **Comprobación del método a la vista.** Cada predicción se pone a prueba ocultando el último examen ordinario y prediciéndolo con los anteriores. El estudiante ve cuántos temas habría acertado el método y cuántos acertaría el azar; de ahí sale la confianza (alta, media o baja).
3. **Examen probable con solución revisada.** Exámenes originales con el formato de cada comunidad, centrados en los temas más probables y resueltos por varios agentes de IA que se vigilan entre sí (ver más abajo). Incluyen cronómetro opcional de 90 minutos, solución y criterios de corrección por pregunta, y autocorrección que calcula la nota del simulacro.
4. **Compartir y retar.** Tarjeta en formato historia (1080×1920) dibujada en el propio dispositivo, botón de compartir, WhatsApp y un enlace de reto que abre a la otra persona **exactamente el mismo examen** junto con tu nota:
   - examen de PAUsible → `?c=madrid&m=matematicas2&n=7.5&v=<huella>`. Si el examen se regenera, la versión anterior queda en `data/examenes/archivo/` y el reto la sigue abriendo;
   - examen generado por el estudiante con su clave → el examen entero, comprimido, en la parte del enlace que va detrás de `#`. No pasa por ningún servidor ni se sube al repositorio. Si el enlace es demasiado largo para algún sitio, se puede enviar como fichero `.json` y abrirlo desde la portada.
5. **Historial.** Cada estudiante conserva en su navegador hasta 5 exámenes generados por comunidad y materia, y elige cuál hacer: el de PAUsible, un reto recibido o uno suyo.
6. **Ranking de España.** Qué comunidad tiene la PAU más previsible y qué temas caen en casi toda España en cada materia.
7. **Guía de la clave de IA.** Cómo conseguir una clave con límite de gasto, cuánto cuesta, qué exige cada proveedor por edad y en qué se diferencia de una suscripción mensual al chatbot.
8. **Ejemplo sin clave ni datos** (Matemáticas II), con predicción ficticia marcada como tal y soluciones comprobadas con sympy.

## Cobertura actual

Exámenes oficiales con texto en el corpus a 16 de noviembre de 2026. Se actualiza en `data/cobertura.json` con cada ejecución.

| Comunidad | Exámenes | Materias | Años | Estado |
|---|---:|---:|---|---|
| Comunidad de Madrid | 1.034 | 32 | 2022-2026 | completa |
| Región de Murcia | 599 | 29 | 2022-2026 | completa |
| País Vasco | 548 | 32 | 2022-2026 | completa |
| Comunidad Foral de Navarra | 500 | 31 | 2022-2026 | completa |
| Cataluña | 484 | 29 | 2022, 2024-2026 | casi completa |
| Comunitat Valenciana | 453 | 31 | 2022-2026 | completa |
| Canarias | 361 | 30 | 2022-2026 | completa |
| Aragón | 303 | 29 | 2022-2026 | completa |
| Cantabria | 258 | 28 | 2023-2026 | casi completa |
| Andalucía | 142 | 27 | 2025-2026 | en curso: faltan ZIP de 2022-2024 |
| Castilla y León | 133 | 30 | 2025-2026 | faltan 2022-2024 |
| Galicia | 64 | 23 | 2025-2026 | en curso: faltan 2022-2024 y PDF escaneados |
| Principado de Asturias | 6 | 5 | 2024-2026 | no se encuentra el archivo de exámenes |
| Castilla-La Mancha | 0 | – | – | la web bloquea la descarga automática (403) |
| Extremadura | 0 | – | – | la web bloquea la descarga automática (403) |
| La Rioja | 0 | – | – | la web limita las peticiones (429) |
| Illes Balears | 0 | – | – | la web no responde a los servidores de GitHub |

Las cuatro últimas se pueden completar subiendo sus PDF a mano a `manual/` (ver más abajo).

## Cómo se construyen los datos (`pipeline/`)

Todo lo hace GitHub Actions, porque las webs de las universidades solo son accesibles desde allí. El workflow `.github/workflows/corpus.yml` tiene tres fases:

1. **Rastreo:** 17 tareas en paralelo, una por comunidad, de 45 minutos como máximo cada una. Cada tarea guarda lo conseguido aunque no termine, y un fallo en una comunidad no afecta a las demás.
2. **Análisis:** junta todas las comunidades y recalcula las predicciones y el contexto para los generadores.
3. **Exámenes:** genera los exámenes probables que falten. Cada uno se sube nada más generarse.

Se ejecuta al cambiar las fuentes, el código del rastreo o la carpeta `manual/`, el día 1 de cada mes y cada lunes de junio y julio (cuando se publican los exámenes nuevos). También se puede lanzar a mano desde **Actions → Corpus y predicciones PAU → Run workflow**.

| Paso | Script | Qué hace |
|---|---|---|
| 1 | `crawl.py` | Una comunidad por tarea (`--ccaa`, `--tiempo`). Parte de las páginas oficiales de `fuentes.json`, sigue sus enlaces y localiza los documentos de 2022-2026: PDF, ZIP (Andalucía publica uno por materia y año), enlaces de gestores documentales sin «.pdf» (UCM, Liferay) y Google Drive (UC3M). Los clasifica por materia, año, convocatoria y tipo (examen o criterios), los descarga, extrae el texto (pdftotext, y OCR con tesseract si es un escaneo) y escribe `data/corpus/<comunidad>.json` y `data/logs/<comunidad>.log`. También incorpora los PDF subidos a mano a `manual/<comunidad>/`. |
| 1b | `une.py` | Junta las comunidades en `data/corpus.json` y `data/cobertura.json`. |
| 2 | `analiza.py` | Etiqueta cada examen por temas (`temario.json`) y calcula la predicción con su comprobación → `data/predicciones.json`. Es determinista y no usa IA. Además prepara `data/contexto/<comunidad>__<materia>.json`: los dos exámenes reales más recientes (para el formato) y, para cada tema, cómo se ha preguntado en hasta tres exámenes anteriores. |
| 3 | `genera.py` | Exámenes probables con agentes de IA → `data/examenes/`. Necesita el secreto `OPENAI_API_KEY`. También se puede lanzar solo con el workflow `genera.yml`. |

- **Qué se guarda en el repositorio:** el texto de cada examen y el manifiesto con su URL oficial (`corpus/`, `data/`).
- **Los PDF originales** van a la Release `corpus` (un zip por comunidad y fecha), no al repositorio, para no pasar del límite de 1 GB de GitHub Pages.
- **Clasificación:** reconoce los nombres completos de las materias y las abreviaturas de cada comunidad (HFIL, MCS, quim…). Si el enlace no dice la materia o el año, los toma del título de la página o de la cabecera del propio examen. Descarta las pruebas que no son la PAU de bachillerato (mayores de 25 y 45 años, PAP de Cataluña) y los documentos de gestor que no parecen exámenes (listados, ayudas, presupuestos…).
- **Opciones por comunidad en `fuentes.json`:** `pausa`, `timeout`, `max_paginas`, `profundidad`, `dominios_extra` (otros dominios de la misma institución, como `uib.cat` y `uib.es`) y `plantillas` (URL con `{anio}` y rangos, por ejemplo la de Galicia: `/PDF/{anio}/PAU/{conv}/exames/{cod}.pdf`).
- **Si una comunidad sale con poca cobertura:** revisa `data/logs/<comunidad>.log` y añade en `fuentes.json` la página exacta de su archivo de exámenes. El workflow **Diagnóstico de fuentes** (`diagnostico.yml`) guarda en `diag/` cómo responde cada URL de `pipeline/diagnostico.txt` (estado, cabeceras, HTML y enlaces), para ver cómo está hecha una web antes de ajustarla.

### Exámenes subidos a mano (`manual/`)

Para las webs que bloquean la descarga automática:

1. Descarga los PDF o ZIP desde la web oficial.
2. Súbelos a `manual/<comunidad>/` desde GitHub (**Add file → Upload files**), por ejemplo `manual/rioja/2025/Matemáticas II junio.pdf`.

Conviene que el nombre o la carpeta digan año, materia y convocatoria; si no, se intenta leer de la cabecera del examen. Al subirlos se relanza solo el workflow. Instrucciones completas en [`manual/README.md`](manual/README.md).

### Agentes que se vigilan entre sí

- **Ponente:** redacta un examen original con el formato y la puntuación de los dos últimos exámenes reales, repartiendo las preguntas según la probabilidad de cada tema. Recibe también, tema a tema, las preguntas reales de años anteriores de esa comunidad, con la orden de imitar su estilo, dificultad y forma de puntuar sin copiarlas y sin repetir el planteamiento del último año.
- **Resolutor A y Resolutor B:** resuelven cada pregunta por separado, sin ver la otra solución.
- **Código:** en las preguntas de cálculo, cada resolutor entrega además un programa con sympy. Se ejecuta y tiene que reproducir el resultado que el resolutor afirma.
- **Desempate y tribunal:** si A y B no coinciden, un tercer resolutor decide por mayoría de 2 de 3. En las preguntas abiertas, un tribunal comprueba que las dos resoluciones coinciden y que ninguna tiene errores de contenido.
- **Sin acuerdo, fuera:** la pregunta se descarta y el ponente redacta otra (hasta 3 rondas). Cada pregunta publicada lleva su nivel: «comprobada por código» o «doble resolución».

Esto reduce mucho los errores, pero no los elimina: la app lo dice y pide avisar de cualquier error en las [*issues*](https://github.com/fborrasumh/pausible/issues).

**Activar la generación:** en **Settings → Secrets and variables → Actions**, crea el secreto `OPENAI_API_KEY`. Variables opcionales:
- `PAUSIBLE_MODELO`: por defecto `gpt-6-luna`, el más económico de OpenAI.
- `PAUSIBLE_ESFUERZO`: nivel de razonamiento, por defecto `high`. Con `medium` es más rápido y barato, pero se descartan más preguntas.

Cada ejecución genera como máximo 20 exámenes nuevos; el número se puede cambiar al lanzarla a mano.

## La IA en la app

Sin clave, la app funciona entera con los datos ya generados. Con su propia clave, el estudiante puede generar exámenes nuevos con el mismo esquema (ponente con el contexto de años anteriores, dos resolutores y desempate o tribunal), aunque sin ejecutar código.

Proveedores admitidos:
- **OpenAI:** desde los 13 años; los menores de 18 necesitan permiso de su madre, padre o tutor.
- **Anthropic Claude:** a partir de 18 años.
- **Google Gemini no está disponible:** sus condiciones prohíben usar su API en aplicaciones a las que probablemente accedan menores de 18 años. La app la bloquea del todo, incluida la conexión, y si alguien la tenía elegida vuelve a OpenAI y se borra su clave.

La guía **«Tu clave de IA»** de la app explica cómo crear la clave con límite de gasto y por qué una suscripción mensual al chatbot no sirve para esto.

## Fórmulas

Las fórmulas se pintan con [KaTeX](https://katex.org) y su extensión de química mhchem (licencia MIT), incluidos dentro del propio `index.html` con sus fuentes, así que se ven bien sin conexión. Admite LaTeX entre `$…$`, `$$…$$`, `\(…\)` y `\[…\]`, química con `\ce{…}` y fórmulas sueltas como `\frac{…}{…}`.

Para actualizar KaTeX: `npm i katex@0.16 && python3 tools/vendor_katex.py node_modules/katex`.

## Privacidad

- **Sin registro ni servidor propio.** La comunidad, la materia, las notas, los exámenes propios y la clave se guardan solo en el navegador.
- **La tarjeta para compartir** se dibuja en el propio dispositivo.
- **Retos:** un examen compartido viaja dentro del enlace, en la parte que no llega a ningún servidor.
- **Generar con clave propia:** al proveedor de IA salen la materia, la comunidad, la lista de temas y fragmentos de exámenes oficiales de años anteriores, que son públicos. No sale nada personal.

## Límites

- **Cobertura incompleta:** Andalucía, Galicia, Castilla y León y Asturias tienen huecos, y cuatro comunidades no tienen datos (ver la tabla).
- **Cambio de modelo en 2025:** con la LOMLOE el examen pasó a modelo único con parte competencial. Los exámenes de 2022-2024 pesan menos, pero siguen contando.
- **Etiquetado por palabras clave:** puede fallar con exámenes en catalán, gallego o euskera, o con enunciados muy breves. Las materias sin temas en `temario.json` solo muestran los exámenes oficiales enlazados.
- **Exámenes probables:** son originales, no anticipan el examen real y pueden contener errores pese a la doble resolución.
- **Derechos:** los exámenes oficiales pertenecen a las administraciones que los publican, y siempre se enlazan a su fuente.

## Estructura del repositorio

```
index.html            la app (se monta con build.py; es lo que publica GitHub Pages)
src/                  código de la app: datos.js, nucleo.js, app.js, body.html, app.css, i18n.js, katex.*
forja/                módulos comunes de las apps Forja (IA, idiomas, navegación, verificación)
pipeline/             crawl.py, une.py, analiza.py, genera.py, fuentes.json, temario.json, diagnostico.*
data/                 corpus/, logs/, contexto/, examenes/ (+ archivo/), corpus.json, cobertura.json, predicciones.json
corpus/               texto extraído de cada examen oficial
manual/               PDF subidos a mano para las comunidades que bloquean la descarga
diag/                 resultado del diagnóstico de fuentes
tests/                test_pipeline.py (sin red) y e2e_test.py (navegador)
tools/vendor_katex.py actualiza KaTeX dentro de la app
```

## Desarrollo

```bash
python3 build.py                       # monta index.html desde src/ y forja/
python3 tests/test_pipeline.py         # clasificación, ZIP, contexto, predicción y filtro multiagente (sin red)
python3 tests/e2e_test.py <sitio>      # navegador: ejemplo, datos, fórmulas, generación simulada, retos,
                                       # historial, fichero, idiomas, ranking, móvil y sin conexión
```

## Autoría

Fernando Borrás Rocher (Universidad Miguel Hernández de Elche). ORCID [0000-0002-5519-4573](https://orcid.org/0000-0002-5519-4573).

Para citar la app, usa [`CITATION.cff`](CITATION.cff).

## Licencia

Código: MIT. KaTeX y mhchem: MIT. Los exámenes oficiales pertenecen a sus administraciones.
