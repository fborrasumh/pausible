# Exámenes subidos a mano

Algunas webs oficiales bloquean la descarga automática desde GitHub (Castilla-La Mancha, Extremadura y La Rioja). Para incluirlas:

1. Descarga los PDF (o los ZIP) de la web oficial de la comunidad.
2. Súbelos aquí, en la carpeta de su comunidad: `manual/castillalamancha/`, `manual/extremadura/`, `manual/rioja/` (vale cualquier comunidad: `manual/<id>/`, con el id de `pipeline/fuentes.json`).
3. Ayuda a clasificarlos con el nombre o la carpeta: año, materia y convocatoria. Por ejemplo `manual/rioja/2025/Matemáticas II junio.pdf` o `manual/extremadura/2024/Historia de España julio criterios.pdf`.
   Si el nombre no lo dice, se intenta leer de la cabecera del propio examen.

Al subir algo a `manual/` se relanza solo el workflow «Corpus y predicciones PAU». Lo que no se pueda clasificar aparece en `data/logs/<id>.log`.

Desde GitHub: entra en la carpeta, **Add file → Upload files**, arrastra los PDF y pulsa **Commit changes**.
