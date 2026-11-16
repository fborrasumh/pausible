# PAUsible

El examen más PAUsible de la PAU 2027 (selectividad), por comunidad autónoma y materia. Aplicación web de un solo fichero, sin registro.

**Usar la app:** https://fborrasumh.github.io/pausible/

**Idiomas:** español (por defecto), inglés y portugués; selector en la barra superior (o `?lang=en` / `?lang=pt`).

## Qué hace

1. **Predicción por comunidad y materia.** Para cada una de las 17 comunidades y cada materia de la PAU, calcula la probabilidad de que cada tema aparezca en el examen de 2027 a partir de los exámenes oficiales de 2022 a 2026. Enseña cuántas veces salió cada tema, cuándo fue la última, su tendencia, un fragmento del enunciado real con enlace al PDF oficial y la probabilidad media en toda España.
2. **Validación ciega visible.** Cada predicción se pone a prueba ocultando el último examen ordinario y prediciéndolo con los anteriores; el estudiante ve cuántos temas habría acertado el método y cuántos acertaría el azar. De ahí sale la confianza (alta, media o baja).
3. **Examen probable con solución verificada.** Exámenes originales con el formato de la comunidad, centrados en los temas más probables, resueltos por varios agentes de IA que se vigilan entre sí (ver abajo). Cronómetro de 90 minutos opcional, solución y criterios por pregunta, y autocorrección que calcula la nota del simulacro.
4. **Compartir y retar.** Tarjeta en formato historia (1080×1920) dibujada en el propio dispositivo, botón de compartir nativo, WhatsApp y un enlace de reto (`?c=madrid&m=matematicas2&n=7.5`) que abre a tu amigo el mismo examen con tu nota.
5. **Ranking de España.** Qué comunidad tiene la PAU más previsible y qué temas caen en casi toda España en cada materia.
6. **Ejemplo sin clave ni datos** (Matemáticas II), con predicción ficticia marcada como tal y soluciones comprobadas con sympy.

## Cómo se construyen los datos (`pipeline/`)

Todo lo hace un GitHub Action (`.github/workflows/corpus.yml`), porque las webs de las universidades solo son accesibles desde allí. Va en tres fases: **17 tareas en paralelo**, una por comunidad (máximo 45 min cada una; cada una guarda lo conseguido aunque no termine, y un fallo en una no afecta a las demás); después se junta todo y se recalculan las predicciones; al final se generan los exámenes probables que falten (cada uno se sube nada más generarse). Se ejecuta al cambiar las fuentes, el día 1 de cada mes y cada lunes de junio y julio (cuando se publican los exámenes nuevos), o a mano desde la pestaña **Actions → Corpus y predicciones PAU → Run workflow**.

| Paso | Script | Qué hace |
|---|---|---|
| 1 | `crawl.py` | Una comunidad por tarea (`--ccaa`, `--tiempo`). Parte de las páginas oficiales de cada comunidad (`fuentes.json`), sigue los enlaces del mismo dominio, localiza los PDF 2022-2026, los clasifica por materia, año, convocatoria y tipo (examen / criterios), los descarga, extrae el texto (pdftotext; OCR con tesseract si es un escaneo) y escribe `data/corpus/<comunidad>.json`. `une.py` los junta en `data/corpus.json` y `data/cobertura.json`. |
| 2 | `analiza.py` | Etiqueta cada examen por temas (`temario.json`) y calcula la predicción con validación ciega → `data/predicciones.json`. Determinista, sin IA. |
| 3 | `genera.py` | Exámenes probables con agentes (solo si existe el secreto `OPENAI_API_KEY`) → `data/examenes/`. |

- El **texto** de cada examen y el manifiesto con la **URL oficial** se guardan en el repositorio (`corpus/`, `data/`).
- Los **PDF originales** se suben a la Release `corpus` (un zip por comunidad y fecha), no al repositorio, para no pasar del límite de 1 GB de GitHub Pages.
- Si una comunidad sale con poca cobertura en `data/cobertura.json` o en `data/logs/<comunidad>.log`, añade en `fuentes.json` la URL exacta de su archivo de exámenes.

### Agentes que se vigilan entre sí

- **Ponente**: redacta un examen original con el formato y la puntuación de los dos últimos exámenes reales, repartiendo las preguntas según la probabilidad de cada tema.
- **Resolutor A y Resolutor B**: resuelven cada pregunta por separado, sin ver la otra solución.
- **Código**: en las preguntas de cálculo, cada resolutor entrega además un programa con sympy; se ejecuta y tiene que reproducir el resultado que el resolutor afirma.
- **Desempate / tribunal**: si A y B no coinciden, un tercer resolutor decide por mayoría 2 de 3; en preguntas abiertas, un tribunal comprueba que coinciden y que ninguna tiene errores de contenido.
- Si no hay acuerdo, la pregunta **se descarta** y el ponente redacta otra (hasta 3 rondas). Cada pregunta publicada lleva su nivel: «comprobada por código» o «doble resolución».

Esto reduce mucho los errores, pero no los elimina: la app lo dice y pide avisar de cualquier error en las *issues* de GitHub.

Para activar la generación: **Settings → Secrets and variables → Actions → New repository secret** con nombre `OPENAI_API_KEY`. Opcional: variable `PAUSIBLE_MODELO` (por defecto `gpt-6-luna`, el más económico de OpenAI, con razonamiento `high`; se puede cambiar con la variable `PAUSIBLE_ESFUERZO`). Cada ejecución genera como máximo 20 exámenes nuevos (configurable al lanzar el Action a mano).

## Cómo se usa la IA en la app

Sin clave, la app funciona entera con los datos ya generados. Con la propia clave de OpenAI, Google Gemini o Anthropic Claude, el estudiante puede generar un examen probable para una combinación que aún no lo tenga; el navegador aplica el mismo esquema ponente + dos resolutores + desempate/tribunal (sin ejecutar código). La clave se guarda solo en el navegador.

## Fórmulas

Las fórmulas (LaTeX entre `$…$`, `$$…$$`, `\(…\)`, `\[…\]`, y química con `\ce{…}`) se pintan con [KaTeX](https://katex.org) y su extensión mhchem (licencia MIT), incluidos dentro del propio `index.html` con sus fuentes, así que se ven bien sin conexión. Para actualizarlos: `npm i katex@0.16 && python3 tools/vendor_katex.py node_modules/katex`.

## Privacidad

No hay registro ni servidor propio. La comunidad, la materia, las notas del simulacro y la clave se guardan solo en el navegador. La tarjeta se dibuja en el dispositivo. Si se genera un examen con clave propia, al proveedor de IA solo salen la materia, la comunidad y la lista de temas.

## Límites

- PAUsible **no es oficial** ni tiene relación con las universidades o las comisiones de la PAU. Las predicciones son probabilidades calculadas con exámenes anteriores; no anticipan el examen real. Ningún tema baja del 5 %: hay que estudiar todo el temario.
- El modelo de examen cambió en 2025 (LOMLOE: modelo único y parte competencial). Los exámenes de 2022-2024 pesan menos, pero siguen contando.
- El etiquetado por temas usa palabras clave; en exámenes en catalán, gallego o euskera, o con enunciados muy breves, puede fallar. Las materias sin temario por temas en `temario.json` solo muestran los exámenes oficiales enlazados.
- El rastreador no se ha podido probar contra las webs reales desde el entorno de desarrollo; su primera ejecución en Actions dirá qué comunidades necesitan ajustar `fuentes.json`.
- Los exámenes oficiales pertenecen a las administraciones que los publican; se enlazan siempre a su fuente.

## Desarrollo

```bash
python3 build.py                       # monta index.html desde src/ y forja/
python3 tests/test_pipeline.py         # clasificación de enlaces, predicción y filtro multiagente (sin red)
python3 tests/e2e_test.py <sitio>      # navegador: ejemplo, datos, generación simulada, reto, idiomas, móvil
```

## Autoría

Fernando Borrás Rocher (Universidad Miguel Hernández de Elche). ORCID [0000-0002-5519-4573](https://orcid.org/0000-0002-5519-4573).

## Licencia

Código: MIT.
