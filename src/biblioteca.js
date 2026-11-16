/* ══ «Mis exámenes»: biblioteca local en IndexedDB (base propia, un registro por examen) ══
   Registro: {id, c, m, origen: 'propio'|'reto', creado, ex, reto_nota?, intentos: [{id, fecha, nota, hechas, de}]}
   Nada sale del navegador salvo que el estudiante exporte la copia de seguridad. */
const BIB_DB = 'pausible_biblioteca';
const BIB_AVISO = 500;   // por encima, se avisa (cada examen ocupa unos 10-20 KB)
let _bib = null;
function bibAbre() {
  if (!_bib) _bib = new Promise((ok, ko) => {
    const r = indexedDB.open(BIB_DB, 1);
    r.onupgradeneeded = () => { const st = r.result.createObjectStore('examenes', {keyPath: 'id'}); st.createIndex('creado', 'creado'); };
    r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error); r.onblocked = () => ko(new Error('bloqueada'));
    setTimeout(() => ko(new Error('sin respuesta')), 4000);   // navegadores integrados (Instagram, WhatsApp…) a veces no responden
  });
  _bib.catch(() => { _bib = null; });
  return _bib;
}
async function bibTx(modo, fn) {
  const d = await bibAbre();
  return new Promise((ok, ko) => { const tx = d.transaction('examenes', modo), q = fn(tx.objectStore('examenes')); tx.oncomplete = () => ok(q && q.result); tx.onerror = () => ko(tx.error); });
}
const bibTodos = async () => ((await bibTx('readonly', s => s.getAll())) || []).sort((a, b) => String(b.creado).localeCompare(String(a.creado)));
const bibGuarda = rec => bibTx('readwrite', s => s.put(rec));
const bibBorra = id => bibTx('readwrite', s => s.delete(id));
const nuevoId = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
function bibNuevo(c, m, ex, origen, extra = {}) {
  return {id: nuevoId(), c, m, origen, creado: new Date().toISOString(), ex: paqueteExamen(ex), intentos: [], ...extra};
}
const mejorNota = r => (r.intentos || []).reduce((mx, i) => i.nota != null && (mx == null || i.nota > mx) ? i.nota : mx, null);
async function pidePersistencia() { try { if (navigator.storage && navigator.storage.persist && !(await navigator.storage.persisted())) await navigator.storage.persist(); } catch {} }

/* copia de seguridad: un fichero con todos los registros; importar fusiona por id (no duplica) */
async function bibExporta() {
  const regs = await bibTodos();
  return {pausible_biblioteca: 1, exportado: new Date().toISOString(), n: regs.length, registros: regs};
}
async function bibImporta(j) {
  if (!j || j.pausible_biblioteca !== 1 || !Array.isArray(j.registros)) throw new Error('formato');
  let n = 0;
  for (const r of j.registros) {
    if (!r || typeof r.id !== 'string' || !CCAA.some(x => x.id === r.c) || !MATERIAS[r.m] || !r.ex || !Array.isArray(r.ex.preguntas)) continue;
    await bibGuarda({id: r.id, c: r.c, m: r.m, origen: r.origen === 'reto' ? 'reto' : 'propio', creado: String(r.creado || new Date().toISOString()),
      ex: paqueteExamen(r.ex), reto_nota: r.reto_nota ?? null, intentos: Array.isArray(r.intentos) ? r.intentos.slice(0, 200) : []});
    n++;
  }
  return n;
}
