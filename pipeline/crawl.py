#!/usr/bin/env python3
"""Rastrea las páginas oficiales de cada comunidad (fuentes.json), localiza los PDF de exámenes y criterios
de la PAU 2022-2026, los descarga, extrae su texto y escribe el manifiesto del corpus.

Pensado para ejecutarse en GitHub Actions (allí hay acceso a las webs de las universidades):
  python3 pipeline/crawl.py --ccaa madrid --tiempo 2280   # una comunidad, como máximo 38 min (lo que usa el Action)
  python3 pipeline/crawl.py                                # todas, una tras otra (lento)
  python3 pipeline/crawl.py --sin-descarga                 # solo localiza enlaces (para depurar fuentes)

Salidas:
  corpus/<ccaa>/<materia>/<anio>_<conv>_<tipo>_<h8>.txt   texto extraído (se sube al repo)
  pdf/<ccaa>/<materia>/…pdf                               PDF originales (NO se suben al repo: van a una Release)
  data/corpus/<ccaa>.json manifiesto de esa comunidad: un registro por documento, con su URL oficial
  data/logs/<ccaa>.log    qué se visitó y qué falló
(pipeline/une.py junta los manifiestos en data/corpus.json y data/cobertura.json)

Con --tiempo, el rastreo de páginas usa como mucho el 40 % del tiempo y las descargas el resto; al agotarse,
se guarda lo conseguido (el manifiesto se escribe también cada 10 descargas, por si el proceso muere antes).
"""
import argparse, hashlib, html, json, pathlib, re, subprocess, sys, time, unicodedata
from collections import defaultdict, deque
from urllib.parse import urljoin, urlparse, unquote

R = pathlib.Path(__file__).resolve().parent.parent
UA = 'PAUsible/1.0 (+https://github.com/fborrasumh/pausible; recopilacion de examenes PAU publicos)'


def norm(s):
    """minúsculas, sin tildes, separadores como espacio: para comparar patrones"""
    s = unicodedata.normalize('NFKD', unquote(str(s))).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[_\-/\.%+]+', ' ', s)


TEMARIO = json.loads((R / 'pipeline' / 'temario.json').read_text(encoding='utf-8'))
PATRONES = sorted(((norm(p).strip(), m['id']) for m in TEMARIO['materias'] for p in m['patrones']), key=lambda x: -len(x[0]))


# Abreviaturas que usan algunas comunidades en el nombre del fichero (Comunitat Valenciana, Cataluña…).
# Solo cuentan como palabra entera del NOMBRE DEL FICHERO o del texto del enlace, y solo si no hay nombre completo.
ABREV = {
    'hfil': 'filosofia', 'fil': 'filosofia', 'hes': 'historia', 'his': 'historia', 'hist': 'historia', 'hesp': 'historia',
    'mat': 'matematicas2', 'mat2': 'matematicas2', 'mate': 'matematicas2', 'mcs': 'matccss', 'macs': 'matccss', 'mccss': 'matccss', 'maca': 'matccss',
    'qui': 'quimica', 'quim': 'quimica', 'fis': 'fisica', 'fisi': 'fisica', 'bio': 'biologia', 'biol': 'biologia',
    'geo': 'geografia', 'geog': 'geografia', 'gca': 'geologia', 'geol': 'geologia', 'ctm': 'geologia',
    'cas': 'lengua', 'cast': 'lengua', 'lcl': 'lengua', 'val': 'valenciano', 'cat': 'catalan', 'llca': 'catalan',
    'ang': 'ingles', 'angl': 'ingles', 'ing': 'ingles', 'fra': 'frances', 'fran': 'frances', 'ale': 'aleman', 'alem': 'aleman', 'ita': 'italiano', 'ital': 'italiano',
    'lat': 'latin', 'llat': 'latin', 'gri': 'griego', 'grec': 'griego', 'gre': 'griego',
    'dt': 'dibujo', 'dt2': 'dibujo', 'dib': 'dibujo', 'dibu': 'dibujo', 'da': 'dibujoartistico', 'diar': 'dibujoartistico',
    'emp': 'empresa', 'edmn': 'empresa', 'femp': 'empresa', 'hart': 'historiaarte', 'har': 'historiaarte', 'fart': 'historiaarte',
    'tec': 'tecnologia', 'tecn': 'tecnologia', 'tin': 'tecnologia', 'dis': 'diseno', 'diss': 'diseno',
    'amus': 'musica', 'anm': 'musica', 'hmus': 'musica', 'cau': 'audiovisual', 'aesc': 'escenicas', 'ae': 'escenicas', 'lidr': 'literaturadram',
    'cien': 'ciencias', 'cg': 'ciencias', 'mg': 'matgenerales', 'mcult': 'movimientos', 'mca': 'movimientos'}
# Pruebas que no son la PAU de bachillerato (mayores de 25/45, PAP de Cataluña…): se descartan
NO_PAU = re.compile(r'mayores (de )?(25|45)|majors (de )?(25|45)|maiores (de )?(25|45)|\bm25\b|\bm45\b|\bpap\b|\b25 anos\b|prova d.acces per a majors|ciclos? formativos? de grado medio')


def fichero_de(url):
    """Nombre útil del fichero. En Liferay (/documents/…/NOMBRE.pdf/UUID?t=…) el último segmento es un UUID."""
    partes = [x for x in urlparse(url).path.split('/') if x]
    for x in reversed(partes):
        if '.pdf' in x.lower(): return x
    for x in reversed(partes):
        if not re.fullmatch(r'[0-9a-f-]{20,}|\d+', x.lower()): return x
    return partes[-1] if partes else ''


def materia_abrev(*textos):
    for t in textos:
        for tok in re.findall(r'[a-z0-9]+', norm(t)):
            if tok in ABREV: return ABREV[tok]
    return None


def materia_de(*textos):
    """El patrón más largo que aparece gana (así «historia del arte» no se confunde con «historia»).
    Se prueban los textos por orden de fiabilidad: nombre del fichero y texto del enlace antes que el contexto."""
    for t in textos:
        n = ' ' + norm(t) + ' '
        for p, mid in PATRONES:
            if re.search(r'(?<![a-z])' + re.escape(p) + r'(?![a-z])', n):
                return mid
    return None


def anio_de(*textos, anios=range(2022, 2027)):
    """Año de la convocatoria. «2024-2025» o «2024/25» → 2025 (año en que se hace la prueba)."""
    for t in textos:
        n = unquote(str(t))
        m = re.search(r'(20[12]\d)\s*[-/_]\s*(20)?([12]\d)(?!\d)', n)
        if m:
            a = int('20' + m.group(3))
            if a in anios: return a
        for y in re.findall(r'(?<!\d)(20[12]\d)(?!\d)', n):
            if int(y) in anios: return int(y)
    return None


def conv_de(*textos):
    n = ' '.join(norm(t) for t in textos)
    if re.search(r'extraordinari|julio|juliol|xullo|septiembre|setembre|uztail|irail|\bextra\b|\bext\b|\bjul\b|\bsep\b', n): return 'ext'
    if re.search(r'ordinari|junio|juny|xuno|ekain|\bord\b|\bjun\b', n): return 'ord'
    if re.search(r'model|orientativ|exemple|ejemplo|muestra|prova de mostra|proba', n): return 'modelo'
    return 'nd'


def tipo_de(*textos):
    n = ' '.join(norm(t) for t in textos)
    crit = re.search(r'criteri|solucion|soluci|correcci|corregid|resuelt|resolt|zuzen|respuesta|barem', n)
    # «Examen y criterios», «Examen i correcció», «examen resuelto»: el PDF trae el examen → cuenta como examen
    if crit and re.search(r'examen|exame|exercici|ejercicio|azterketa|prova|prueba', n) and not re.search(r'^\s*criteri', n): return 'examen'
    if crit: return 'criterios'
    if re.search(r'orientacion|orientacio|estructura|caracteristic|instruccion|programa|temario', n): return 'orientaciones'
    return 'examen'


ENLACE_INTERES = re.compile(r'exam|model|pau|ebau|evau|pevau|pbau|abau|selectiv|convocator|anterior|materia|matèri|criteri|prueba|prova|proba|20(2[1-6])|asignatur|ejercici|exercici|enunciat', re.I)


class Rastreador:
    def __init__(self, sesion, cfg, log, limite=float('inf'), silencio_404=False):
        self.s, self.cfg, self.log, self.limite = sesion, cfg, log, limite

    def get(self, url, silencio=False):
        for intento in range(2):
            try:
                r = self.s.get(url, timeout=(self.cfg.get('timeout', 8), 25), headers={'User-Agent': UA}, allow_redirects=True)
                if r.status_code == 200: return r
                if not (silencio and r.status_code == 404): self.log(f'  {r.status_code} {url}')
                if r.status_code in (403, 404, 410): return None
                if r.status_code == 429:                     # nos piden ir más despacio: se respeta
                    ra = r.headers.get('Retry-After', '')
                    time.sleep(min(30, int(ra)) if ra.isdigit() else 15); continue
            except Exception as e:
                self.log(f'  error {type(e).__name__} {url}')
            time.sleep(1)
        return None

    def pdfs(self, semillas):
        """BFS por el mismo dominio. Devuelve {url_pdf: {'texto':…, 'contexto':…, 'pagina':…}}"""
        dominios = {'.'.join(urlparse(u).hostname.split('.')[-2:]) for u in semillas}
        visto, cola, encontrados, meta = set(), deque((u, 0) for u in semillas), {}, {}
        while cola and len(visto) < self.cfg['max_paginas']:
            if time.time() > self.limite:
                self.log('  tiempo de rastreo agotado: se sigue con lo encontrado'); break
            url, d = cola.popleft()
            if url in visto: continue
            visto.add(url)
            r = self.get(url)
            if not r: continue
            ct = r.headers.get('content-type', '')
            if 'pdf' in ct:
                encontrados.setdefault(url, meta.get(url, {'texto': '', 'contexto': '', 'pagina': url})); continue
            if 'html' not in ct and 'xml' not in ct: continue
            mt = re.search(r'<title[^>]*>(.*?)</title>', r.text, re.I | re.S)
            titulo = limpio(mt.group(1))[:200] if mt else ''
            for href, texto, ctx in enlaces(r.text):
                u = urljoin(r.url, href).split('#')[0]
                if not u.startswith('http'): continue
                host = urlparse(u).hostname or ''
                if '.'.join(host.split('.')[-2:]) not in dominios: continue
                info = {'texto': texto, 'contexto': ctx, 'pagina': r.url, 'titulo': titulo}
                if es_pdf(u):
                    encontrados.setdefault(u, info)
                elif d < self.cfg['profundidad'] and ENLACE_INTERES.search(u + ' ' + texto) and u not in visto:
                    meta.setdefault(u, info)             # por si resulta ser un PDF sin «.pdf» en la URL
                    cola.append((u, d + 1))
            time.sleep(self.cfg.get('pausa', 0.2))
        self.log(f'  {len(visto)} páginas visitadas, {len(encontrados)} PDF')
        return encontrados


def es_pdf(u):
    p = urlparse(u).path.lower()
    return p.endswith('.pdf') or '.pdf' in unquote(u.lower()) or '/download' in p and 'pdf' in u.lower()


_A = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_H = re.compile(r'<(h[1-6]|strong|b|th|caption|summary|legend)\b[^>]*>(.*?)</\1>', re.I | re.S)


def limpio(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def enlaces(doc):
    """(href, texto del enlace, contexto) — el contexto son los dos últimos encabezados vistos antes del enlace
    (las webs suelen poner «Matemáticas II» o «Convocatoria ordinaria 2024» en un título y debajo «Examen» / «Criterios»)."""
    cabeceras = [(m.start(), limpio(m.group(2))) for m in _H.finditer(doc)]
    out, j, ultimos = [], 0, []
    for m in _A.finditer(doc):
        while j < len(cabeceras) and cabeceras[j][0] < m.start():
            if cabeceras[j][1]: ultimos = (ultimos + [cabeceras[j][1]])[-3:]
            j += 1
        fila = doc.rfind('<tr', 0, m.start())
        fila_txt = limpio(doc[fila:m.start()])[-160:] if fila != -1 and m.start() - fila < 3000 and '</tr' not in doc[fila:m.start()].lower() and '</table' not in doc[fila:m.start()].lower() else ''
        out.append((html.unescape(m.group(1)), limpio(m.group(2)), ' · '.join(ultimos + ([fila_txt] if fila_txt else []))))
    return out


def texto_pdf(pdf, txt):
    """pdftotext (poppler); si el PDF es una imagen escaneada, OCR con tesseract (spa+cat+glg+eus+eng)."""
    subprocess.run(['pdftotext', '-layout', str(pdf), str(txt)], capture_output=True, timeout=120)
    t = txt.read_text(encoding='utf-8', errors='ignore') if txt.exists() else ''
    if len(t.strip()) < 200 and subprocess.run(['which', 'tesseract'], capture_output=True).returncode == 0:
        tmp = pdf.with_suffix('')
        subprocess.run(['pdftoppm', '-r', '200', '-png', '-l', '6', str(pdf), str(tmp)], capture_output=True, timeout=300)
        partes = []
        for img in sorted(pdf.parent.glob(tmp.name + '-*.png')):
            r = subprocess.run(['tesseract', str(img), '-', '-l', 'spa+cat+glg+eus+eng'], capture_output=True, text=True, timeout=300)
            partes.append(r.stdout); img.unlink()
        t = '\n'.join(partes)
        txt.write_text(t, encoding='utf-8')
    return t


def clasifica(url, info, anios):
    fich = fichero_de(url)
    mat = materia_de(fich, info['texto'], info['contexto']) or materia_abrev(fich, info['texto'])
    anio = anio_de(fich, info['texto'], url, info['contexto'], info.get('titulo', ''), info.get('pagina', ''), anios=anios)
    conv = conv_de(fich, info['texto'], info['contexto'])
    tipo = tipo_de(fich, info['texto'])
    return mat, anio, conv, tipo


def guarda_manifiesto(cid, docs, logl):
    lista = sorted(docs.values(), key=lambda d: (d['materia'] or '~', d['anio'], d['conv'], d['tipo']))
    for sub in ('corpus', 'logs'): (R / 'data' / sub).mkdir(parents=True, exist_ok=True)
    (R / 'data' / 'corpus' / f'{cid}.json').write_text(json.dumps({'ccaa': cid, 'generado': time.strftime('%Y-%m-%d %H:%M'), 'n': len(lista), 'documentos': lista}, ensure_ascii=False, indent=1), encoding='utf-8')
    (R / 'data' / 'logs' / f'{cid}.log').write_text('\n'.join(logl), encoding='utf-8')


def completa_con_texto(d, texto, anios):
    """Si el enlace no decía la materia, la convocatoria o el año, se miran en la cabecera del propio examen
    (Galicia nombra los PDF por código: «20.pdf» = «MATEMÁTICAS II · CÓDIGO 20»)."""
    cab = texto[:1500]
    if not d['materia']: d['materia'] = materia_de(cab)
    if d['conv'] == 'nd': d['conv'] = conv_de(cab)
    if not d.get('anio'): d['anio'] = anio_de(cab, anios=anios)
    if d['tipo'] != 'examen' and re.search(r'examen|exame\b|azterketa', norm(cab[:300])) and not re.search(r'criteri|soluci', norm(cab[:300])): d['tipo'] = 'examen'
    return d


def candidatos_plantilla(pl, anios):
    """Enlaces generados a partir de un patrón conocido (p. ej. Galicia: /PDF/{anio}/PAU/{conv}/exames/{cod}.pdf)."""
    import itertools
    def rango(v):
        if isinstance(v, list): return v
        out = []
        for parte in str(v).split(','):
            a, _, b = parte.partition('-')
            out += [str(i).zfill(len(a)) for i in range(int(a), int(b or a) + 1)]
        return out
    claves = [k for k in pl if k not in ('url', 'anio')]
    for anio in anios:
        for combo in itertools.product(*(rango(pl[k]) for k in claves)):
            yield pl['url'].format(anio=anio, **dict(zip(claves, combo)))


def rastrea(cid, cc, cfg, anios, s, sin_descarga, tiempo):
    t0 = time.time(); fin = t0 + tiempo
    man_p = R / 'data' / 'corpus' / f'{cid}.json'
    previo = {d['url']: d for d in json.loads(man_p.read_text())['documentos']} if man_p.exists() else {}
    docs, logl = dict(previo), []
    log = lambda m: (print(m, flush=True), logl.append(m))
    log(f'== {cc["nombre"]}')
    cfg = {**cfg, **{k: cc[k] for k in ('pausa', 'max_paginas', 'profundidad') if k in cc}}
    encontrados = Rastreador(s, cfg, log, limite=t0 + 0.4 * tiempo).pdfs(cc['semillas'])
    for pl in cc.get('plantillas', []):
        for u in candidatos_plantilla(pl, anios):
            encontrados.setdefault(u, {'texto': '', 'contexto': '', 'pagina': u, 'plantilla': True})
    pend = []
    for url, info in encontrados.items():
        mat, anio, conv, tipo = clasifica(url, info, anios)
        if not anio: continue                           # fuera de 2022-2026 o sin año reconocible
        if NO_PAU.search(norm(' '.join([url, info['texto'], info['contexto']]))):
            docs.pop(url, None); continue              # mayores de 25/45, PAP…: no es la PAU de bachillerato
        h = hashlib.sha1(url.encode()).hexdigest()[:8]
        rel = f'{cid}/{mat or "sin_materia"}/{anio}_{conv}_{tipo}_{h}'
        d = {'id': h, 'ccaa': cid, 'materia': mat, 'anio': anio, 'conv': conv, 'tipo': tipo, 'url': url,
             'pagina': info['pagina'], 'enlace': info['texto'][:160], 'contexto': info['contexto'][:240],
             'txt': f'corpus/{rel}.txt', 'chars': previo.get(url, {}).get('chars', 0)}
        viejo = previo.get(url)
        if viejo and (R / viejo['txt']).exists():      # ya descargado: se conserva el fichero y se reclasifica
            d['txt'], d['chars'] = viejo['txt'], viejo.get('chars', 0)
        if sin_descarga or (R / d['txt']).exists():
            if (R / d['txt']).exists(): completa_con_texto(d, (R / d['txt']).read_text(encoding='utf-8', errors='ignore'), anios)
            docs[url] = d
        else: pend.append((d, rel, info.get('plantilla', False)))
    # primero lo que más importa: exámenes con materia reconocida, de los años más recientes
    pend.sort(key=lambda x: (x[2], x[0]['tipo'] != 'examen', x[0]['materia'] is None, -x[0]['anio']))
    log(f'  {len(pend)} PDF por descargar')
    hechos = 0
    rd = Rastreador(s, cfg, log, silencio_404=True)
    for d, rel, de_plantilla in pend:
        if time.time() > fin:
            log(f'  tiempo agotado: quedan {len(pend) - hechos} PDF para la próxima ejecución'); break
        r = rd.get(d['url'], silencio=de_plantilla)
        if r is not None and r.content[:4] != b'%PDF' and 'download' not in d['url']:
            r = rd.get(d['url'] + ('&' if '?' in d['url'] else '?') + 'download=true', silencio=de_plantilla)   # visor → descarga directa
        hechos += 1
        time.sleep(cfg.get('pausa', 0.2))
        if not (r and r.content[:4] == b'%PDF' and len(r.content) < 25_000_000):
            if not de_plantilla: log(f'  no es un PDF válido: {d["url"]}')
            continue
        pdf = R / 'pdf' / f'{rel}.pdf'; pdf.parent.mkdir(parents=True, exist_ok=True); pdf.write_bytes(r.content)
        txt = R / d['txt']; txt.parent.mkdir(parents=True, exist_ok=True)
        try:
            t = texto_pdf(pdf, txt); d['chars'] = len(t.strip()); completa_con_texto(d, t, anios)
        except Exception as e: log(f'  sin texto ({type(e).__name__}): {d["url"]}'); d['chars'] = 0; t = ''
        if NO_PAU.search(norm(t[:800] if d['chars'] else '')): txt.unlink(missing_ok=True); continue
        d['bytes'] = len(r.content); docs[d['url']] = d
        if hechos % 10 == 0: guarda_manifiesto(cid, docs, logl)
    guarda_manifiesto(cid, docs, logl)
    log(f'✓ {cc["nombre"]}: {len(docs)} documentos en {round((time.time() - t0) / 60)} min')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ccaa', action='append')
    ap.add_argument('--sin-descarga', action='store_true')
    ap.add_argument('--tiempo', type=int, default=2280, help='segundos como máximo por comunidad')
    a = ap.parse_args()
    import requests
    cfg = json.loads((R / 'pipeline' / 'fuentes.json').read_text(encoding='utf-8'))
    anios = range(min(cfg['anios']), max(cfg['anios']) + 1)
    s = requests.Session()
    for cid, cc in cfg['ccaa'].items():
        if a.ccaa and cid not in a.ccaa: continue
        rastrea(cid, cc, cfg, anios, s, a.sin_descarga, a.tiempo)


if __name__ == '__main__':
    main()
