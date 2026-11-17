# Incorporación manual de PAU 2022–2026: Castilla-La Mancha, Extremadura y La Rioja

## Estado

La rama `feature/pau-nuevas-comunidades-2022-2026` adapta el cuaderno existente
`notebooks/descarga_manual.ipynb` para trabajar exclusivamente con:

- `castillalamancha`
- `extremadura`
- `rioja`

El cuaderno clona esta rama y, si se configura un token, publica los ficheros en
esta misma rama. **No hace push a `main`.**

## Ejecución

1. Abrir [el cuaderno de descarga manual](../notebooks/descarga_manual.ipynb) desde la rama de trabajo
   (en GitHub: seleccionar la rama y abrir el notebook).
2. Ejecutar todas las celdas en Colab. Revisar primero el resultado de acceso y el respeto a
   `robots.txt`; el cuaderno aplica una pausa entre peticiones y espera ante respuestas 429.
3. Si el origen bloquea Colab, ejecutar el mismo cuaderno en un Jupyter local conectado a la red
   desde la que se pueda acceder legítimamente a los portales.
4. Para publicar directamente, crear un fine-grained personal access token limitado a este
   repositorio y con permiso **Contents: Read and write**. Guardarlo como secreto de Colab
   `GITHUB_TOKEN`; no pegarlo en celdas ni en el repositorio. Revocarlo al terminar.
5. Si no se usa token, descargar el ZIP generado y subir sus carpetas a
   `manual/<comunidad>/<año>/` en esta rama.
6. En GitHub, abrir **Actions → Corpus y predicciones PAU → Run workflow** y seleccionar
   explícitamente la rama `feature/pau-nuevas-comunidades-2022-2026`. El evento `push` del
   workflow está limitado a `main`, por lo que los cambios en esta rama no lo lanzan solos.
7. Revisar el resultado del rastreo y la clasificación en `data/logs/<comunidad>.log`.

## Verificación de cobertura

La descarga no equivale a cobertura completa. Comprobar en `data/cobertura.json` y
`data/corpus/<comunidad>.json` que cada documento tiene materia, año, convocatoria,
tipo y URL de origen. Revisar especialmente:

- convocatorias ordinaria y extraordinaria (o la denominación oficial equivalente);
- documentos de examen frente a criterios/orientaciones;
- materias nuevas o con denominación distinta;
- años 2022–2024 (EBAU/EvAU) y 2025–2026 (PAU), manteniendo la denominación histórica;
- ficheros sin clasificar, duplicados y documentos escaneados que necesiten OCR.

No declarar una comunidad completa mientras queden años/materias/convocatorias sin revisar.
Los bloqueos 403/429 no deben eludirse: usar descarga manual autorizada o solicitar el
documento por un canal oficial.

## Integración

Cuando las tres comunidades estén auditadas y las pruebas del pipeline pasen, abrir/revisar
un Pull Request hacia `main`. No integrar una cobertura parcial como si fuera completa.
