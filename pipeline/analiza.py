#!/usr/bin/env python3
"""Del corpus (data/corpus.json + corpus/*.txt) a la predicción por comunidad y materia (data/predicciones.json).

Método (determinista, sin IA; mismo corpus → misma predicción):
  1. Cada examen se etiqueta por temas contando las raíces de temario.json (un tema está si suma ≥ 2 apariciones).
  2. Frecuencia ponderada por antigüedad: el modelo actual de PAU empezó en 2025, así que 2025-2026 pesan más.
     La extraordinaria pesa algo menos que la ordinaria y los modelos oficiales, la mitad.
  3. «Rebote»: un tema frecuente que no salió en la última ordinaria sube un poco (las comisiones tienden a rotar).
  4. Ningún tema baja del 5 %: la predicción ordena el estudio, no autoriza a saltarse temas.
  5. Validación ciega: se oculta la última ordinaria, se predice con lo anterior y se mide cuántos de los temas
     que de verdad cayeron estaban en el top. Se compara con el azar. De ahí sale la confianza que ve el estudiante.
"""
import json, pathlib, re, sys, time
from collections import defaultdict

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'pipeline'))
from crawl import norm  # noqa: E402

PESO_ANIO = {2026: 1.0, 2025: 0.85, 2024: 0.5, 2023: 0.4, 2022: 0.3}
PESO_CONV = {'ord': 1.0, 'ext': 0.8, 'nd': 0.7, 'modelo': 0.5}
UMBRAL = 2


def cuenta(texto, kws):
    n = ' ' + norm(texto) + ' '
    tot = 0
    for k in kws:
        k = norm(k).strip()
        fin = r'(?![a-z])' if len(k) <= 4 else ''   # raíces cortas («ph», «van», «tir») solo como palabra entera
        tot += min(5, len(re.findall(r'(?<![a-z])' + re.escape(k) + fin, n)))
    return tot


def etiqueta(texto, temas):
    return {t['id']: cuenta(texto, t['kw']) for t in temas}


def fragmento(texto, kws, largo=280):
    """Primer párrafo del examen que contiene una raíz del tema: se enseña como «así salió»."""
    for par in re.split(r'\n\s*\n', texto):
        p = re.sub(r'\s+', ' ', par).strip()
        if 40 < len(p) and any(norm(k).strip() in norm(p) for k in kws):
            return p[:largo] + ('…' if len(p) > largo else '')
    return ''


CAB_PREGUNTA = re.compile(r'(?im)^\s*(?:(?:pregunta|ejercicio|cuesti[oó]n|problema|exercici|q[üu]esti[oó]|pregunta|tarea|question|bloque|apartado|ariketa|galdera)\s*[A-Z]?\s*\d+|\d{1,2}\s*[.)-]\s+\S|[A-D]\s*\d\s*[.)])')


def bloques(texto):
    """Trocea un examen en preguntas por sus cabeceras («Ejercicio 2», «Pregunta 3», «2.»…); si no las hay, en párrafos."""
    idx = [m.start() for m in CAB_PREGUNTA.finditer(texto)]
    partes = [texto[a:b] for a, b in zip(idx, idx[1:] + [len(texto)])] if len(idx) >= 2 else re.split(r'\n\s*\n', texto)
    return [re.sub(r'[ \t]+', ' ', re.sub(r'\n{3,}', '\n\n', x)).strip() for x in partes if len(x.strip()) > 30]


def ejemplos(con, t, n=3, largo=900):
    """Cómo se ha preguntado un tema: el bloque con más raíces del tema de hasta n exámenes distintos, del más reciente al más antiguo."""
    out, vistos = [], set()
    for e in sorted(con, key=lambda e: (e['anio'], e['conv'] == 'ord'), reverse=True):
        if (e['anio'], e['conv']) in vistos: continue
        mejor = max(bloques(e['txt']), key=lambda b: cuenta(b, t['kw']), default='')
        if cuenta(mejor, t['kw']) < 1: continue
        vistos.add((e['anio'], e['conv']))
        out.append({'anio': e['anio'], 'conv': e['conv'], 'url': e['url'], 'texto': mejor[:largo] + ('…' if len(mejor) > largo else '')})
        if len(out) >= n: break
    return out


def predice(examenes, temas, ultimo_ord=None):
    """examenes: [{'anio','conv','hits':{tema:n}}]. Devuelve {tema: p}"""
    w_tot, f = 0.0, defaultdict(float)
    for e in examenes:
        w = PESO_ANIO.get(e['anio'], 0.25) * PESO_CONV.get(e['conv'], 0.7)
        w_tot += w
        for t in temas:
            if e['hits'].get(t['id'], 0) >= UMBRAL: f[t['id']] += w
    out = {}
    for t in temas:
        fr = f[t['id']] / w_tot if w_tot else 0
        rebote = 0.1 if ultimo_ord and fr >= 0.4 and ultimo_ord['hits'].get(t['id'], 0) < UMBRAL else 0
        out[t['id']] = round(min(0.97, max(0.05, fr * 0.9 + rebote)), 3)
    return out


def validacion(examenes, temas):
    ords = sorted((e for e in examenes if e['conv'] == 'ord'), key=lambda e: e['anio'])
    if len(examenes) < 3 or not ords: return None
    oculto = ords[-1]
    previos = [e for e in examenes if e['anio'] < oculto['anio']]
    if len(previos) < 2: return None
    prev_ords = [e for e in previos if e['conv'] == 'ord']
    p = predice(previos, temas, prev_ords[-1] if prev_ords else None)
    reales = {t['id'] for t in temas if oculto['hits'].get(t['id'], 0) >= UMBRAL}
    if not reales: return None
    k = len(reales)
    top = [tid for tid, _ in sorted(p.items(), key=lambda x: -x[1])[:k]]
    aciertos = len(reales & set(top))
    return {'anio': oculto['anio'], 'k': k, 'aciertos': aciertos, 'tasa': round(aciertos / k, 2), 'azar': round(k / len(temas), 2), 'top': top, 'reales': sorted(reales)}


def confianza(n, val):
    if not val: return 'baja'
    if n >= 6 and val['tasa'] >= 0.75 and val['tasa'] > val['azar']: return 'alta'
    if n >= 4 and val['tasa'] >= 0.5 and val['tasa'] > val['azar']: return 'media'
    return 'baja'


def tendencia(examenes, tid):
    nuevo = [e for e in examenes if e['anio'] >= 2025]; viejo = [e for e in examenes if e['anio'] < 2025]
    if not nuevo or not viejo: return 'estable'
    fn = sum(e['hits'].get(tid, 0) >= UMBRAL for e in nuevo) / len(nuevo)
    fv = sum(e['hits'].get(tid, 0) >= UMBRAL for e in viejo) / len(viejo)
    return 'sube' if fn - fv >= 0.25 else 'baja' if fv - fn >= 0.25 else 'estable'


def main():
    temario = {m['id']: m for m in json.loads((R / 'pipeline' / 'temario.json').read_text(encoding='utf-8'))['materias']}
    fuentes = json.loads((R / 'pipeline' / 'fuentes.json').read_text(encoding='utf-8'))
    corpus = json.loads((R / 'data' / 'corpus.json').read_text(encoding='utf-8'))['documentos']
    grupos = defaultdict(list)
    for d in corpus:
        if d['tipo'] != 'examen' or not d['materia']: continue
        p = R / d['txt']
        if not p.exists() or d.get('chars', 0) < 200: continue
        grupos[(d['ccaa'], d['materia'])].append((d, p.read_text(encoding='utf-8', errors='ignore')))
    out = {'generado': time.strftime('%Y-%m-%d'), 'metodo': __doc__.strip(), 'ccaa': {}, 'nacional': {}}
    acum = defaultdict(lambda: defaultdict(list))
    for (cid, mid), docs in sorted(grupos.items()):
        temas = temario[mid]['temas']
        ex = [{'anio': d['anio'], 'conv': d['conv'], 'url': d['url'], 'hits': etiqueta(txt, temas), 'txt': txt} for d, txt in docs]
        reg = {'nombre': temario[mid]['nombre'], 'n_examenes': len(ex), 'anios': sorted({e['anio'] for e in ex}),
               'examenes': [{'anio': e['anio'], 'conv': e['conv'], 'url': e['url']} for e in sorted(ex, key=lambda e: (e['anio'], e['conv']))]}
        if temas:
            ords = sorted((e for e in ex if e['conv'] == 'ord'), key=lambda e: e['anio'])
            p = predice(ex, temas, ords[-1] if ords else None)
            val = validacion(ex, temas)
            lista = []
            for t in temas:
                con = [e for e in ex if e['hits'].get(t['id'], 0) >= UMBRAL]
                ult = max(con, key=lambda e: (e['anio'], e['conv'] == 'ord'), default=None)
                lista.append({'id': t['id'], 'nombre': t['nombre'], 'p': p[t['id']], 'veces': len(con), 'de': len(ex),
                              'ultimo': ult['anio'] if ult else None, 'tendencia': tendencia(ex, t['id']),
                              'muestra': fragmento(ult['txt'], t['kw']) if ult else '', 'muestra_url': ult['url'] if ult else ''})
                acum[mid][t['id']].append((p[t['id']], len(ex)))
            lista.sort(key=lambda x: -x['p'])
            reg.update({'temas': lista, 'validacion': val, 'confianza': confianza(len(ex), val)})
        else:
            reg.update({'temas': [], 'validacion': None, 'confianza': 'sin_temario'})
        out['ccaa'].setdefault(cid, {'nombre': fuentes['ccaa'][cid]['nombre'], 'materias': {}})['materias'][mid] = reg
        # contexto para los generadores (pipeline y app con clave): formato real + cómo se ha preguntado cada tema
        recientes = sorted(ex, key=lambda e: (e['anio'], e['conv'] == 'ord'), reverse=True)[:2]
        ctx = {'ccaa': cid, 'materia': mid, 'generado': out['generado'],
               'formato': [{'anio': e['anio'], 'conv': e['conv'], 'url': e['url'], 'texto': e['txt'][:6000]} for e in recientes],
               'temas': {t['id']: ejemplos([e for e in ex if e['hits'].get(t['id'], 0) >= UMBRAL], t) for t in temas}}
        (R / 'data' / 'contexto').mkdir(parents=True, exist_ok=True)
        (R / 'data' / 'contexto' / f'{cid}__{mid}.json').write_text(json.dumps(ctx, ensure_ascii=False, indent=0), encoding='utf-8')
    for mid, ts in acum.items():
        nombres = {t['id']: t['nombre'] for t in temario[mid]['temas']}
        out['nacional'][mid] = sorted(({'id': tid, 'nombre': nombres[tid], 'p': round(sum(p * n for p, n in v) / sum(n for _, n in v), 3), 'ccaa': len(v)} for tid, v in ts.items()), key=lambda x: -x['p'])
    for cid, c in out['ccaa'].items():
        vs = [m['validacion']['tasa'] for m in c['materias'].values() if m.get('validacion')]
        c['predecibilidad'] = round(sum(vs) / len(vs), 2) if vs else None
    (R / 'data' / 'predicciones.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'✓ predicciones: {sum(len(c["materias"]) for c in out["ccaa"].values())} combinaciones comunidad × materia')


if __name__ == '__main__':
    main()
