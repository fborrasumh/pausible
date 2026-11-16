"""Prueba de extremo a extremo de PAUsible en Chromium (Playwright), con datos sintéticos servidos por HTTP y la IA simulada.
Uso: python3 tests/e2e_test.py /ruta/al/sitio   (carpeta con index.html y data/)"""
import asyncio, http.server, json, re, sys, threading, functools, pathlib
from playwright.async_api import async_playwright
SITE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
OUT = pathlib.Path('/tmp/e2e/shots'); OUT.mkdir(parents=True, exist_ok=True)

def sirve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s

import itertools
RESOL = {'A': itertools.cycle([[9], [6]]), 'B': itertools.cycle([[9], [7]]), 'C': itertools.cycle([[8]])}
PONENTE = []
def ia(user):
    if 'Redacta un examen ORIGINAL' in user:
        PONENTE.append(user)
        return {'titulo': 'Mates II · probable', 'duracion_min': 90, 'instrucciones': 'Responde.', 'preguntas': [
            {'n': '1', 'tema': 'integrales', 'puntos': 5, 'tipo': 'calculo', 'enunciado': 'Calcula $\\int_0^3 2x\\,dx$.'},
            {'n': '2', 'tema': 'derivadas', 'puntos': 5, 'tipo': 'calculo', 'enunciado': 'Pregunta ambigua.'}]}
    if 'Resuelve esta pregunta' in user:
        k = 'C' if 'cuidadoso' in user else 'B' if 'método distinto' in user else 'A'
        n = next(RESOL[k]); return {'solucion': f'= {n[0]}', 'resultado': str(n[0]), 'numeros': n, 'claves': [], 'criterios': 'todo o nada'}
    raise AssertionError(user[:80])

async def main():
    srv = sirve(); base = f'http://127.0.0.1:{srv.server_port}/'
    errores = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1360, 'height': 900}, bypass_csp=True)
        async def api(route):
            body = json.loads(route.request.post_data); user = body['messages'][-1]['content']
            await route.fulfill(status=200, content_type='application/json', body=json.dumps({'choices': [{'message': {'content': json.dumps(ia(user))}}]}))
        await ctx.route('https://api.openai.com/**', api)
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errores.append(str(e))); pg.on('console', lambda m: m.type == 'error' and errores.append(m.text))
        await pg.goto(base); await pg.wait_for_function('DATOS.cargado')
        assert 'Corpus: 6' in await pg.inner_text('#estadoDatos'), await pg.inner_text('#estadoDatos')
        faltan = await pg.evaluate('i18nFaltan()'); assert faltan == [], faltan
        await pg.screenshot(path=OUT / '0_inicio.png', full_page=True)
        # 1) ejemplo sin clave
        await pg.click('#btnEjemplo'); await pg.wait_for_selector('.pa-tema')
        assert await pg.locator('.pa-tema').count() == 7
        await pg.click('#navNext'); await pg.wait_for_selector('.pa-preg')
        assert await pg.locator('.pa-preg').count() == 5
        for i, v in enumerate([2, 2, 1.5, 2, 1]): await pg.fill(f'#auto{i}', str(v))
        assert '8,5' in await pg.inner_text('#exNota'), await pg.inner_text('#exNota')
        await pg.locator('.pa-sol summary').first.click(); await pg.screenshot(path=OUT / '3_examen_ejemplo.png', full_page=True)
        await pg.click('#btnACompartir'); await pg.wait_for_timeout(300)
        blanco = await pg.evaluate("(()=>{const c=$('cvTarjeta');const d=c.getContext('2d').getImageData(540,800,1,1).data;return c.width===1080&&d[3]>0})()"); assert blanco
        wa = await pg.get_attribute('#btnWa', 'href'); assert 'wa.me' in wa and '8%2C5' in wa, wa
        await pg.screenshot(path=OUT / '4_comparte.png', full_page=True)
        # 2) datos reales: Madrid · Matemáticas II, con examen ya generado
        await pg.click('#goHome'); await pg.click('#btnStart')
        await pg.click('[data-c="madrid"]'); await pg.select_option('#selMat', 'matematicas2')
        assert 'Faltan' in await pg.inner_text('#cuenta')
        await pg.click('#navNext'); await pg.wait_for_selector('.pa-tema')
        assert 'Ocultamos el examen de 2026' in await pg.inner_text('#predValid')
        assert 'en España' in await pg.inner_text('#predTemas')
        await pg.screenshot(path=OUT / '2_prediccion.png', full_page=True)
        await pg.click('#navNext'); await pg.wait_for_selector('.pa-preg')
        # fórmulas: KaTeX dentro del HTML, sin LaTeX en crudo ni errores (\( \), $$, \[ \], \ce, \binom…)
        for s_ in await pg.query_selector_all('.pa-sol'): await s_.evaluate('e => e.open = true')
        assert await pg.evaluate("document.querySelectorAll('#exPreg .katex').length") > 5
        assert await pg.evaluate("document.querySelectorAll('#exPreg .katex-error').length") == 0
        crudo = await pg.inner_text('#exPreg'); assert not [w for w in ['\\(', '\\binom', '\\ce', '{,}', '$$', '\\['] if w in crudo], crudo[:300]
        # 3) generar con clave (Comunitat Valenciana no tiene examen): la pregunta en la que nadie coincide se descarta
        await pg.evaluate("localStorage.setItem(PROV.openai.k,'sk-proj-prueba-0000000000000000')")
        await pg.click('#goHome'); await pg.click('#btnStart'); await pg.click('[data-c="valenciana"]'); await pg.select_option('#selMat', 'matematicas2')
        await pg.click('#navNext'); await pg.click('#navNext'); await pg.click('#btnGenera')
        await pg.wait_for_selector('.pa-preg', timeout=15000)
        assert await pg.locator('.pa-preg').count() == 1 and 'Se descartaron 1' in await pg.inner_text('#exCab')
        # el ponente recibe las preguntas reales de años anteriores de esa comunidad y materia
        assert 'ASÍ SE HA PREGUNTADO CADA TEMA' in PONENTE[-1] and 'EXAMEN REAL' in PONENTE[-1] and 'NO las copies' in PONENTE[-1], PONENTE[-1][-400:]
        assert await pg.evaluate("document.querySelectorAll('.pa-enun .katex').length") > 0    # fórmula del enunciado con KaTeX
        # historial: un segundo examen con la clave → «Mío 1» y «Mío 2»
        await pg.click('#btnGeneraOtro'); await pg.wait_for_function("document.querySelectorAll('[data-fuente]').length >= 2", timeout=15000)
        assert await pg.locator('[data-fuente^="bib:"]').count() == 2
        # reto con examen propio: viaja comprimido en el #fragmento y el amigo recibe exactamente el mismo
        await pg.fill('#auto0', '4'); await pg.click('#btnACompartir'); await pg.wait_for_function('LINK.length > 0')
        link = await pg.evaluate('LINK'); assert '#e=z' in link and len(link) < 6000, link[:120]
        enun = await pg.evaluate("examenActual().preguntas.map(p => p.enunciado)")
        async with pg.expect_download() as dlinfo: await pg.click('#btnExJson')
        fich = await (await dlinfo.value).path()
        amigo = await ctx.new_page(); amigo.on('pageerror', lambda e: errores.append(str(e)))
        await amigo.goto(link.replace('https://fborrasumh.github.io/pausible/', base)); await amigo.wait_for_function('DATOS.cargado')
        assert '8' in await amigo.inner_text('#retoBanner')
        await amigo.click('#btnReto'); await amigo.wait_for_selector('.pa-preg')
        assert 'Generado con la clave de quien te reta' in await amigo.inner_text('#exCab')
        assert await amigo.evaluate("examenActual().preguntas.map(p => p.enunciado)") == enun
        assert '#' not in amigo.url                                   # el examen no se queda en la barra de direcciones
        # y como fichero, por si el enlace se corta
        otro = await ctx.new_page(); await otro.goto(base); await otro.wait_for_function('DATOS.cargado')
        await otro.set_input_files('#fichReto', fich); await otro.wait_for_selector('.pa-preg')
        assert await otro.evaluate("examenActual().preguntas.map(p => p.enunciado)") == enun
        # «Mis exámenes»: el amigo tiene el reto guardado con la nota de quien le retó, y el intento se registra al corregirse
        await amigo.fill('#auto0', '3'); await amigo.wait_for_timeout(700)
        await amigo.click('#goHome'); await amigo.click('#btnBib'); await amigo.wait_for_selector('.pa-bib')
        txtb = await amigo.inner_text('#bibLista'); assert 'Reto recibido' in txtb and '1 intentos' in txtb and 'nota de quien te retó: 8' in txtb, txtb
        # yo: dos exámenes generados, exportar → borrar uno → importar lo recupera sin duplicar
        # (mismo contexto de navegador = misma base: aquí también están los retos del amigo)
        await pg.click('#goHome'); await pg.click('#btnBib'); await pg.wait_for_selector('.pa-bib')
        await pg.evaluate('recargaBib().then(pintaBiblioteca)')
        n = await pg.locator('.pa-bib').count(); assert n >= 2 and n == await pg.evaluate('MEM.bib.length')
        await pg.select_option('#bibOrig', 'propio'); assert await pg.locator('.pa-bib').count() == 2; await pg.select_option('#bibOrig', '')
        async with pg.expect_download() as d2: await pg.click('#btnBibExp')
        copia = await (await d2.value).path()
        borrar = pg.locator('[data-borrar]').first; await borrar.click(); await borrar.click(); await pg.wait_for_timeout(300)
        assert await pg.locator('.pa-bib').count() == n - 1
        await pg.set_input_files('#fichBib', copia); await pg.wait_for_timeout(500)
        assert await pg.locator('.pa-bib').count() == n
        await pg.set_input_files('#fichBib', copia); await pg.wait_for_timeout(500)
        assert await pg.locator('.pa-bib').count() == n                       # importar dos veces no duplica
        await pg.select_option('#bibOrig', 'propio')
        await pg.locator('[data-abrir]').first.click(); await pg.wait_for_selector('.pa-preg')
        assert 'Generado con tu clave' in await pg.inner_text('#exCab')
        # migración: un estado antiguo con exámenes dentro (S.propios) pasa a «Mis exámenes»
        mig = await ctx.new_page(); await mig.goto(base); await mig.wait_for_function('DATOS.cargado')
        await mig.evaluate("kv('readwrite', s => s.put({...S, propios: {'madrid__matematicas2': [EJ_EXAMEN.es]}, retos: {}}, 'main'))")
        await mig.reload(); await mig.wait_for_function('DATOS.cargado')
        await mig.wait_for_function(f"MEM.bib.length === {n + 1}", timeout=5000)
        assert await mig.evaluate("S.propios === undefined")
        # reto con examen oficial: lleva la huella de la versión
        await pg.click('#goHome'); await pg.click('#btnStart'); await pg.click('[data-c="madrid"]'); await pg.select_option('#selMat', 'matematicas2')
        await pg.click('#navNext'); await pg.click('#navNext'); await pg.wait_for_selector('.pa-preg'); await pg.fill('#auto0', '2')
        await pg.click('#btnACompartir'); await pg.wait_for_function("LINK.includes('madrid')")
        assert re.search(r'[?&]v=[0-9a-f]{10}', await pg.evaluate('LINK')) and '#e=' not in await pg.evaluate('LINK')
        # 4) idiomas y ranking
        for l in ('en', 'pt', 'es'):
            await pg.select_option('#selLang', l); await pg.click('#goHome'); await pg.click('#btnRanking'); await pg.wait_for_selector('.pa-rank')
            await pg.screenshot(path=OUT / f'5_ranking_{l}.png', full_page=True)
        # 5) reto
        pg2 = await ctx.new_page(); pg2.on('pageerror', lambda e: errores.append(str(e)))
        await pg2.goto(base + '?c=madrid&m=matematicas2&n=7.5'); await pg2.wait_for_function('DATOS.cargado')
        await pg2.wait_for_selector('#btnReto'); assert '7,5' in await pg2.inner_text('#retoBanner')
        await pg2.click('#btnReto'); await pg2.wait_for_selector('.pa-preg')
        # 6) móvil
        m = await b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, device_scale_factor=2, bypass_csp=True); pm = await m.new_page()
        await pm.goto(base); await pm.wait_for_function('DATOS.cargado'); await pm.screenshot(path=OUT / 'm0_inicio.png', full_page=True)
        await pm.click('#btnEjemplo'); await pm.wait_for_selector('.pa-tema'); await pm.screenshot(path=OUT / 'm2_pred.png', full_page=True)
        ancho = await pm.evaluate('document.documentElement.scrollWidth'); assert ancho <= 392, ancho
        # 7) sin datos (fichero local)
        pf = await ctx.new_page(); await pf.goto((SITE / 'index.html').as_uri()); await pf.wait_for_function('DATOS.cargado')
        assert 'Todavía no' in await pf.inner_text('#estadoDatos')
        await b.close()
    errores = [e for e in errores if 'favicon' not in e and 'ERR_FILE_NOT_FOUND' not in e and 'Failed to load resource' not in e]
    assert not errores, errores
    print('✓ e2e: ejemplo, datos reales, generación multiagente, reto, idiomas, ranking, móvil y modo sin datos')
asyncio.run(main())
