#!/usr/bin/env python3
"""Junta los manifiestos de cada comunidad (data/corpus/<ccaa>.json) en data/corpus.json y data/cobertura.json."""
import hashlib, json, pathlib, re, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from crawl import anio_de, conv_de, norm
from collections import defaultdict

R = pathlib.Path(__file__).resolve().parent.parent


ANIOS = range(2022, 2027)
VARIANTE_RX = re.compile(r'coincidenc|incidenc|reserva|suplente', re.I)
BASURA_RX = re.compile(r'tribunal calificador|acuerdo de \d|acuerdo del tribunal|plantilla definitiva|oposici|tercer ejercicio|lecturas? a2', re.I)
NO_EXAMEN_RX = re.compile(r'\bhorarios?\b|calendario|comisi[oó]n organizadora|\binstrucciones\b|resoluci[oó]n rectoral|\bacuerdo de \d', re.I)


def corrige(d):
    """Reglas comunes a todas las comunidades (se aplican al unir, sin volver a rastrear).
    1) Si el texto del enlace dice un curso o año, ese manda; fuera de 2022-2026 el documento sale.
    2) «Coincidencias»/«incidencias» se marcan como variante del examen de su convocatoria.
    3) La convocatoria sale del enlace o del nombre del fichero y, si no lo dicen, de la cabecera del PDF;
       el título de la página («junio y julio») ya no decide.
    4) Fuera los documentos sin materia que son acuerdos de tribunales u oposiciones.
    Devuelve None si el documento sale."""
    enl = (d.get('enlace') or '')
    fich = re.sub(r'[?#].*$', '', d.get('url', '')).rsplit('/', 1)[-1]
    if not d.get('materia') and BASURA_RX.search(enl + ' ' + fich): return None
    if NO_EXAMEN_RX.search(enl): return None                       # horarios, calendarios, acuerdos con materia por error
    a = anio_de(enl, anios=range(2000, 2040))
    if a:
        if a not in ANIOS: return None
        d['anio'] = a
    if VARIANTE_RX.search(enl + ' ' + fich): d['variante'] = 'coincidencia'
    if d.get('tipo') == 'examen':
        c = conv_de(enl, fich.replace('_', ' ').replace('-', ' '))
        if c in ('nd', 'modelo') or (re.search(r'extraordinari', norm(enl)) and re.search(r'(?<!extra)ordinari', norm(enl))):
            try: cab = re.sub(r'\s+', ' ', (R / d['txt']).read_text(encoding='utf-8', errors='ignore')[:20000])[:1500]
            except (OSError, KeyError): cab = ''
            c2 = conv_de(cab) if cab else 'nd'
            ambas = re.search(r'extraordinari', norm(cab)) and re.search(r'(?<!extra)ordinari', norm(cab))
            if c2 in ('ord', 'ext') and not ambas: c = c2
            elif c == 'nd' and re.search(r'modelo de examen|examen modelo|modelo orientativo|modelo de prueba', norm(cab)): c = 'modelo'
        ctxn = norm(d.get('contexto') or '')
        ctx_ambiguo = bool(re.search(r'extraordinari|julio', ctxn) and re.search(r'(?<!extra)ordinari|junio', ctxn))
        if c == 'nd' and not ctx_ambiguo:   # solo si el contexto nombra UNA convocatoria («junio y julio» no decide)
            for seg in (d.get('contexto') or '').split('·'):
                n = norm(seg)
                if re.search(r'extraordinari|julio', n) and re.search(r'(?<!extra)ordinari|junio', n): continue
                c3 = conv_de(seg)
                if c3 == 'modelo' and a: continue   # «Alemán 2022-2023» bajo «Modelos de examen»: es un examen pasado
                if c3 != 'nd': c = c3; break
        if c == 'nd':   # lo que dijo el rastreo (carpeta «Junio», ruta…), salvo que viniera de un contexto con las dos
            c = 'nd' if ctx_ambiguo else d.get('conv', 'nd')
        d['conv'] = c
    return d


def huella_texto(d):
    """Mismo PDF publicado con dos direcciones (CiUG: /PDF/2025/… y /link/…): mismo texto, salvo espacios."""
    try: t = (R / d['txt']).read_text(encoding='utf-8', errors='ignore')
    except (OSError, KeyError): return None
    t = re.sub(r'\s+', ' ', t).strip()
    return hashlib.sha1(t.encode()).hexdigest() if len(t) >= 200 else None


def palabras(d):
    try: t = (R / d['txt']).read_text(encoding='utf-8', errors='ignore')
    except (OSError, KeyError): return set()
    w = re.findall(r'[a-záéíóúñüçàèòïl·]{4,}', t.lower()[:6000])
    return {' '.join(w[i:i + 3]) for i in range(0, max(0, len(w) - 2))}


def casi_duplicados(docs):
    """El mismo examen publicado por varias universidades (Madrid: UCM, UAM, UC3M…) con texto casi igual
    pero no idéntico: dentro de la misma comunidad, materia y año, si comparten
    ≥ 80 % de los trigramas de palabras (Jaccard), se queda uno."""
    grupos = defaultdict(list)
    for d in docs:
        if d.get('tipo') == 'examen' and d.get('materia') and d.get('chars', 0) >= 200:
            grupos[(d['ccaa'], d['materia'], d['anio'])].append(d)
    fuera = set()
    for g in grupos.values():
        if len(g) < 2: continue
        g.sort(key=lambda d: (d.get('conv') not in ('ord', 'ext'), bool(d.get('variante'))))   # se queda el de convocatoria conocida
        sets = [(d, palabras(d)) for d in g]
        guard = []
        for d, w in sets:
            if w and any(len(w & w2) / max(1, len(w | w2)) >= 0.8 for _, w2 in guard): fuera.add(id(d)); continue
            guard.append((d, w))
    return [d for d in docs if id(d) not in fuera], len(fuera)


def sin_duplicados(docs):
    """Quita los documentos de una comunidad con el mismo texto que otro ya visto (se queda el primero, con URL directa si la hay)."""
    vistos, fuera = set(), 0
    orden = sorted(docs, key=lambda d: ('/link/' in d.get('url', ''), d.get('url', '')))
    quedan = []
    for d in orden:
        h = huella_texto(d) if d.get('chars', 0) >= 200 else None
        if h and (d['ccaa'], h) in vistos: fuera += 1; continue
        if h: vistos.add((d['ccaa'], h))
        quedan.append(d)
    return quedan, fuera


def main():
    docs, estado = [], {}
    for f in sorted((R / 'data' / 'corpus').glob('*.json')):
        m = json.loads(f.read_text(encoding='utf-8'))
        docs += m['documentos']; estado[m['ccaa']] = {'actualizado': m['generado'], 'documentos': m['n']}
    antes = len(docs); docs = [x for x in (corrige(d) for d in docs) if x]; fuera_reglas = antes - len(docs)
    docs, repes = sin_duplicados(docs)
    docs, casi = casi_duplicados(docs); repes += casi
    docs.sort(key=lambda d: (d['ccaa'], d['materia'] or '~', d['anio'], d['conv'], d['tipo']))
    (R / 'data' / 'corpus.json').write_text(json.dumps({'generado': time.strftime('%Y-%m-%d'), 'n': len(docs), 'ccaa': estado, 'documentos': docs}, ensure_ascii=False, indent=1), encoding='utf-8')
    cob = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for d in docs:
        if d['tipo'] == 'examen' and d['materia'] and d.get('chars', 0) >= 200: cob[d['ccaa']][d['materia']][str(d['anio'])] += 1
    (R / 'data' / 'cobertura.json').write_text(json.dumps(cob, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print(f'✓ {len(docs)} documentos de {len(estado)} comunidades ({repes} duplicados y {fuera_reglas} fuera de curso o basura)')
    for c, e in estado.items():
        n = sum(sum(v.values()) for v in cob.get(c, {}).values())
        print(f'  {c:18} {e["documentos"]:4} documentos · {n:4} exámenes con texto · {len(cob.get(c, {}))} materias')


if __name__ == '__main__':
    main()
