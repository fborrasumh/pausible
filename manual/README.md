# Exámenes subidos a mano

Algunas webs oficiales bloquean la descarga automática desde GitHub (Castilla-La Mancha, Extremadura, La Rioja e Illes Balears).

## Con el cuaderno de Colab (lo más rápido)

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fborrasumh/pausible/blob/main/notebooks/descarga_manual.ipynb)

Recorre las páginas oficiales de esas cuatro comunidades despacio (4 s entre peticiones, respetando `robots.txt`), guarda los PDF en `manual/<comunidad>/<año>/` con su materia y convocatoria en el nombre y los sube al repositorio con tu token (o te da un ZIP). Si desde Colab también hay bloqueo, el cuaderno explica cómo ejecutarlo en tu ordenador.

## La Rioja: exámenes escaneados (OCR)

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fborrasumh/pausible/blob/main/notebooks/ocr_rioja.ipynb)

La Universidad de La Rioja publica muchos exámenes como imágenes escaneadas. `manual/rioja/escaneados.json` tiene sus enlaces públicos de SharePoint; el cuaderno los descarga, los lee con Tesseract y deja el texto en `manual/rioja/<año>/`.

## A mano

1. Descarga los PDF (o los ZIP) de la web oficial de la comunidad.
2. Súbelos aquí, en la carpeta de su comunidad: `manual/castillalamancha/`, `manual/extremadura/`, `manual/rioja/`, `manual/baleares/` (vale cualquier comunidad: `manual/<id>/`, con el id de `pipeline/fuentes.json`).
3. Ayuda a clasificarlos con el nombre o la carpeta: año, materia y convocatoria. Por ejemplo `manual/rioja/2025/Matemáticas II junio.pdf` o `manual/extremadura/2024/Historia de España julio criterios.pdf`.
   Si el nombre no lo dice, se intenta leer de la cabecera del propio examen.

Al subir algo a `manual/` se relanza solo el workflow «Corpus y predicciones PAU». Lo que no se pueda clasificar aparece en `data/logs/<id>.log`.

Desde GitHub: entra en la carpeta, **Add file → Upload files**, arrastra los PDF y pulsa **Commit changes**.
