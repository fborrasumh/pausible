"""Prueba de extremo a extremo de PAUsible en Chromium (Playwright), con datos sintéticos servidos por HTTP y la IA simulada.
Uso: python3 tests/e2e_test.py /ruta/al/sitio   (carpeta con index.html y data/)"""
import asyncio, http.server, json, sys, threading, functools, pathlib
from playwright.async_api import async_playwright
SITE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
OUT = pathlib.Path('/tmp/e2e/shots'); OUT.mkdir(parents=True, exist_ok=True)

def sirve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    h.log_message = lambda *a: None
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s

RESOL = {'A': iter([[9], [6]]), 'B': iter([[9], [7]]), 'C': iter([[8]])}
def ia(user):
    if 'Redacta un examen ORIGINAL' in user:
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
        await pg.click('#navNext'); await pg.wait_for_selector('.pa-preg'); assert 'Examen probable Madrid' in await pg.inner_text('#exCab')
        # 3) generar con clave (Comunitat Valenciana no tiene examen): la pregunta en la que nadie coincide se descarta
        await pg.evaluate("localStorage.setItem(PROV.openai.k,'sk-proj-prueba-0000000000000000')")
        await pg.click('#goHome'); await pg.click('#btnStart'); await pg.click('[data-c="valenciana"]'); await pg.select_option('#selMat', 'matematicas2')
        await pg.click('#navNext'); await pg.click('#navNext'); await pg.click('#btnGenera')
        await pg.wait_for_selector('.pa-preg', timeout=15000)
        assert await pg.locator('.pa-preg').count() == 1 and 'Se descartaron 1' in await pg.inner_text('#exCab')
        assert '∫' in await pg.inner_text('.pa-enun')    # LaTeX ligero
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
