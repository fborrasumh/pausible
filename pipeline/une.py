#!/usr/bin/env python3
"""Junta los manifiestos de cada comunidad (data/corpus/<ccaa>.json) en data/corpus.json y data/cobertura.json."""
import json, pathlib, time
from collections import defaultdict

R = pathlib.Path(__file__).resolve().parent.parent


def main():
    docs, estado = [], {}
    for f in sorted((R / 'data' / 'corpus').glob('*.json')):
        m = json.loads(f.read_text(encoding='utf-8'))
        docs += m['documentos']; estado[m['ccaa']] = {'actualizado': m['generado'], 'documentos': m['n']}
    docs.sort(key=lambda d: (d['ccaa'], d['materia'] or '~', d['anio'], d['conv'], d['tipo']))
    (R / 'data' / 'corpus.json').write_text(json.dumps({'generado': time.strftime('%Y-%m-%d'), 'n': len(docs), 'ccaa': estado, 'documentos': docs}, ensure_ascii=False, indent=1), encoding='utf-8')
    cob = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for d in docs:
        if d['tipo'] == 'examen' and d['materia'] and d.get('chars', 0) >= 200: cob[d['ccaa']][d['materia']][str(d['anio'])] += 1
    (R / 'data' / 'cobertura.json').write_text(json.dumps(cob, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print(f'✓ {len(docs)} documentos de {len(estado)} comunidades')
    for c, e in estado.items():
        n = sum(sum(v.values()) for v in cob.get(c, {}).values())
        print(f'  {c:18} {e["documentos"]:4} documentos · {n:4} exámenes con texto · {len(cob.get(c, {}))} materias')


if __name__ == '__main__':
    main()
