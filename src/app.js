/* ══ PAUsible · interfaz ══ */
const STEPS = ['Inicio', 'Tu PAU', 'Predicción', 'Examen', 'Comparte'];
const HUBS = ['Ranking de España', 'Tu clave de IA', 'Mis exámenes'];
const NAV = [['Elegir mi comunidad', 'Prueba el ejemplo: no necesita clave ni datos.'], ['Ver la predicción', 'Elige comunidad y materia.'], ['Hacer el examen probable', 'Estudia primero lo de arriba.'], ['Compartir mi resultado', 'Abre cada solución y ponte nota.'], ['Volver al inicio', 'Comparte la tarjeta o reta a un amigo.']];
const RENDER = {0: pintaInicio, 1: pintaTuPau, 2: pintaPred, 3: pintaExamen, 4: pintaComparte, 5: pintaRanking, 6: pintaClave, 7: pintaBiblioteca};
const CAN_NEXT = i => i === 1 && !(S.c && S.m) ? t('Elige comunidad y materia') : true;
const GLOS = [
  ['¿Qué hace PAUsible?', 'Lee los exámenes oficiales de la PAU publicados por cada comunidad entre 2022 y 2026, calcula qué temas tienen más probabilidad de caer en 2027 y te ofrece un examen probable resuelto.'],
  ['¿Cómo se calcula la probabilidad?', 'Por código, sin IA: se cuenta en qué exámenes aparece cada tema, pesando más 2025 y 2026 (el modelo de examen cambió en 2025). Un tema frecuente que no salió el último año sube un poco. Ningún tema baja del 5 %.'],
  ['¿Acierta?', 'Cada predicción se pone a prueba ocultando el último examen y prediciéndolo con los anteriores. Ves cuántos temas habría acertado y cuántos acertaría el azar. Si la confianza es baja, se dice.'],
  ['¿Las soluciones están bien?', 'Cada pregunta la resuelven dos IA por separado. Solo se publica si coinciden; en cálculo, además, un programa comprueba el resultado. Es mucho más fiable que una sola IA, pero no es infalible: si ves un error, avísanos en GitHub.'],
  ['¿Es oficial?', 'No. PAUsible no tiene relación con las universidades ni con las comisiones de la PAU. Los exámenes reales enlazados son los oficiales; los exámenes probables son originales y no anticipan el examen real.'],
  ['Generar con tu clave', 'Si tu combinación aún no tiene examen probable, puedes generarlo con tu clave de OpenAI o de Claude. El ponente ve cómo se han preguntado esos temas en tu comunidad en años anteriores. Salen la comunidad, la materia, la lista de temas y fragmentos de exámenes oficiales; nada personal.'],
  ['Privacidad', 'No hay registro. Tu comunidad, materia y notas se guardan solo en este navegador. La tarjeta para compartir se dibuja en tu dispositivo.']
];
/* Gemini fuera: sus condiciones de uso prohíben la API en apps a las que probablemente accedan menores de 18 años.
   Si alguien lo tenía elegido, vuelve a OpenAI y se borra su clave de Gemini de este navegador. */
delete PROV.gemini;
try { if (localStorage.getItem(APP + '_prov') === 'gemini') localStorage.removeItem(APP + '_prov'); localStorage.removeItem(APP + '_key_gemini'); } catch {}
let S = {c: '', m: '', auto: {}, ejemplo: false, crono: null, fuente: {}, intento: null};
const MEM = {examenes: {}, version: {}, bib: [], bibId: {}};
const clave = () => `${S.c}__${S.m}`;
let LINK = '';           // enlace de reto ya calculado (comprimir es asíncrono)
const ejemploOn = () => S.ejemplo;
const predActual = () => ejemploOn() ? EJ_PRED : prediccionDe(S.c, S.m);
/* De dónde sale el examen de esta comunidad y materia: el oficial de PAUsible o uno de «Mis exámenes» (tuyo o de un reto) */
async function recargaBib() { try { MEM.bib = await bibTodos(); } catch { MEM.bib = []; } MEM.bibId = Object.fromEntries(MEM.bib.map(r => [r.id, r])); }
const bibDe = (c, m) => MEM.bib.filter(r => r.c === c && r.m === m);
function fuenteActual() {
  const k = clave(), f = S.fuente[k];
  if (f === 'oficial' && MEM.examenes[k]) return f;
  if (f && f.startsWith('bib:')) { const r = MEM.bibId[f.slice(4)]; if (r && r.c === S.c && r.m === S.m) return f; }
  if (MEM.examenes[k]) return 'oficial';
  const r = bibDe(S.c, S.m)[0]; return r ? 'bib:' + r.id : 'oficial';
}
const recActual = () => { const f = ejemploOn() ? '' : fuenteActual(); return f.startsWith('bib:') ? MEM.bibId[f.slice(4)] : null; };
function examenActual() {
  if (ejemploOn()) return EJ_EXAMEN[LANG] || EJ_EXAMEN.es;
  const r = recActual(); return r ? r.ex : MEM.examenes[clave()] || null;
}
async function alBib(c, m, ex, origen, extra) {
  const r = bibNuevo(c, m, ex, origen, extra); await bibGuarda(r); await recargaBib(); pidePersistencia();
  if (MEM.bib.length > BIB_AVISO) toast(t('Tienes {0} exámenes guardados: exporta una copia y borra los que ya no uses.', MEM.bib.length), 8000);
  return r;
}
const cc = () => CCAA.find(c => c.id === S.c);
const fmtP = p => Math.round(p * 100) + ' %';
const fmtN = n => (+n).toLocaleString(locale(), {minimumFractionDigits: 1, maximumFractionDigits: 2});
const RETO = leeReto(location.search, location.hash);
const TEND = {sube: '↑', baja: '↓', estable: '→'};

/* ── 0 · inicio ── */
function pintaInicio() {
  const b = $('retoBanner');
  if (RETO) {
    b.hidden = false;
    b.innerHTML = `<b>${esc(RETO.n != null ? t('Te han retado: {0} en el examen PAUsible de {1}.', fmtN(RETO.n), nombreMat(RETO.m)) : t('Te han retado con el examen PAUsible de {0}.', nombreMat(RETO.m)))}</b><p class="sub" style="margin:4px 0 10px">${esc(nombreCCAA(RETO.c))} · ${esc(t('¿Lo superas?'))}</p><button class="btn btn-primary" id="btnReto" type="button">${esc(t('Aceptar el reto'))}</button>`;
  } else b.hidden = true;
  $('estadoDatos').textContent = !DATOS.cargado ? t('Cargando datos…') : hayDatos()
    ? t('Corpus: {0} combinaciones comunidad × materia con exámenes oficiales · actualizado el {1}.', nf(Object.values(DATOS.pred.ccaa).reduce((s, c) => s + Object.keys(c.materias).length, 0)), DATOS.pred.generado)
    : t('Todavía no se ha descargado el corpus de exámenes oficiales: de momento puedes ver el ejemplo.');
  $('btnBib').hidden = !MEM.bib.length; $('btnBibN').textContent = MEM.bib.length;
  $('inicioProj').innerHTML = S.c && S.m && !S.ejemplo ? `${esc(t('Tu última consulta:'))} <b>${esc(nombreMat(S.m))} · ${esc(nombreCCAA(S.c))}</b> <button class="btn btn-ghost btn-sm" id="btnCont" type="button">${esc(t('Seguir'))}</button>` : '';
}
$('btnStart').onclick = () => { S.ejemplo = false; guarda(); go(1); };
$('btnEjemplo').onclick = () => { S.ejemplo = true; S.auto = {}; S.intento = null; guarda(); go(2); toast(t('Ejemplo con datos ficticios: no es una predicción real')); };
$('btnRanking').onclick = () => go(5);
document.addEventListener('click', e => {
  if (e.target.id === 'btnCont') go(2);
  if (e.target.id === 'btnReto') aceptaReto();
});

async function aceptaReto() {
  S.c = RETO.c; S.m = RETO.m; S.ejemplo = false; S.auto = {}; S.intento = null; const k = clave();
  if (RETO.x) {
    const ex = await descomprimeExamen(RETO.x);
    if (ex) { const r = await alBib(S.c, S.m, ex, 'reto', {reto_nota: RETO.n}); S.fuente[k] = 'bib:' + r.id; } else toast(t('El examen del enlace está dañado o incompleto: se abre el examen oficial.'), 7000);
  } else { S.fuente[k] = 'oficial'; if (RETO.v) { MEM.version[k] = RETO.v; delete MEM.examenes[k]; } }
  await guardaYa(); history.replaceState(null, '', location.pathname); go(3);
}
/* Examen recibido como fichero (cuando el enlace era demasiado largo para el sitio donde se compartió) */
$('fichReto').onchange = async e => {
  const f = e.target.files[0]; e.target.value = ''; if (!f) return;
  try {
    const j = JSON.parse(await f.text());
    if (!j || !CCAA.some(x => x.id === j.c) || !MATERIAS[j.m] || !j.x) throw 0;
    const ex = await descomprimeExamen(j.x); if (!ex) throw 0;
    S.c = j.c; S.m = j.m; S.ejemplo = false; S.auto = {}; S.intento = null; const r = await alBib(j.c, j.m, ex, 'reto', {reto_nota: j.n ?? null}); S.fuente[clave()] = 'bib:' + r.id;
    await guardaYa(); go(3);
    if (j.n != null) toast(t('Te han retado: {0} en el examen PAUsible de {1}.', fmtN(j.n), nombreMat(j.m)), 7000);
  } catch { toast(t('Ese fichero no es un examen de PAUsible.'), 6000); }
};

/* ── 1 · tu PAU ── */
function pintaTuPau() {
  $('ccaaGrid').innerHTML = CCAA.map(c => {
    const n = materiasDe(c.id).length;
    return `<button type="button" role="radio" aria-checked="${S.c === c.id}" data-c="${c.id}">${esc(c.nombre)}<small>${hayDatos() ? esc(t('{0} materias', n)) : ''}</small></button>`;
  }).join('');
  $$('#ccaaGrid button').forEach(b => b.onclick = () => { S.c = b.dataset.c; S.ejemplo = false; if (hayDatos() && !materiasDe(S.c).includes(S.m)) S.m = ''; S.auto = {}; S.intento = null; guarda(); pintaTuPau(); });
  const mats = S.c && hayDatos() ? materiasDe(S.c) : Object.keys(MATERIAS);
  $('selMat').innerHTML = `<option value="">${esc(t('Elige materia…'))}</option>` + mats.map(m => `<option value="${m}">${esc(nombreMat(m))}</option>`).join('');
  $('selMat').value = S.m; $('selMat').disabled = !S.c;
  const reg = prediccionDe(S.c, S.m);
  $('matInfo').textContent = !S.c ? t('Primero elige tu comunidad.') : !hayDatos() ? t('Aún no hay corpus descargado: las predicciones aparecerán cuando se cargue.')
    : reg ? t('{0} exámenes oficiales analizados ({1}).', reg.n_examenes, reg.anios.join(', ')) : '';
  const c = cc();
  $('cuenta').innerHTML = c ? `${esc(t('Faltan {0} días', diasHasta(c.fecha)))}<small>${esc(c.oficial ? t('PAU 2027 en {0}: fecha oficial publicada.', c.nombre) : t('Fecha estimada: {0} aún no ha publicado el calendario de 2027.', c.nombre))}</small>` : '';
}
$('selMat').onchange = () => { S.m = $('selMat').value; S.auto = {}; S.intento = null; guarda(); pintaTuPau(); };

/* ── 2 · predicción ── */
function pintaPred() {
  const reg = predActual();
  $('predTit').textContent = ejemploOn() ? t('Ejemplo · {0}', t('Matemáticas II')) : `${nombreMat(S.m)} · ${nombreCCAA(S.c)}`;
  const aviso = $('predAviso');
  if (!reg) {
    aviso.innerHTML = `<p style="margin:0">${esc(!S.c || !S.m ? t('Elige comunidad y materia.') : t('Aún no hay exámenes oficiales de esta materia en el corpus de esta comunidad.'))}</p>`;
    ['predTemas', 'predValid', 'predFuentes'].forEach(id => { $(id).innerHTML = ''; $(id).hidden = true; }); return;
  }
  ['predTemas', 'predValid', 'predFuentes'].forEach(id => $(id).hidden = false);
  const CONF = {alta: ['ok', t('Confianza alta')], media: ['aviso', t('Confianza media')], baja: ['error', t('Confianza baja')], sin_temario: ['', t('Sin temario por temas')]};
  const [cls, lbl] = CONF[reg.confianza] || CONF.baja;
  aviso.innerHTML = `${reg.ficticio ? `<p class="fa-chip aviso" style="margin:0 0 8px">${esc(t('Datos ficticios de demostración'))}</p>` : ''}<span class="fa-chip ${cls}">${esc(lbl)}</span> <span class="sub">${esc(t('{0} exámenes oficiales · {1}', reg.n_examenes, (reg.anios || []).join(', ')))}</span>`
    + (reg.confianza === 'baja' ? `<p class="help">${esc(t('Pocos exámenes o un patrón débil: úsalo para ordenar el estudio, no para descartar temas.'))}</p>` : '');
  if (!reg.temas || !reg.temas.length) { $('predTemas').innerHTML = `<p>${esc(t('Esta materia todavía no tiene temario por temas en PAUsible: puedes consultar los exámenes oficiales enlazados abajo.'))}</p>`; }
  else $('predTemas').innerHTML = `<h3>${esc(t('Temas por probabilidad'))}</h3>` + reg.temas.map(tm => `<div class="pa-tema"><b>${esc(tm.nombre)}</b><span class="pa-p">${fmtP(tm.p)}</span>
    <div class="pa-bar" role="img" aria-label="${fmtP(tm.p)}"><span style="width:${Math.round(tm.p * 100)}%"></span></div>
    <span class="pa-meta">${esc(t('Salió en {0} de {1} exámenes', tm.veces, tm.de))}${tm.ultimo ? ' · ' + esc(t('último: {0}', tm.ultimo)) : ''} · ${esc(t('tendencia'))} ${TEND[tm.tendencia] || '→'}${nacionalDe(tm.id)}</span>
    ${tm.muestra ? `<div class="pa-muestra">${esc(t('Así salió:'))} «${esc(tm.muestra)}» ${tm.muestra_url ? `<a href="${esc(tm.muestra_url)}" target="_blank" rel="noopener">${esc(t('PDF oficial'))}</a>` : ''}</div>` : ''}</div>`).join('');
  const v = reg.validacion;
  $('predValid').innerHTML = `<h3>${esc(t('¿Habría acertado PAUsible?'))}</h3>` + (v
    ? `<p>${esc(t('Ocultamos el examen de {0} y lo predijimos con los anteriores: de los {1} temas que cayeron, {2} estaban en nuestro top {1}. Al azar se acertarían {3} %.', v.anio, v.k, v.aciertos, Math.round(v.azar * 100)))}</p>`
    : `<p>${esc(t('Aún no hay suficientes exámenes para comprobar el método en esta combinación.'))}</p>`);
  $('predFuentes').innerHTML = reg.examenes && reg.examenes.length ? `<h3>${esc(t('Exámenes oficiales analizados'))}</h3><ul>${reg.examenes.map(e => `<li><a href="${esc(e.url)}" target="_blank" rel="noopener">${e.anio} · ${esc(t(e.conv === 'ord' ? 'ordinaria' : e.conv === 'ext' ? 'extraordinaria' : 'modelo'))}</a></li>`).join('')}</ul>` : `<p class="help">${esc(t('En el ejemplo no hay enlaces: con datos reales verás aquí cada PDF oficial.'))}</p>`;
}
function nacionalDe(tid) {
  const n = hayDatos() && !ejemploOn() && DATOS.pred.nacional && (DATOS.pred.nacional[S.m] || []).find(x => x.id === tid);
  return n ? ' · ' + esc(t('en España: {0}', fmtP(n.p))) : '';
}

/* ── 3 · examen probable ── */
async function pintaExamen() {
  const k = clave();
  if (!ejemploOn() && S.c && S.m && !MEM.examenes[k] && tieneExamen(S.c, S.m)) {
    $('exCab').innerHTML = `<span class="spin"></span> ${esc(t('Cargando…'))}`;
    const ex = await cargaExamen(S.c, S.m, MEM.version[k] || ''); if (ex) MEM.examenes[k] = ex;
  }
  const ex = examenActual();
  if (!ex) {
    const reg = prediccionDe(S.c, S.m);
    $('exCab').innerHTML = `<h3>${esc(t('Todavía no hay examen probable para esta combinación'))}</h3><p>${esc(t('Puedes generarlo ahora con tu clave de IA: un ponente lo redacta con los temas más probables y dos resolutores lo resuelven por separado; solo se queda lo que coincide.'))}</p>`
      + (reg && reg.n_examenes ? `${!(reg.temas || []).length ? `<p class="fa-chip aviso" style="margin:0 0 8px">${esc(t('Sin predicción de temas'))}</p><p class="help">${esc(t('Esta materia aún no tiene temario por temas en PAUsible: el examen imitará el formato de los exámenes reales de tu comunidad y repartirá las preguntas por el currículo oficial, sin priorizar temas.'))}</p>` : ''}<div class="actions"><button class="btn btn-primary" id="btnGenera" type="button">${ico('sparkles')}<span>${esc(t('Generar con mi clave'))}</span></button></div><p class="help" id="genEstado"></p><p class="help"><a href="#" id="lnkClave">${esc(t('¿No tienes clave? Así se consigue (y lo que cuesta)'))}</a></p>` : `<p class="help">${esc(t('Todavía no hay exámenes reales de esta materia en tu comunidad para tomar como modelo.'))}</p>`)
      + `<p class="help">${esc(t('O prueba el ejemplo de Matemáticas II, que no necesita clave.'))}</p>`;
    $('exPreg').innerHTML = ''; $('exNota').innerHTML = ''; $('exNota').hidden = true; return;
  }
  $('exNota').hidden = false;
  const f = ejemploOn() ? '' : fuenteActual();
  const mios = ejemploOn() ? [] : bibDe(S.c, S.m), rec = recActual();
  const opciones = ejemploOn() ? [] : [...(MEM.examenes[k] ? [['oficial', t('Examen de PAUsible')]] : []),
    ...mios.slice(0, 6).map(r => ['bib:' + r.id, (r.origen === 'reto' ? t('Reto') : t('Mío')) + ' · ' + fechaCorta(r.creado) + (mejorNota(r) != null ? ' · ' + fmtN(mejorNota(r)) : '')])];
  const selector = opciones.length > 1 || mios.length ? `<div class="pa-fuentes" role="group" aria-label="${esc(t('Qué examen hacer'))}">${opciones.map(([v, l]) => `<button type="button" class="btn btn-sm ${v === f ? 'btn-primary' : 'btn-ghost'}" data-fuente="${v}" aria-pressed="${v === f}">${esc(l)}</button>`).join('')}${mios.length ? `<button type="button" class="btn btn-sm btn-ghost" id="btnVerBib">${esc(t('Ver todos mis exámenes ({0})', MEM.bib.length))}</button>` : ''}</div>` : '';
  const avisoReto = rec && rec.origen === 'reto' ? `<p class="fa-chip aviso" style="margin:0 0 8px">${esc(t('Generado con la clave de quien te reta · doble resolución · no revisado por PAUsible'))}</p>` : '';
  const avisoVersion = f === 'oficial' && ex.version_distinta ? `<p class="help">${esc(t('Este examen se ha actualizado desde que te retaron: las notas pueden no ser comparables.'))}</p>` : '';
  $('exCab').innerHTML = `${selector}${avisoReto}${avisoVersion}${ex.ficticio ? `<p class="fa-chip aviso" style="margin:0 0 8px">${esc(t('Ejemplo: soluciones comprobadas, temas ficticios'))}</p>` : ''}${rec && rec.origen === 'propio' ? `<p class="fa-chip aviso" style="margin:0 0 8px">${esc(t('Generado con tu clave'))}</p>` : ''}${ex.sin_prediccion ? `<p class="fa-chip" style="margin:0 0 8px">${esc(t('Sin predicción de temas: formato real y currículo oficial'))}</p>` : ''}${rec && (rec.intentos || []).length ? `<p class="help">${esc(t('Intentos: {0} · mejor nota: {1}', rec.intentos.length, mejorNota(rec) != null ? fmtN(mejorNota(rec)) : '–'))}</p>` : ''}<h3>${conFormulas(ex.titulo)}</h3><p>${conFormulas(ex.instrucciones)}</p>
    <div class="actions"><button class="btn btn-ghost" id="btnCrono" type="button">${ico('clock')}<span>${esc(S.crono ? t('Parar cronómetro') : t('Empezar cronómetro de {0} min', ex.duracion_min || 90))}</span></button><span class="pa-crono" id="crono" aria-live="off"></span>${!ejemploOn() && (prediccionDe(S.c, S.m) || {}).n_examenes ? `<button class="btn btn-ghost" id="btnGeneraOtro" type="button">${ico('sparkles')}<span>${esc(t('Generar otro con mi clave'))}</span></button>` : ''}</div><p class="help" id="genEstado"></p>
    ${ex.descartadas && ex.descartadas.length ? `<p class="help">${esc(t('Se descartaron {0} pregunta(s) porque los resolutores no coincidieron.', ex.descartadas.length))}</p>` : ''}`;
  $('exPreg').innerHTML = ex.preguntas.map((p, i) => `<div class="card pa-preg"><h3>${esc(t('Pregunta {0}', p.n || i + 1))} <span class="fa-chip">${esc(t('{0} puntos', fmtN(p.puntos)))}</span> ${insignia(p)}</h3>
    <div class="pa-enun">${conFormulas(p.enunciado)}</div>
    <details class="pa-sol"><summary>${esc(t('Ver solución y criterios'))}</summary><div class="md">${p.resultado ? `<p><b>${esc(t('Resultado:'))}</b> ${conFormulas(p.resultado)}</p>` : ''}${conFormulas(p.solucion || '', true)}${p.criterios ? `<p class="help"><b>${esc(t('Criterios:'))}</b> ${conFormulas(p.criterios)}</p>` : ''}</div></details>
    <div class="pa-auto"><label for="auto${i}">${esc(t('Mi nota en esta pregunta'))}</label><input id="auto${i}" data-i="${i}" type="number" min="0" max="${p.puntos}" step="0.25" inputmode="decimal" value="${S.auto[i] ?? ''}"><span class="sub">/ ${fmtN(p.puntos)}</span></div></div>`).join('');
  $$('.pa-auto input').forEach(inp => inp.oninput = () => { const v = inp.value === '' ? undefined : Math.min(+inp.max, Math.max(0, +inp.value)); if (v === undefined) delete S.auto[inp.dataset.i]; else S.auto[inp.dataset.i] = v; guarda(); pintaNota(ex); });
  pintaNota(ex); tic();
}
const insignia = p => p.verificacion === 'codigo' ? `<span class="fa-chip ok" title="${esc(t('Dos resoluciones independientes y su código coinciden'))}">✓ ${esc(t('comprobada por código'))}</span>`
  : p.verificacion === 'consenso' ? `<span class="fa-chip ok" title="${esc(t('Dos resoluciones independientes coinciden'))}">✓ ${esc(t('doble resolución'))}</span>` : `<span class="fa-chip aviso">${esc(t('sin verificar'))}</span>`;
/* Cada vez que el estudiante se corrige un examen de «Mis exámenes» se guarda el intento (fecha y nota) */
let _int;
function registraIntento(hechas, de) {
  const r = recActual(); if (!r) return;
  if (!S.intento || S.intento.rec !== r.id) { S.intento = {rec: r.id, id: nuevoId()}; r.intentos = [...(r.intentos || []), {id: S.intento.id, fecha: new Date().toISOString()}]; }
  const i = r.intentos.find(x => x.id === S.intento.id); if (!i) return;
  Object.assign(i, {nota: S.nota, hechas, de});
  clearTimeout(_int); _int = setTimeout(() => bibGuarda(r).catch(() => {}), 400);
}
const fechaCorta = iso => { try { return new Date(iso).toLocaleDateString(locale(), {day: 'numeric', month: 'short'}); } catch { return ''; } };
function pintaNota(ex) {
  const hechas = Object.keys(S.auto).length;
  if (!hechas) { $('exNota').innerHTML = `<p class="help" style="margin:0">${esc(t('Cuando te corrijas, aquí verás tu nota del simulacro.'))}</p>`; return; }
  S.nota = notaDe(ex.preguntas, S.auto);
  registraIntento(hechas, ex.preguntas.length);
  $('exNota').innerHTML = `<h3>${esc(t('Tu nota del simulacro'))}</h3><div class="pa-nota">${fmtN(S.nota)}</div><p class="sub">${esc(t('{0} de {1} preguntas corregidas', hechas, ex.preguntas.length))}</p><div class="actions"><button class="btn btn-primary" id="btnACompartir" type="button">${ico('share')}<span>${esc(t('Compartir mi resultado'))}</span></button></div>`;
}
document.addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.id === 'btnACompartir') go(4);
  if (b.id === 'btnCrono') { S.crono = S.crono ? null : Date.now() + (examenActual().duracion_min || 90) * 60000; pintaExamen(); }
  if (b.id === 'btnGenera' || b.id === 'btnGeneraOtro') generaConClave(b);
  if (b.id === 'btnVerBib') go(7);
  if (b.dataset.fuente) { S.fuente[clave()] = b.dataset.fuente; S.auto = {}; S.intento = null; S.crono = null; guarda(); pintaExamen(); }
});
function tic() {
  clearTimeout(tic._t); const el = $('crono'); if (!el) return;
  if (!S.crono) { el.textContent = ''; return; }
  const q = Math.max(0, (S.crono - Date.now()) / 1000); el.textContent = mmss(q);
  if (q <= 0) { S.crono = null; toast(t('¡Tiempo! Deja el boli y corrígete.')); return; }
  if (step === 3) tic._t = setTimeout(tic, 1000);
}
let busy = false;
async function generaConClave(b) {
  if (busy) return;
  if (!pideClave()) return;
  const reg = prediccionDe(S.c, S.m); if (!reg || !reg.n_examenes) return;
  busy = true; b.disabled = true; const st = $('genEstado');
  const ask = async prompt => llmJSON([{role: 'system', content: SYS_PAU}, {role: 'user', content: prompt}], {max: 6000});
  try {
    const ctx = await cargaContexto(S.c, S.m);   // preguntas reales de años anteriores de esta comunidad y materia
    st.innerHTML = `<span class="spin"></span> ${esc(t('El ponente redacta el examen…'))}`;
    const ex = await generaExamen(ask, nombreCCAA(S.c), nombreMat(S.m), reg.temas.slice(0, 8), (i, k, n) => {
      st.innerHTML = `<span class="spin"></span> ${esc(t('Pregunta {0} de {1}: {2}', i + 1, n, t(['resolutor A', 'resolutor B', 'desempate', 'tribunal'][k])))}`;
    }, ctx);
    if (ctx) ex.con_contexto = true;
    if (!(reg.temas || []).length) ex.sin_prediccion = true;
    if (!ex.preguntas.length) throw new Error(t('Ninguna pregunta superó la doble resolución. Prueba otra vez o con otro modelo.'));
    const r = await alBib(S.c, S.m, ex, 'propio'); S.fuente[clave()] = 'bib:' + r.id; S.auto = {}; S.intento = null; await guardaYa(); pintaExamen();
  } catch (e) { st.textContent = e.message; toast(e.message, 8000); }
  finally { busy = false; b.disabled = false; }
}

/* ── 4 · comparte ── */
function datosTarjeta() {
  const reg = predActual() || {temas: []}, ex = examenActual(), c = cc();
  const notaOk = Object.keys(S.auto).length && ex;
  return {cabecera: t('Mi PAU 2027'), materia: ejemploOn() ? t('Matemáticas II') + ' · ' + t('ejemplo') : nombreMat(S.m), ccaa: ejemploOn() ? t('Datos ficticios de demostración') : nombreCCAA(S.c),
    titTop: t('Lo más probable que caiga'), top: reg.temas || [], nota: notaOk ? S.nota : null, titNota: t('Mi nota en el examen probable'), notaTxt: notaOk ? fmtN(S.nota) : '',
    dias: c && !ejemploOn() ? t('Faltan {0} días', diasHasta(c.fecha)) : '', cta: t('¿Me superas? → pausible')};
}
async function enlaceActual() {
  if (ejemploOn()) return URL_APP;
  const ex = examenActual(), f = fuenteActual(), n = Object.keys(S.auto).length ? S.nota : null;
  if (!ex) return enlaceReto({c: S.c, m: S.m, n});
  if (f === 'oficial') return enlaceReto({c: S.c, m: S.m, n, v: ex.version || ''});
  return enlaceReto({c: S.c, m: S.m, n, x: await comprimeExamen(ex)});   // examen de un estudiante: viaja dentro del enlace
}
async function ficheroExamen() {
  const ex = examenActual(); if (!ex) return;
  const j = {pausible: 1, c: S.c, m: S.m, n: Object.keys(S.auto).length ? S.nota : null, x: await comprimeExamen(ex)};
  dl(`pausible-${S.c}-${S.m}.json`, new Blob([JSON.stringify(j)], {type: 'application/json'}));
}
function textoReto() {
  const n = Object.keys(S.auto).length ? fmtN(S.nota) : null;
  return n ? t('He sacado un {0} en el examen PAUsible de {1} ({2}). ¿Me superas?', n, ejemploOn() ? t('Matemáticas II') : nombreMat(S.m), ejemploOn() ? t('ejemplo') : nombreCCAA(S.c))
    : t('Esto es lo más probable que caiga en la PAU 2027 de {0}. Míralo:', ejemploOn() ? t('Matemáticas II') : nombreMat(S.m));
}
async function pintaComparte() {
  tarjeta($('cvTarjeta'), datosTarjeta());
  LINK = await enlaceActual();
  $('btnWa').href = 'https://wa.me/?text=' + encodeURIComponent(textoReto() + ' ' + LINK);
  const propio = !ejemploOn() && examenActual() && fuenteActual() !== 'oficial';
  $('btnExJson').hidden = !propio;
  $('compTxt').textContent = t('Quien abra tu enlace hará el mismo examen probable y podrá comparar su nota con la tuya.')
    + (propio ? ' ' + t('Tu examen va dentro del enlace: no se sube a ningún sitio.') : '')
    + (LINK.length > ENLACE_MAX ? ' ' + t('El enlace es largo: si el sitio donde lo compartes lo corta, envía también el examen como fichero.') : '');
}
$('btnExJson').onclick = ficheroExamen;
const pngBlob = () => new Promise(r => $('cvTarjeta').toBlob(r, 'image/png'));
$('btnPng').onclick = async () => dl('pausible.png', await pngBlob());
$('btnShare').onclick = async () => {
  const f = new File([await pngBlob()], 'pausible.png', {type: 'image/png'}), url = LINK || await enlaceActual();
  try {
    if (navigator.canShare && navigator.canShare({files: [f]})) await navigator.share({files: [f], text: textoReto() + ' ' + url});
    else if (navigator.share) await navigator.share({text: textoReto(), url});
    else { dl('pausible.png', f); toast(t('Imagen descargada: súbela a tu historia')); }
  } catch (e) { if (e.name !== 'AbortError') toast(e.message); }
};
$('btnLink').onclick = async () => { const url = LINK || await enlaceActual(); try { await navigator.clipboard.writeText(textoReto() + ' ' + url); toast(t('Enlace copiado')); } catch { toast(url, 9000); } };

/* ── 5 · ranking ── */
function pintaRanking() {
  if (!hayDatos()) { $('rankCCAA').innerHTML = `<p>${esc(t('El ranking aparecerá cuando se cargue el corpus de exámenes oficiales.'))}</p>`; $('rankTemas').innerHTML = ''; $('selMatRank').innerHTML = ''; return; }
  const filas = Object.entries(DATOS.pred.ccaa).filter(([, c]) => c.predecibilidad != null).sort((a, b) => b[1].predecibilidad - a[1].predecibilidad);
  $('rankCCAA').innerHTML = `<h3>${esc(t('PAU más previsible'))}</h3><p class="help">${esc(t('Porcentaje medio de temas del último examen que el método habría acertado con los exámenes anteriores.'))}</p>`
    + filas.map(([id, c], i) => `<div class="pa-rank"><span>${i + 1}</span><span>${esc(c.nombre)}</span><b>${fmtP(c.predecibilidad)}</b></div>`).join('');
  const mats = Object.keys(DATOS.pred.nacional || {});
  const sel = $('selMatRank'); if (!sel.options.length || sel.dataset.n !== String(mats.length)) { sel.innerHTML = mats.map(m => `<option value="${m}">${esc(nombreMat(m))}</option>`).join(''); sel.dataset.n = mats.length; sel.value = mats.includes(S.m) ? S.m : mats[0] || ''; }
  const lista = DATOS.pred.nacional[sel.value] || [];
  $('rankTemas').innerHTML = `<h3>${esc(t('Lo más probable en toda España'))}</h3>` + lista.map((x, i) => `<div class="pa-rank"><span>${i + 1}</span><span>${esc(x.nombre)} <small class="sub">· ${esc(t('{0} comunidades', x.ccaa))}</small></span><b>${fmtP(x.p)}</b></div>`).join('');
}
$('selMatRank').onchange = pintaRanking;

/* ── 6 · cómo conseguir la clave (adaptado de ProfesorIA para estudiantes) ── */
const lista = (tit, items, tag = 'ul') => `<h3>${esc(t(tit))}</h3><${tag}>${items.map(x => `<li>${esc(t(x))}</li>`).join('')}</${tag}>`;
function pintaClave() {
  $('claveEdad').innerHTML = `<h3>${esc(t('Antes de nada: la edad'))}</h3><p>${esc(t('OpenAI permite usar su API desde los 13 años, pero si eres menor de 18 necesitas el permiso de tu madre, padre o tutor. Anthropic Claude exige tener 18 años. Si eres menor, pide a un adulto que cree la clave, fije el límite de gasto y te la deje usar en este navegador.'))}</p>`;
  $('clavePasos').innerHTML = lista('Crear la clave con límite de gasto (OpenAI)', [
    'Entra en platform.openai.com y crea una cuenta. Es distinta de la de ChatGPT, aunque puedes usar el mismo correo.',
    'En Billing, añade un método de pago y compra un crédito pequeño (por ejemplo, 5 €). Fija un límite de gasto mensual bajo antes de crear la clave.',
    'En API keys, pulsa Create new secret key. Cópiala y guárdala en un lugar seguro: no se vuelve a mostrar.',
    'En PAUsible, pulsa IA arriba a la derecha, elige OpenAI, pega la clave, pulsa «Ver los modelos de mi clave» y elige uno económico.',
    'No la compartas ni la pegues en chats o redes. Si se expone, revócala en la plataforma y crea otra.'], 'ol')
    + `<div class="actions"><a class="btn btn-ghost btn-sm" href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI</a><a class="btn btn-ghost btn-sm" href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">Anthropic Claude (+18)</a></div>`;
  $('claveCoste').innerHTML = lista('¿Cuánto cuesta?', [
    'Se paga por uso, por tokens (trozos de texto). Con un modelo económico, un examen probable completo cuesta unos céntimos.',
    'Cada examen hace varias llamadas: un ponente lo redacta y dos resolutores lo resuelven por separado; si no coinciden, un tercero desempata.',
    'Con el límite de gasto que fijas, nunca pagarás más de lo que hayas decidido.',
    'La clave se guarda solo en este navegador y solo se envía a tu proveedor. PAUsible no la ve ni la guarda en ningún servidor.']);
  $('claveChat').innerHTML = lista('Suscripción mensual al chatbot (ChatGPT, Claude…)', [
    'Cuota fija cada mes, la uses mucho o poco.',
    'Conversación libre: el resultado depende de cómo preguntes y cambia de una vez a otra.',
    'Las soluciones que te da las tienes que comprobar tú.',
    'Un examen completo se hace pregunta a pregunta, copiando y pegando.',
    'No sirve para PAUsible: la suscripción no incluye la clave de API, que se paga aparte.']);
  $('claveApi').innerHTML = lista('Clave de API en PAUsible', [
    'Pagas solo lo que usas: céntimos por examen, con un límite que fijas tú.',
    'PAUsible organiza el trabajo: redacta el examen con los temas más probables de tu comunidad y lo resuelve dos veces por separado.',
    'Solo se queda lo que coincide; las preguntas sin acuerdo se descartan.',
    'Por API, OpenAI no usa tus datos para entrenar sus modelos por defecto.']);
  $('claveNota').textContent = t('Son complementarios: el chatbot va bien para preguntar dudas; la clave en PAUsible, para generar exámenes completos con solución revisada dos veces. Y recuerda: no hace falta ninguna de las dos para usar las predicciones ni los exámenes ya generados.');
}
/* ── 7 · Mis exámenes ── */
function pintaBiblioteca() {
  const todos = MEM.bib;
  const mats = [...new Set(todos.map(r => r.m))].sort((a, b) => nombreMat(a).localeCompare(nombreMat(b)));
  const selM = $('bibMat'), selO = $('bibOrig'), vm = selM.value, vo = selO.value;
  selM.innerHTML = `<option value="">${esc(t('Todas las materias'))}</option>` + mats.map(m => `<option value="${m}">${esc(nombreMat(m))}</option>`).join('');
  selM.value = mats.includes(vm) ? vm : '';
  selO.innerHTML = [['', t('Todos')], ['propio', t('Generados por mí')], ['reto', t('Retos recibidos')]].map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('');
  selO.value = vo || '';
  const lista = todos.filter(r => (!selM.value || r.m === selM.value) && (!selO.value || r.origen === selO.value));
  $('bibResumen').textContent = todos.length ? t('{0} exámenes guardados en este navegador. Si borras los datos del navegador se pierden: exporta una copia de vez en cuando.', todos.length) : '';
  $('bibLista').innerHTML = !todos.length ? `<div class="card"><p style="margin:0">${esc(t('Aún no tienes exámenes guardados. Aparecen aquí los que generas con tu clave y los que recibes en un reto.'))}</p></div>`
    : !lista.length ? `<div class="card"><p style="margin:0">${esc(t('Ningún examen con estos filtros.'))}</p></div>`
    : lista.map(r => {
      const pr = r.ex.preguntas || [], cod = pr.filter(p => p.verificacion === 'codigo').length, mn = mejorNota(r);
      return `<div class="card pa-bib"><div class="pa-bib-cab"><div><b>${conFormulas(r.ex.titulo || nombreMat(r.m))}</b><div class="sub">${esc(nombreMat(r.m))} · ${esc(nombreCCAA(r.c))} · ${esc(fechaCorta(r.creado))}</div></div>
        <div class="pa-bib-nota">${mn != null ? fmtN(mn) : '–'}<small>${esc(t('mejor nota'))}</small></div></div>
        <p class="pa-bib-meta"><span class="fa-chip ${r.origen === 'reto' ? 'aviso' : ''}">${esc(r.origen === 'reto' ? t('Reto recibido') : t('Generado por mí'))}</span> <span class="fa-chip">${esc(t('{0} preguntas', pr.length))}</span>${cod ? ` <span class="fa-chip ok">✓ ${esc(t('{0} comprobadas por código', cod))}</span>` : ''} <span class="sub">${esc(t('{0} intentos', (r.intentos || []).length))}${r.reto_nota != null ? ' · ' + esc(t('nota de quien te retó: {0}', fmtN(r.reto_nota))) : ''}</span></p>
        <div class="actions" style="margin-top:8px"><button class="btn btn-primary btn-sm" type="button" data-abrir="${r.id}">${esc(t('Hacer de nuevo'))}</button><button class="btn btn-ghost btn-sm" type="button" data-retar="${r.id}">${esc(t('Retar con este examen'))}</button><button class="btn btn-ghost btn-sm" type="button" data-borrar="${r.id}">${esc(t('Borrar'))}</button></div></div>`;
    }).join('');
}
$('bibMat').onchange = pintaBiblioteca; $('bibOrig').onchange = pintaBiblioteca;
function abreDeBib(id) { const r = MEM.bibId[id]; if (!r) return false; S.c = r.c; S.m = r.m; S.ejemplo = false; S.fuente[`${r.c}__${r.m}`] = 'bib:' + id; S.auto = {}; S.intento = null; S.crono = null; guarda(); return true; }
document.addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.dataset.abrir && abreDeBib(b.dataset.abrir)) go(3);
  if (b.dataset.retar && abreDeBib(b.dataset.retar)) go(4);
  if (b.dataset.borrar) {
    if (b.dataset.seguro !== '1') { b.dataset.seguro = '1'; b.textContent = t('¿Seguro? Pulsa otra vez'); b.classList.add('btn-danger'); setTimeout(() => { if (b.isConnected) { b.dataset.seguro = ''; b.textContent = t('Borrar'); b.classList.remove('btn-danger'); } }, 4000); return; }
    await bibBorra(b.dataset.borrar); await recargaBib(); pintaBiblioteca(); toast(t('Examen borrado'));
  }
  if (b.id === 'btnBib') go(7);
});
$('btnBibExp').onclick = async () => { const j = await bibExporta(); dl(`pausible-mis-examenes-${new Date().toISOString().slice(0, 10)}.json`, new Blob([JSON.stringify(j)], {type: 'application/json'})); toast(t('Copia de seguridad descargada: {0} exámenes', j.n)); };
$('fichBib').onchange = async e => {
  const f = e.target.files[0]; e.target.value = ''; if (!f) return;
  try { const n = await bibImporta(JSON.parse(await f.text())); await recargaBib(); pintaBiblioteca(); toast(t('Importados {0} exámenes', n)); }
  catch { toast(t('Ese fichero no es una copia de «Mis exámenes».'), 6000); }
};

$('btnGuiaClave').onclick = () => { $('mIA').classList.remove('on'); go(6); };
document.addEventListener('click', e => { if (e.target.closest('#lnkClave')) { e.preventDefault(); go(6); } });

window.addEventListener('langchange', () => { if (step === 4) pintaComparte(); });
(async () => {
  const prev = await cargaEstado(); if (prev) S = {...S, ...prev, crono: null};
  S.fuente = S.fuente || {}; S.intento = null;
  // versiones anteriores: exámenes dentro del estado (S.examen, S.propios, S.retos) → «Mis exámenes»
  iniciaUI(); go(0);
  const datos = cargaDatos();   // los datos y la interfaz no esperan a «Mis exámenes»
  try {
    const viejos = [];
    if (S.examen && S.examen.ex) viejos.push([S.examen.c, S.examen.m, S.examen.ex, 'propio']);
    for (const [k, l] of Object.entries(S.propios || {})) for (const ex of [...l].reverse()) viejos.push([...k.split('__'), ex, 'propio']);
    for (const [k, ex] of Object.entries(S.retos || {})) viejos.push([...k.split('__'), ex, 'reto']);
    for (const [c, m, ex, o] of viejos) await bibGuarda(bibNuevo(c, m, ex, o));
    if (viejos.length || S.propios || S.retos || S.examen) { delete S.examen; delete S.propios; delete S.retos; for (const k in S.fuente) if (!/^(oficial|bib:)/.test(S.fuente[k])) delete S.fuente[k]; await guardaYa(); }
  } catch {}
  await recargaBib();
  await datos; (RENDER[step] || (() => {}))();
  if (RETO && step === 0) pintaInicio();
})();
