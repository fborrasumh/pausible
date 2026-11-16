#!/usr/bin/env python3
"""Guarda en diag/ la respuesta de cada URL de pipeline/diagnostico.txt (estado, cabeceras, HTML y enlaces)."""
import hashlib, json, pathlib, re, sys, time
import requests
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from crawl import UA, enlaces

R = pathlib.Path(__file__).resolve().parent.parent
out = R / 'diag'; out.mkdir(exist_ok=True)
res = []
for url in [l.strip() for l in (R / 'pipeline' / 'diagnostico.txt').read_text().splitlines() if l.strip() and not l.startswith('#')]:
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    try:
        r = requests.get(url, timeout=(20, 40), headers={'User-Agent': UA}, allow_redirects=True)
        body = r.text[:2_000_000] if 'html' in r.headers.get('content-type', '') or r.status_code != 200 else ''
        (out / f'{h}.html').write_text(body, encoding='utf-8')
        links = [{'href': a, 'texto': t, 'ctx': c[:120]} for a, t, c in enlaces(body)] if body else []
        (out / f'{h}.links.json').write_text(json.dumps(links, ensure_ascii=False, indent=0), encoding='utf-8')
        res.append({'url': url, 'id': h, 'estado': r.status_code, 'final': r.url, 'tipo': r.headers.get('content-type', ''), 'server': r.headers.get('server', ''), 'bytes': len(r.content), 'enlaces': len(links), 'scripts': len(re.findall(r'<script', body, re.I))})
    except Exception as e:
        res.append({'url': url, 'id': h, 'error': f'{type(e).__name__}: {e}'[:300]})
    time.sleep(1)
(out / 'index.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(res, ensure_ascii=False, indent=1))
