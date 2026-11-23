#!/usr/bin/env python3
"""OCR de los exámenes escaneados de La Rioja (lo mismo que notebooks/ocr_rioja.ipynb, para GitHub Actions).
Lee manual/rioja/escaneados.json, abre las carpetas públicas de SharePoint (permiso de invitado), descarga
cada PDF, lo lee con Tesseract (spa) y escribe manual/rioja/<año>/<Materia> <conv> examen (OCR).txt.
Se puede relanzar: lo ya leído (manual/rioja/ocr_hechos.json) no se repite. Con --tiempo para a tiempo."""
import argparse, json, re, pathlib, subprocess, tempfile, time, requests
R = pathlib.Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument('--tiempo', type=int, default=19000); a = ap.parse_args(); t0 = time.time()
LISTA = json.loads((R / 'manual' / 'rioja' / 'escaneados.json').read_text(encoding='utf-8'))
S = requests.Session(); S.headers['User-Agent'] = 'Mozilla/5.0 (PAUsible; investigacion educativa)'
ok = 0
for c in LISTA['carpetas']:
    try: ok += S.get(c['enlace'], timeout=40, allow_redirects=True).status_code == 200
    except Exception as e: print('  ', c['materia'], e)
    time.sleep(1)
print(ok, 'de', len(LISTA['carpetas']), 'carpetas abiertas', flush=True)
HECHOS = R / 'manual' / 'rioja' / 'ocr_hechos.json'
def nombre_destino(e, texto):
    m = re.search(r'_(jun|jul)\w*_(\d\d)', e['nombre'], re.I)
    if m: anio, conv = 2000 + int(m.group(2)), ('junio' if m.group(1).lower() == 'jun' else 'julio')
    else:   # enlaces sueltos de 2026: año y convocatoria por la cabecera
        cab = re.sub(r'\s+', ' ', texto[:1500]).lower()
        anio = 2026 if re.search(r'2025\s*[-/]\s*(20)?26', cab) else 2026
        conv = 'julio' if re.search(r'extraordinaria|julio', cab) else ('junio' if re.search(r'ordinaria|junio', cab) else '')
    extra = 'incidencias ' if 'incidencia' in e['nombre'].lower() else ''
    nom = re.sub(r'[\\/:*?"<>|]', '', e['materia'])[:60]
    return anio, re.sub(' +', ' ', f'{nom} {conv} {extra}examen (OCR).txt')

def ocr(pdf):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['pdftoppm', '-r', '200', '-gray', '-png', str(pdf), f'{d}/p'], check=True, capture_output=True)
        partes = []
        for img in sorted(pathlib.Path(d).glob('p*.png')):
            partes.append(subprocess.run(['tesseract', str(img), '-', '-l', 'spa', '--psm', '3'], capture_output=True, text=True).stdout)
        return '\n\f\n'.join(partes)

hechos = json.loads(HECHOS.read_text()) if HECHOS.exists() else {}
for i, e in enumerate(LISTA['escaneados'], 1):
    if e['url'] in hechos: continue
    if time.time() - t0 > a.tiempo: print('tiempo agotado: se sigue en la próxima ejecución'); break
    try:
        r = S.get(e['url'], timeout=90)
        if not r.content.startswith(b'%PDF'): print(f'{i:3} ✗ no es PDF ({r.status_code}):', e['materia'], e['nombre']); continue
        pdf = pathlib.Path(tempfile.gettempdir()) / 'ocr_tmp.pdf'; pdf.write_bytes(r.content)
        texto = ocr(pdf)
        anio, fich = nombre_destino(e, texto)
        if anio < 2022: continue
        f = R / 'manual' / 'rioja' / str(anio) / fich; f.parent.mkdir(parents=True, exist_ok=True)
        k = 1
        while f.exists(): k += 1; f = f.with_name(fich.replace('(OCR)', f'(OCR {k})'))
        f.write_text(f"[Fuente: {e['url']} · OCR Tesseract]\n" + texto, encoding='utf-8')
        hechos[e['url']] = str(f.relative_to(R)); HECHOS.write_text(json.dumps(hechos, ensure_ascii=False, indent=0))
        print(f'{i:3} ✓ {len(texto):6} car. ·', f.relative_to(R / 'manual'), flush=True)
    except Exception as ex: print(f'{i:3} ✗', e['materia'], e['nombre'], type(ex).__name__, ex)
    time.sleep(1)
print(len(hechos), 'leídos de', len(LISTA['escaneados']))
