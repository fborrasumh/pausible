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
import argparse, hashlib, html, json, os, pathlib, re, subprocess, sys, time, unicodedata, zipfile
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
    'emp': 'empresa', 'edmn': 'empresa', 'femp': 'empresa', 'hart': 'historiaarte', 'har': 'historiaarte', 'fart': 'fundamentosart',
    'tec': 'tecnologia', 'tecn': 'tecnologia', 'tin': 'tecnologia', 'dis': 'diseno', 'diss': 'diseno',
    'amus': 'musica', 'anm': 'musica', 'hmus': 'musica', 'cau': 'audiovisual', 'aesc': 'escenicas', 'ae': 'escenicas', 'lidr': 'literaturadram',
    'cien': 'ciencias', 'cg': 'ciencias', 'mg': 'matgenerales', 'mcult': 'movimientos', 'mca': 'movimientos'}
# Pruebas que no son la PAU de bachillerato (mayores de 25/45, PAP de Cataluña…): se descartan
NO_PAU = re.compile(r'personal investigador|oferta de contractaci|contrato de investigaci|mayores (de )?(25|45)|majors (de )?(25|45)|maiores (de )?(25|45)|\bm25\b|\bm45\b|\bpap\b|\b25 anos\b|prova d.acces per a majors|ciclos? formativos? de grado medio')


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
        m = re.search(r'(?<!\d)(20[12]\d)[\s\u00a0]+(20[12]\d)(?!\d)', n)   # «2022 2023» (carpetas de curso de Liferay)
        if m and int(m.group(2)) == int(m.group(1)) + 1 and int(m.group(2)) in anios: return int(m.group(2))
        for y in re.findall(r'(?<!\d)(20[12]\d)(?!\d)', n):
            if int(y) in anios: return int(y)
    return None


def conv_de(*textos):
    n = ' '.join(norm(t) for t in textos)
    if re.search(r'extraordinari|julio|juliol|xullo|septiembre|setembre|uztail|irail|reserva|suplente|\bextra\b|\bext\b|\bjul\b|\bsep\b', n): return 'ext'
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
                r = self.s.get(url, timeout=(self.cfg.get('timeout', 8), 25), headers={'User-Agent': UA}, allow_redirects=True, stream=True)
                if r.status_code == 200:
                    # tope de tiempo por fichero: un servidor que manda el ZIP a cuentagotas no puede comerse la tarea entera
                    t0, trozos, tope = time.time(), [], self.cfg.get('max_descarga_s', 240)
                    for tr in r.iter_content(1 << 16):
                        trozos.append(tr)
                        if time.time() - t0 > tope:
                            r.close(); self.log(f'  descarga demasiado lenta (>{tope} s, {sum(map(len, trozos)) >> 20} MB): {url}'); return None
                    r._content = b''.join(trozos); return r
                r.content   # lee el cuerpo de las respuestas de error
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
        dominios = {'.'.join(urlparse(u).hostname.split('.')[-2:]) for u in semillas} | set(self.cfg.get('dominios_extra', []))
        visto, cola, encontrados, meta = set(), deque((u, 0, '') for u in semillas), {}, {}
        while cola and len(visto) < self.cfg['max_paginas']:
            if time.time() > self.limite:
                self.log('  tiempo de rastreo agotado: se sigue con lo encontrado'); break
            url, d, ruta = cola.popleft()
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
            mb = re.search(r'<base[^>]+href=["\']([^"\']+)', r.text[:20000], re.I)
            raiz = urljoin(r.url, mb.group(1)) if mb else r.url   # <base href> (CiUG: los enlaces «link/…» cuelgan de la raíz)
            for href, texto, ctx in enlaces(r.text):
                u = urljoin(raiz, href).split('#')[0]
                if not u.startswith('http'): continue
                host = urlparse(u).hostname or ''
                if '.'.join(host.split('.')[-2:]) not in dominios and host != 'drive.google.com': continue
                if host == 'drive.google.com' and not es_pdf(u): continue
                info = {'texto': texto, 'contexto': ctx, 'pagina': r.url, 'titulo': titulo, 'ruta': ruta}
                solo_pdf = bool(re.fullmatch(r'\s*(pdf|descargar( pdf)?|descarga)\s*', texto, re.I))   # CiUG: enlaces «PDF» a /link/…
                if any(x in u for x in self.cfg.get('excluir', [])): continue
                if es_pdf(u) or solo_pdf:
                    if es_gestor(u) and not parece_examen(ctx if solo_pdf else texto, u):
                        continue                         # /file/… o /documents/d/… que no nombra materia ni examen (ayudas, presupuestos…)
                    encontrados.setdefault(u, info)
                elif d < self.cfg['profundidad'] and ENLACE_INTERES.search(u + ' ' + texto) and u not in visto \
                        and (not self.cfg.get('solo_rutas') or any(x in u for x in self.cfg['solo_rutas'])) \
                        and not any(x in u for x in self.cfg.get('excluir', [])):   # Uniovi: no perderse por el menú ni por cursos viejos
                    meta.setdefault(u, info)             # por si resulta ser un PDF sin «.pdf» en la URL
                    cola.append((u, d + 1, (ruta + ' › ' + limpio(texto))[-300:]))
            time.sleep(self.cfg.get('pausa', 0.2))
        self.log(f'  {len(visto)} páginas visitadas, {len(encontrados)} PDF')
        return encontrados


def es_pdf(u):
    """Enlace que probablemente sea un documento: PDF, ZIP (Andalucía) o los gestores sin extensión
    (UCM /file/…, Liferay /documents/d/…, Google Drive /file/d/…). Al descargar se comprueba el contenido."""
    p = urlparse(u).path.lower()
    return (p.endswith('.pdf') or p.endswith('.zip') or '.pdf' in unquote(u.lower()) or '/download' in p and 'pdf' in u.lower()
            or '/file/' in p or '/documents/d/' in p or 'drive.google.com' in u and '/file/d/' in p
            or re.search(r'/documents/\d+/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-', p))   # Liferay por UUID (Uniovi)


def es_gestor(u):
    """Enlace de gestor documental sin extensión (UCM /file/…, Liferay /documents/d/…, Drive)."""
    p = urlparse(u).path.lower()
    return not (p.endswith('.pdf') or p.endswith('.zip') or '.pdf' in unquote(u.lower()))


EXAMEN_RX = re.compile(r'exam|exame|azterketa|criteri|soluci|correcci|zuzen|ejercici|exercici|prueba|prova|proba|\bpau\b|ebau|evau|pevau|pbau|abau|selectiv|model')


def parece_examen(texto, u=''):
    """Solo se descargan los enlaces sin «.pdf» cuyo texto (o nombre) nombra una materia o habla de examen/criterios/PAU."""
    t = texto + ' ' + fichero_de(u)
    return bool(materia_de(t) or EXAMEN_RX.search(norm(t)))   # sin abreviaturas: «cas» o «val» saldrían en cualquier sitio


def descarga_directa(u):
    """Google Drive: de /file/d/ID/view a la descarga del fichero."""
    m = re.search(r'drive\.google\.com/file/d/([\w-]+)', u)
    return f'https://drive.google.com/uc?export=download&id={m.group(1)}' if m else u


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
        subprocess.run(['pdftoppm', '-r', '150', '-png', '-l', '3', str(pdf), str(tmp)], capture_output=True, timeout=120)
        partes = []
        for img in sorted(pdf.parent.glob(tmp.name + '-*.png')):
            try: r = subprocess.run(['tesseract', str(img), '-', '-l', 'spa+cat+glg+eus+eng'], capture_output=True, text=True, timeout=90)
            except subprocess.TimeoutExpired: img.unlink(missing_ok=True); continue
            partes.append(r.stdout); img.unlink()
        t = '\n'.join(partes)
        txt.write_text(t, encoding='utf-8')
    return t


def clasifica(url, info, anios):
    fich = fichero_de(url)
    mat = materia_de(fich, info['texto'], info['contexto']) or materia_abrev(fich, info['texto'])
    anio = anio_de(fich, info['texto'], url, info['contexto'], info.get('titulo', ''), info.get('pagina', ''), info.get('ruta', ''), anios=anios)
    conv = conv_de(fich, info['texto'], info['contexto'])
    if conv == 'nd' and info.get('ruta'):            # carpeta «Junio»/«Julio» más cercana en el camino de enlaces
        conv = next((c for c in (conv_de(x) for x in reversed(info['ruta'].split('›'))) if c != 'nd'), 'nd')
    tipo = tipo_de(fich, info['texto'])
    return mat, anio, conv, tipo


_SUBIDA = {'t': 0.0}
def sube(cid, forzar=False):
    """Con PAUSIBLE_GIT=1 (Actions), sube al repositorio lo reunido de esta comunidad cada 5 min como mucho, y los PDF
    originales nuevos a la Release «corpus»: si la tarea se corta, se pierden como mucho 5 minutos de trabajo."""
    if os.environ.get('PAUSIBLE_GIT') != '1' or (not forzar and time.time() - _SUBIDA['t'] < 300): return
    _SUBIDA['t'] = time.time()
    g = lambda *a: subprocess.run(['git', *a], cwd=R, capture_output=True, text=True)
    try:
        g('add', f'data/corpus/{cid}.json', f'data/logs/{cid}.log')
        if (R / 'corpus' / cid).exists(): g('add', f'corpus/{cid}')
        if g('diff', '--cached', '--quiet').returncode:
            g('commit', '-q', '-m', f'Corpus: {cid} {time.strftime("%Y-%m-%d %H:%M")}')
            for i in range(6):
                if g('push', '-q').returncode == 0: break
                time.sleep(5 + 5 * i); g('pull', '-q', '--rebase', '--autostash')
        pdfs = sorted((R / 'pdf' / cid).rglob('*.pdf')) if (R / 'pdf' / cid).exists() else []
        if pdfs and os.environ.get('GH_TOKEN'):
            z = R / f'pau-{cid}-{time.strftime("%Y-%m-%d-%H%M%S")}.zip'
            with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as f:
                for q in pdfs: f.write(q, q.relative_to(R / 'pdf'))
            if subprocess.run(['gh', 'release', 'upload', 'corpus', str(z), '--clobber'], cwd=R, capture_output=True).returncode == 0:
                for q in pdfs: q.unlink(missing_ok=True)
            z.unlink(missing_ok=True)
    except Exception as e: print(f'  (no se pudo subir: {type(e).__name__}: {e})', flush=True)


def guarda_manifiesto(cid, docs, logl, pendientes=None):
    lista = sorted(docs.values(), key=lambda d: (d['materia'] or '~', d['anio'], d['conv'], d['tipo']))
    for sub in ('corpus', 'logs'): (R / 'data' / sub).mkdir(parents=True, exist_ok=True)
    (R / 'data' / 'corpus' / f'{cid}.json').write_text(json.dumps({'ccaa': cid, 'generado': time.strftime('%Y-%m-%d %H:%M'), 'n': len(lista), **({'pendientes': pendientes} if pendientes is not None else {}), 'documentos': lista}, ensure_ascii=False, indent=1), encoding='utf-8')
    (R / 'data' / 'logs' / f'{cid}.log').write_text('\n'.join(logl), encoding='utf-8')
    sube(cid)


CABECERA_MANDA = {'si': False, 'codigos': {}}
def completa_con_texto(d, texto, anios):
    """Si el enlace no decía la materia, la convocatoria o el año, se miran en la cabecera del propio examen
    (Galicia nombra los PDF por código: «20.pdf» = «MATEMÁTICAS II · CÓDIGO 20»)."""
    cab = re.sub(r'[ \t\u00a0]+', ' ', texto[:20000])[:1500]   # pdftotext -layout mete cientos de espacios
    if CABECERA_MANDA['si'] and EXAMEN_RX.search(norm(cab[:800])):
        mk = re.search(r'c[óo]digo:?\s*(\d{2})\b', cab[:800], re.I)
        mc = CABECERA_MANDA['codigos'].get(mk.group(1)) if mk else None   # CiUG: «CÓDIGO 21» = Bioloxía (el texto puede nombrar otras cosas)
        mc, ac, cc_ = mc or materia_de(cab[:400]), anio_de(cab[:800], anios=anios), conv_de(cab[:800])
        if mc: d['materia'] = mc
        if ac: d['anio'] = ac
        if cc_ != 'nd': d['conv'] = cc_
    if not d['materia'] and EXAMEN_RX.search(norm(cab[:800])): d['materia'] = materia_de(cab)   # solo si la cabecera parece de examen
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


def desde_zip(d, rel, contenido, anios, log, fin=float('inf')):
    """Cada PDF de dentro del ZIP es un documento: hereda materia y año del ZIP; convocatoria y tipo, de su nombre."""
    import io, zipfile
    out = []
    try: z = zipfile.ZipFile(io.BytesIO(contenido))
    except zipfile.BadZipFile: log(f'  ZIP dañado: {d["url"]}'); return out
    for i, nombre in enumerate(n for n in z.namelist() if n.lower().endswith('.pdf')):
        if i >= 40 or time.time() > fin: break
        try: datos = z.read(nombre)
        except Exception: continue
        if datos[:4] != b'%PDF' or NO_PAU.search(norm(nombre)): continue
        dm = dict(d)
        dm['url'] = d['url'] + '#' + nombre
        dm['enlace'] = nombre[:160]
        dm['conv'] = conv_de(nombre) if conv_de(nombre) != 'nd' else d['conv']
        dm['tipo'] = tipo_de(nombre)
        dm['materia'] = d['materia'] or materia_de(nombre) or materia_abrev(nombre)
        h = hashlib.sha1(dm['url'].encode()).hexdigest()[:8]
        relm = f'{rel.rsplit("/", 2)[0]}/{dm["materia"] or "sin_materia"}/{dm["anio"]}_{dm["conv"]}_{dm["tipo"]}_{h}'
        dm['id'], dm['txt'] = h, f'corpus/{relm}.txt'
        pdf = R / 'pdf' / f'{relm}.pdf'; pdf.parent.mkdir(parents=True, exist_ok=True); pdf.write_bytes(datos)
        txt = R / dm['txt']; txt.parent.mkdir(parents=True, exist_ok=True)
        try:
            t = texto_pdf(pdf, txt); dm['chars'] = len(t.strip()); completa_con_texto(dm, t, anios)
        except Exception: dm['chars'] = 0
        dm['bytes'] = len(datos); out.append(dm)
    log(f'  ZIP {fichero_de(d["url"])}: {len(out)} PDF')
    return out


def ingesta_manual(cid, docs, anios, log):
    """PDF o ZIP que alguien ha descargado a mano y subido a manual/<ccaa>/ (para webs que bloquean la descarga
    automática). La materia, el año y la convocatoria salen del nombre del fichero, de su carpeta o de su texto."""
    base = R / 'manual' / cid
    if not base.exists(): return
    n = 0
    for f in sorted(base.rglob('*')):
        if f.suffix.lower() not in ('.pdf', '.zip', '.txt') or not f.is_file() or f.name.upper().startswith('LEEME'): continue
        url = 'manual:' + f.relative_to(R).as_posix()
        if url in docs or any(k.startswith(url + '#') for k in docs): continue
        ruta = f.relative_to(base).as_posix()
        h = hashlib.sha1(url.encode()).hexdigest()[:8]
        d = {'id': h, 'ccaa': cid, 'materia': materia_de(f.name, ruta) or materia_abrev(f.name), 'anio': anio_de(f.name, ruta, anios=anios),
             'conv': conv_de(f.name, ruta), 'tipo': tipo_de(f.name), 'url': url, 'pagina': 'manual', 'enlace': f.name[:160], 'contexto': ruta[:240]}
        if f.suffix.lower() == '.zip':
            if not d['anio']: log(f'  manual sin año reconocible: {ruta}'); continue
            for dz in desde_zip(d, f'{cid}/{d["materia"] or "sin_materia"}/{d["anio"]}_{d["conv"]}_{d["tipo"]}_{h}', f.read_bytes(), anios, log): docs[dz['url']] = dz; n += 1
            continue
        txt = R / 'corpus' / cid / 'manual' / f'{h}.txt'; txt.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix.lower() == '.txt':   # texto ya extraído en el navegador (webs que bloquean a GitHub: UIB)
            t = f.read_text(encoding='utf-8', errors='ignore'); txt.write_text(t, encoding='utf-8')
        else: t = texto_pdf(f, txt)
        d['chars'] = len(t.strip()); completa_con_texto(d, t, anios)
        if not d['anio'] or d['anio'] not in anios or NO_PAU.search(norm(t[:800])): txt.unlink(missing_ok=True); log(f'  manual descartado (año o tipo): {ruta}'); continue
        d['txt'] = txt.relative_to(R).as_posix(); docs[url] = d; n += 1
    log(f'  {n} documentos nuevos subidos a mano (manual/{cid}/)')


def rastrea(cid, cc, cfg, anios, s, sin_descarga, tiempo):
    t0 = time.time(); fin = t0 + tiempo
    man_p = R / 'data' / 'corpus' / f'{cid}.json'
    previo = {d['url']: d for d in json.loads(man_p.read_text())['documentos']} if man_p.exists() else {}
    # se descartan los documentos de gestor (UCM /file/…) ya guardados que no tenían pinta de examen: listados, ayudas…
    previo = {k: v for k, v in previo.items() if k.startswith('manual:') or not es_gestor(k.split('#')[0]) or parece_examen(v.get('enlace', ''), k)}
    previo = {k: v for k, v in previo.items() if not any(x in k for x in cc.get('excluir', []))}   # lo excluido sale también de lo ya guardado
    docs, logl = dict(previo), []
    log = lambda m: (print(m, flush=True), logl.append(m))
    log(f'== {cc["nombre"]}')
    CABECERA_MANDA['si'], CABECERA_MANDA['codigos'] = bool(cc.get('cabecera_manda')), cc.get('codigos_materia', {})
    cfg = {**cfg, **{k: cc[k] for k in ('pausa', 'max_paginas', 'profundidad', 'solo_rutas', 'excluir') if k in cc}}
    encontrados = Rastreador(s, cfg, log, limite=t0 + cc.get('fraccion_rastreo', 0.4) * tiempo).pdfs(cc['semillas'])   # fraccion_rastreo: parte del tiempo para recorrer páginas
    for pl in cc.get('plantillas', []):
        for u in candidatos_plantilla(pl, anios):
            encontrados.setdefault(u, {'texto': '', 'contexto': '', 'pagina': u, 'plantilla': True})
    pend = []
    for url, info in encontrados.items():
        mat, anio, conv, tipo = clasifica(url, info, anios)
        if not anio:
            if not cc.get('cabecera_manda'): continue   # fuera de 2022-2026 o sin año reconocible
            anio = 0                                    # se decide con la cabecera del PDF al descargarlo
        if NO_PAU.search(norm(' '.join([url, info['texto'], info['contexto']]))):
            docs.pop(url, None); continue              # mayores de 25/45, PAP…: no es la PAU de bachillerato
        h = hashlib.sha1(url.encode()).hexdigest()[:8]
        rel = f'{cid}/{mat or "sin_materia"}/{anio}_{conv}_{tipo}_{h}'
        d = {'id': h, 'ccaa': cid, 'materia': mat, 'anio': anio, 'conv': conv, 'tipo': tipo, 'url': url,
             'pagina': info['pagina'], 'enlace': info['texto'][:160], 'contexto': info['contexto'][:240],
             'txt': f'corpus/{rel}.txt', 'chars': previo.get(url, {}).get('chars', 0)}
        if any(k.startswith(url + '#') for k in previo):    # ZIP ya procesado: se conservan sus PDF
            for k, v in previo.items():
                if k.startswith(url + '#'): docs[k] = v
            continue
        viejo = previo.get(url)
        if viejo and (R / viejo['txt']).exists():      # ya descargado: se conserva el fichero y se reclasifica
            d['txt'], d['chars'] = viejo['txt'], viejo.get('chars', 0)
        if sin_descarga or (R / d['txt']).exists():
            if (R / d['txt']).exists():
                t = (R / d['txt']).read_text(encoding='utf-8', errors='ignore')
                d['chars'] = max(d.get('chars') or 0, len(t.strip()))   # el texto ya está: que cuente aunque el manifiesto dijera 0
                completa_con_texto(d, t, anios)
            if d['anio'] in anios: docs[url] = d
        else: pend.append((d, rel, info.get('plantilla', False)))
    # primero lo que más importa: exámenes con materia reconocida, de los años más recientes
    pend.sort(key=lambda x: (x[2], x[0]['tipo'] != 'examen', x[0]['materia'] is None, -x[0]['anio']))
    log(f'  {len(pend)} PDF por descargar')
    hechos = 0
    quedan = lambda: sum(1 for x in pend[hechos:] if not x[2])   # lo que falta (sin contar las URL de plantilla, que casi siempre dan 404)
    rd = Rastreador(s, cfg, log, silencio_404=True)
    for d, rel, de_plantilla in pend:
        if time.time() > fin:
            log(f'  tiempo agotado: quedan {len(pend) - hechos} PDF para la próxima ejecución'); break
        if not de_plantilla: print(f'  ↓ {d["url"]}', flush=True)   # solo a la consola de Actions: si algo se atasca, se ve dónde
        r = rd.get(descarga_directa(d['url']), silencio=de_plantilla)
        if r is not None and r.content[:2] == b'PK':        # ZIP (Andalucía: un zip por materia y año con todos sus exámenes)
            hechos += 1; time.sleep(cfg.get('pausa', 0.2))
            for dz in desde_zip(d, rel, r.content, anios, log, fin): docs[dz['url']] = dz
            guarda_manifiesto(cid, docs, logl, quedan())  # un ZIP puede traer 15 PDF: se guarda tras cada uno
            continue
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
        if d['anio'] not in anios: txt.unlink(missing_ok=True); pdf.unlink(missing_ok=True); continue   # la cabecera dice otro curso
        d['bytes'] = len(r.content); docs[d['url']] = d
        if hechos % 10 == 0: guarda_manifiesto(cid, docs, logl, quedan())
    try: ingesta_manual(cid, docs, anios, log)
    except Exception as e: log(f'  error en manual/{cid}: {type(e).__name__}: {e}')
    guarda_manifiesto(cid, docs, logl, quedan()); sube(cid, forzar=True)
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
