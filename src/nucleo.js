/* ══ Núcleo de PAUsible: lógica pura (sin DOM salvo la tarjeta), probada en Node. ══ */
let DATOS = {pred: null, idx: [], cargado: false};

async function cargaDatos() {
  try {
    const r = await fetch('data/predicciones.json', {cache: 'no-cache'});
    if (r.ok) DATOS.pred = await r.json();
  } catch {}
  try {
    const r = await fetch('data/examenes/index.json', {cache: 'no-cache'});
    if (r.ok) DATOS.idx = await r.json();
  } catch {}
  DATOS.cargado = true;
  return DATOS;
}
const hayDatos = () => !!(DATOS.pred && Object.keys(DATOS.pred.ccaa || {}).length);
const nombreCCAA = id => (CCAA.find(c => c.id === id) || {}).nombre || id;
const nombreMat = id => MATERIAS[id] || id;
function materiasDe(cid) {
  const m = hayDatos() && DATOS.pred.ccaa[cid] ? Object.keys(DATOS.pred.ccaa[cid].materias) : [];
  return m.sort((a, b) => Object.keys(MATERIAS).indexOf(a) - Object.keys(MATERIAS).indexOf(b));
}
const prediccionDe = (cid, mid) => (hayDatos() && DATOS.pred.ccaa[cid] && DATOS.pred.ccaa[cid].materias[mid]) || null;
const tieneExamen = (cid, mid) => DATOS.idx.includes(`${cid}__${mid}`);
/* Huella de un examen del repositorio: primeros 10 caracteres del SHA-1 del fichero tal cual (igual que pipeline/genera.py).
   Va en el enlace del reto; si el examen se regenera, la versión antigua queda en data/examenes/archivo/. */
async function huella(texto) {
  try {
    const b = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(texto));
    return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('').slice(0, 10);
  } catch { return ''; }
}
async function cargaExamen(cid, mid, version = '') {
  const urls = [`data/examenes/${cid}__${mid}.json`];
  if (version) urls.unshift(`data/examenes/archivo/${cid}__${mid}__${version}.json`);
  for (const u of urls) {
    try {
      const r = await fetch(u, {cache: 'no-cache'}); if (!r.ok) continue;
      const txt = await r.text(), ex = JSON.parse(txt);
      ex.version = await huella(txt); ex.origen = 'pausible';
      if (!version || ex.version === version || u.includes('/archivo/')) return ex;
      ex.version_distinta = true; return ex;        // no se encontró la versión pedida: se usa la actual y se avisa
    } catch {}
  }
  return null;
}

/* días hasta la PAU de esa comunidad (fecha oficial si se ha publicado; si no, estimada y así se dice) */
function diasHasta(fecha, hoy = new Date()) {
  const f = new Date(fecha + 'T09:00:00'), d = Math.ceil((f - hoy) / 864e5);
  return Math.max(0, d);
}

/* nota del simulacro a partir de la autoevaluación con los criterios (cada pregunta: puntos obtenidos) */
function notaDe(preguntas, auto) {
  const tot = preguntas.reduce((s, p) => s + (+p.puntos || 0), 0) || 1;
  const sac = preguntas.reduce((s, p, i) => s + Math.min(+p.puntos || 0, Math.max(0, +(auto[i] ?? 0))), 0);
  return Math.round(sac / tot * 1000) / 100;
}

/* reto: enlace que abre la misma comunidad y materia con la nota de quien reta */
/* Enlace de reto. Examen del repositorio → ?v=<huella>. Examen generado por un estudiante → el examen entero,
   comprimido, en el #fragmento (no llega a ningún servidor: lo lee solo el navegador de quien abre el enlace). */
function enlaceReto({c, m, n, v, x}, base = URL_APP) {
  const q = new URLSearchParams({c, m}); if (n != null) q.set('n', String(n)); if (v) q.set('v', v);
  return base + '?' + q.toString() + (x ? '#e=' + x : '');
}
function leeReto(search, hash = '') {
  const q = new URLSearchParams(search || '');
  const c = q.get('c'), m = q.get('m'), n = q.get('n'), v = q.get('v');
  if (!c || !CCAA.some(x => x.id === c) || !m || !MATERIAS[m]) return null;
  const nota = n != null && /^\d{1,2}(\.\d{1,2})?$/.test(n) && +n <= 10 ? +n : null;
  const e = (String(hash).match(/[#&]e=([A-Za-z0-9_-]+)/) || [])[1] || '';
  return {c, m, n: nota, v: /^[0-9a-f]{6,40}$/.test(v || '') ? v : '', x: e};
}
/* Solo lo necesario para hacer y corregir el examen */
function paqueteExamen(ex) {
  const P = ['n', 'tema', 'puntos', 'tipo', 'enunciado', 'resultado', 'solucion', 'criterios', 'verificacion', 'resoluciones'];
  return {titulo: ex.titulo, duracion_min: ex.duracion_min, instrucciones: ex.instrucciones, generado: ex.generado,
    preguntas: (ex.preguntas || []).map(p => Object.fromEntries(P.filter(k => p[k] != null).map(k => [k, p[k]])))};
}
const b64url = u8 => btoa(String.fromCharCode(...u8)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const deB64url = s => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), ch => ch.charCodeAt(0));
async function flujo(bytes, Clase) { return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new Clase('deflate-raw'))).arrayBuffer()); }
/* 'z' + deflate (navegadores actuales) o 'j' + JSON sin comprimir (si el navegador no sabe comprimir) */
async function comprimeExamen(ex) {
  const bytes = new TextEncoder().encode(JSON.stringify(paqueteExamen(ex)));
  try { if (typeof CompressionStream !== 'undefined') return 'z' + b64url(await flujo(bytes, CompressionStream)); } catch {}
  let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
  return 'j' + btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
async function descomprimeExamen(x) {
  try {
    const bytes = x[0] === 'z' ? await flujo(deB64url(x.slice(1)), DecompressionStream) : deB64url(x.slice(1));
    const ex = JSON.parse(new TextDecoder().decode(bytes));
    if (!Array.isArray(ex.preguntas) || !ex.preguntas.length || ex.preguntas.length > 30) return null;
    ex.preguntas = ex.preguntas.filter(p => p && typeof p.enunciado === 'string').map(p => ({...p, puntos: Math.min(10, Math.max(0, +p.puntos || 0))}));
    return {...ex, origen: 'estudiante'};
  } catch { return null; }
}
const ENLACE_MAX = 6000;   // por encima, algunos sitios cortan el enlace: se ofrece además el fichero

/* LaTeX ligero → texto legible (sin librerías: la CSP no deja cargar nada y la app ha de ir sin red) */
function latexLite(s) {
  let x = String(s || '');
  const SUP = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻', '+': '⁺', 'n': 'ⁿ', 'x': 'ˣ'};
  const SUB = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'};
  const sup = t => [...t].every(ch => SUP[ch]) ? [...t].map(ch => SUP[ch]).join('') : '^(' + t + ')';
  const sub = t => [...t].every(ch => SUB[ch]) ? [...t].map(ch => SUB[ch]).join('') : '_(' + t + ')';
  for (let k = 0; k < 3; k++) x = x.replace(/\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}/g, '($1)/($2)').replace(/\\sqrt\{([^{}]*)\}/g, '√($1)');
  const MAP = {'\\cdot': '·', '\\times': '×', '\\leq': '≤', '\\le': '≤', '\\geq': '≥', '\\ge': '≥', '\\neq': '≠', '\\infty': '∞', '\\pi': 'π', '\\alpha': 'α', '\\beta': 'β', '\\lambda': 'λ', '\\mu': 'μ', '\\sigma': 'σ', '\\theta': 'θ', '\\Delta': 'Δ', '\\int': '∫', '\\sum': '∑', '\\to': '→', '\\rightarrow': '→', '\\Rightarrow': '⇒', '\\pm': '±', '\\approx': '≈', '\\in': '∈', '\\mathbb{R}': 'ℝ', '\\lim': 'lím', '\\ln': 'ln', '\\log': 'log', '\\sin': 'sen', '\\cos': 'cos', '\\tan': 'tg', '\\left': '', '\\right': '', '\\,': ' ', '\\;': ' ', '\\!': ''};
  for (const [k, v] of Object.entries(MAP).sort((a, b) => b[0].length - a[0].length)) x = x.split(k).join(v);
  x = x.replace(/\^\{([^{}]*)\}/g, (_, t) => sup(t)).replace(/\^(\w)/g, (_, t) => sup(t)).replace(/_\{([^{}]*)\}/g, (_, t) => sub(t)).replace(/_(\d)/g, (_, t) => sub(t));
  return x.replace(/\$\$?/g, '').replace(/\\text\{([^{}]*)\}/g, '$1').replace(/\\\\/g, '\n');
}

/* Texto con fórmulas → HTML. Las fórmulas ($…$, $$…$$, \(…\), \[…\]) se apartan antes del Markdown
   (que se comería los _ y los *) y se pintan con KaTeX, que va dentro del propio HTML. Química con \ce{…}.
   Si KaTeX fallara en una fórmula, se muestra en texto legible (latexLite) en vez de en crudo. */
const MATH_RX = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$(?=\S)((?:\\\$|[^$\n])+?)(?<=\S)\$(?!\d)/g;   // $…$ como en Pandoc: sin espacio pegado al $ (así «3$ y 5$» no es una fórmula)
function formula(tex, display) {
  try {
    if (typeof katex !== 'undefined') return katex.renderToString(tex, {displayMode: display, throwOnError: false, strict: 'ignore', output: 'html'});
  } catch {}
  return esc(latexLite(tex));
}
/* fórmulas sueltas sin delimitadores: \ce{…}, \frac{…}{…}, \sqrt{…}… con sus llaves equilibradas */
const SUELTA_RX = /\\(ce|pu|frac|dfrac|tfrac|sqrt|vec|binom|overline|hat|mathbb|mathrm)(?=\s*[{\[])/g;
function sueltas(texto, guarda) {
  let out = '', i = 0, m;
  SUELTA_RX.lastIndex = 0;
  while ((m = SUELTA_RX.exec(texto))) {
    let j = m.index + m[0].length, grupos = 0;
    while (j < texto.length) {
      let k0 = j; while (texto[k0] === ' ') k0++;
      const abre = texto[k0], cierra = abre === '{' ? '}' : abre === '[' ? ']' : null;
      if (!cierra || (abre === '[' && grupos)) break;
      let prof = 0, k = k0;
      for (; k < texto.length; k++) { if (texto[k] === abre) prof++; else if (texto[k] === cierra && --prof === 0) break; }
      if (prof) break;
      j = k + 1; grupos++;
    }
    if (!grupos) continue;
    out += texto.slice(i, m.index) + guarda(texto.slice(m.index, j), false);
    i = j; SUELTA_RX.lastIndex = j;
  }
  return out + texto.slice(i);
}
function conFormulas(texto, markdown = false) {
  const trozos = [];
  const guarda = (tex, display) => { trozos.push(formula(tex.trim(), display)); return `\u0000${trozos.length - 1}\u0000`; };
  let marcado = String(texto || '').replace(MATH_RX, (m, a, b, c, d) => guarda(a ?? b ?? c ?? d, a != null || b != null));
  marcado = sueltas(marcado, guarda);
  const html = markdown ? md(marcado) : esc(marcado);
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => trozos[+i]);
}

/* igualdad numérica con tolerancia relativa (misma regla que pipeline/genera.py) */
function iguales(a, b, tol = 1e-3) {
  if (!Array.isArray(a) || !Array.isArray(b) || !a.length || a.length !== b.length) return false;
  return a.every((x, i) => Number.isFinite(+x) && Number.isFinite(+b[i]) && Math.abs(x - b[i]) <= tol * Math.max(1, Math.abs(x), Math.abs(b[i])));
}

/* ── Generación con tu clave: ponente + dos resolutores independientes + desempate/tribunal (como el pipeline, sin ejecutar código) ── */
const SYS_PAU = 'Eres miembro de la comisión que elabora la PAU (selectividad) en España. Eres riguroso y respondes SOLO con JSON válido.';
const P_PONENTE = (cc, mat, temas) => `Redacta un examen ORIGINAL de «${mat}» para la PAU 2027 de ${cc}, con el formato del modelo vigente desde 2025 (modelo único, 90 minutos, parte competencial con situaciones contextualizadas). Reparte las preguntas según estas probabilidades de tema, priorizando las más altas:
${temas.map(t => `- ${t.nombre}: ${Math.round(t.p * 100)} %`).join('\n')}
Cada pregunta debe tener UNA solución inequívoca; en cálculo, datos que den resultados limpios.
Devuelve SOLO JSON: {"titulo":"…","duracion_min":90,"instrucciones":"…","preguntas":[{"n":"1","tema":"id","puntos":2.5,"tipo":"calculo|abierta","enunciado":"… (fórmulas en LaTeX entre $…$)"}]}
Ids de tema válidos: ${temas.map(t => t.id).join(', ')}
${INSTR_IDIOMA()}`;
const P_RESOL = (mat, p, variante) => `Resuelve esta pregunta de la PAU de «${mat}» como la comisión correctora, paso a paso. ${variante}
Devuelve SOLO JSON: {"solucion":"desarrollo en Markdown, fórmulas en LaTeX entre $…$","resultado":"resultado final en una línea","numeros":[resultados finales como números, en orden; [] si no es de cálculo],"claves":["afirmaciones que una respuesta correcta debe contener"],"criterios":"reparto de puntos"}
${INSTR_IDIOMA()}

PREGUNTA (${p.puntos} puntos):
${p.enunciado}`;
const P_TRIB = (mat, p, sols) => `Eres el tribunal de la PAU de «${mat}». Compara estas resoluciones independientes. ¿Coinciden en lo esencial? ¿Alguna tiene un error de contenido?
Devuelve SOLO JSON: {"coinciden":true|false,"errores":["…"],"mejor":"A|B|ninguna"}
PREGUNTA: ${p.enunciado}
${sols.map((s, i) => `--- ${'AB'[i]} ---\n${s.solucion}\nClaves: ${JSON.stringify(s.claves || [])}`).join('\n\n')}`;
const VARIANTES = ['', 'Resuélvela por un método distinto al más habitual si existe y comprueba el resultado al final.', 'Sé especialmente cuidadoso con signos, unidades y casos particulares.'];

/* resuelve(): devuelve {sol, nivel} o null. «ask» es la función de IA (inyectable en las pruebas). */
async function resuelvePregunta(ask, mat, p, onPaso = () => {}) {
  const nums = s => (s.numeros || []).map(Number).filter(Number.isFinite);
  const sols = [];
  for (let k = 0; k < 2; k++) { onPaso(k); sols.push(await ask(P_RESOL(mat, p, VARIANTES[k]))); }
  if (p.tipo === 'calculo') {
    if (iguales(nums(sols[0]), nums(sols[1]))) return {sol: sols[0], nivel: 'consenso', n: 2};
    onPaso(2); sols.push(await ask(P_RESOL(mat, p, VARIANTES[2])));
    for (const [i, j] of [[0, 2], [1, 2]]) if (iguales(nums(sols[i]), nums(sols[j]))) return {sol: sols[i], nivel: 'consenso', n: 3};
    return null;
  }
  onPaso(3);
  const tr = await ask(P_TRIB(mat, p, sols));
  if (tr && tr.coinciden && !(tr.errores || []).length && (tr.mejor === 'A' || tr.mejor === 'B')) return {sol: sols[tr.mejor === 'A' ? 0 : 1], nivel: 'consenso', n: 2};
  return null;
}
async function generaExamen(ask, cc, mat, temas, onPaso = () => {}) {
  const ex = await ask(P_PONENTE(cc, mat, temas));
  const preguntas = [], descartadas = [];
  for (const [i, p] of (ex.preguntas || []).entries()) {
    const r = await resuelvePregunta(ask, mat, p, k => onPaso(i, k, ex.preguntas.length));
    if (r) preguntas.push({...p, solucion: r.sol.solucion, resultado: r.sol.resultado || '', criterios: r.sol.criterios || '', verificacion: r.nivel, resoluciones: r.n});
    else descartadas.push(p.n);
  }
  return {titulo: ex.titulo || mat, duracion_min: ex.duracion_min || 90, instrucciones: ex.instrucciones || '', preguntas, descartadas, propio: true, generado: new Date().toISOString().slice(0, 10)};
}

/* ── Tarjeta para compartir (formato historia 1080×1920) ── */
function tarjeta(cv, d) {
  const W = 1080, H = 1920; cv.width = W; cv.height = H;
  const x = cv.getContext('2d');
  const g = x.createLinearGradient(0, 0, W, H); g.addColorStop(0, '#2A1A6E'); g.addColorStop(0.55, '#6B4FD8'); g.addColorStop(1, '#E4572E');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  x.fillStyle = 'rgba(255,255,255,.08)'; for (let i = 0; i < 9; i++) { x.beginPath(); x.arc(980 - i * 40, 220 + i * 170, 120 + i * 18, 0, 7); x.fill(); }
  const F = (w, s) => `${w} ${s}px "Inter", "Segoe UI", system-ui, sans-serif`;
  const txt = (t, X, Y, f, c = '#fff', al = 'left') => { x.font = f; x.fillStyle = c; x.textAlign = al; x.fillText(t, X, Y); };
  const corta = (t, max, f) => { x.font = f; let s = String(t); while (x.measureText(s).width > max && s.length > 3) s = s.slice(0, -2); return s === String(t) ? s : s.trimEnd() + '…'; };
  txt('PAUsible', 90, 170, F(800, 84));
  txt(d.cabecera, 90, 240, F(600, 40), 'rgba(255,255,255,.85)');
  txt(corta(d.materia, 900, F(800, 64)), 90, 420, F(800, 64));
  txt(corta(d.ccaa, 900, F(500, 46)), 90, 490, F(500, 46), 'rgba(255,255,255,.9)');
  txt(d.titTop, 90, 640, F(700, 40), '#FFD166');
  d.top.slice(0, 3).forEach((tm, i) => {
    const Y = 720 + i * 190;
    x.fillStyle = 'rgba(255,255,255,.14)'; x.beginPath(); x.roundRect(90, Y, 900, 150, 28); x.fill();
    txt(`${Math.round(tm.p * 100)}%`, 130, Y + 98, F(800, 64), '#FFD166');
    txt(corta(tm.nombre, 600, F(600, 40)), 330, Y + 92, F(600, 40));
  });
  let y = 1340;
  if (d.nota != null) { txt(d.titNota, 90, y, F(600, 40), 'rgba(255,255,255,.85)'); txt(d.notaTxt, 90, y + 120, F(800, 140)); y += 230; }
  txt(d.dias, 90, y + 40, F(700, 48), '#fff');
  x.fillStyle = '#fff'; x.beginPath(); x.roundRect(90, 1700, 900, 120, 60); x.fill();
  txt(d.cta, W / 2, 1777, F(800, 42), '#2A1A6E', 'center');
  return cv;
}

if (typeof module !== 'undefined') module.exports = {conFormulas, paqueteExamen, comprimeExamen, descomprimeExamen, notaDe, enlaceReto, leeReto, latexLite, iguales, resuelvePregunta, generaExamen, diasHasta};
