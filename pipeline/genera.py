#!/usr/bin/env python3
"""Genera exámenes probables de la PAU 2027 con su solución, mediante varios agentes de IA que se vigilan entre sí.

  Ponente      redacta un examen original con el formato de la comunidad, centrado en los temas más probables.
  Resolutor A  lo resuelve sin ver nada más.
  Resolutor B  lo resuelve por separado (otra temperatura, otro enfoque pedido), sin ver la solución de A.
  Código       en las preguntas de cálculo, cada resolutor entrega además un programa con sympy que calcula el
               resultado; se ejecuta aquí y su salida tiene que coincidir con lo que el resolutor afirma.
  Tribunal     si A y B (o su código) no coinciden, un tercer resolutor C decide por mayoría 2 de 3. Si no hay
               mayoría, la pregunta se descarta y el ponente redacta otra (hasta 2 veces).

Solo se publica lo que pasa el filtro, y cada pregunta lleva su nivel de verificación:
  'codigo'    cálculo: dos resoluciones independientes y su código coinciden en el resultado.
  'consenso'  pregunta abierta: dos resoluciones coinciden en los puntos clave y el tribunal no ve errores.
Nada de esto es una garantía: es mucho más fiable que una sola respuesta de IA, y la app lo dice así.

Uso (en GitHub Actions, con el secreto OPENAI_API_KEY; también acepta ANTHROPIC_API_KEY):
  python3 pipeline/genera.py --max 20                 # las combinaciones que aún no tienen examen
  python3 pipeline/genera.py --ccaa madrid --materia matematicas2 --forzar
"""
import argparse, json, os, pathlib, re, subprocess, sys, tempfile, time

R = pathlib.Path(__file__).resolve().parent.parent
PROVEEDOR = 'openai' if os.environ.get('OPENAI_API_KEY') else 'anthropic' if os.environ.get('ANTHROPIC_API_KEY') else None
MODELO = os.environ.get('PAUSIBLE_MODELO') or {'openai': 'gpt-6-luna', 'anthropic': 'claude-sonnet-5-5'}.get(PROVEEDOR, '')


def llm_openai(system, user, temperatura=0.3, max_tokens=8000):
    """OpenAI Chat Completions. Los modelos de razonamiento (gpt-5*, o*) no admiten temperature ni max_tokens:
    ahí la diversidad entre resolutores sale de las instrucciones distintas que recibe cada uno."""
    import requests
    razona = re.match(r'^(gpt-[5-9]|o\d)', MODELO) is not None
    body = {'model': MODELO, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'response_format': {'type': 'json_object'}}
    if razona:
        body['max_completion_tokens'] = max_tokens * 3
        body['reasoning_effort'] = os.environ.get('PAUSIBLE_ESFUERZO') or 'high'   # modelo barato + razonar más = menos errores de cálculo
    else: body.update(max_tokens=max_tokens, temperature=temperatura)
    for intento in range(4):
        r = requests.post('https://api.openai.com/v1/chat/completions', timeout=600, json=body,
                          headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'], 'Content-Type': 'application/json'})
        if r.status_code == 200: return r.json()['choices'][0]['message']['content'] or ''
        if r.status_code in (429, 500, 502, 503): time.sleep(20 * (intento + 1)); continue
        raise RuntimeError(f'OpenAI {r.status_code}: {r.text[:300]}')
    raise RuntimeError('OpenAI sin respuesta')


def llm_anthropic(system, user, temperatura=0.3, max_tokens=8000):
    import requests
    for intento in range(4):
        r = requests.post('https://api.anthropic.com/v1/messages', timeout=300, headers={
            'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': MODELO, 'max_tokens': max_tokens, 'temperature': temperatura, 'system': system, 'messages': [{'role': 'user', 'content': user}]})
        if r.status_code == 200: return ''.join(b.get('text', '') for b in r.json()['content'])
        if r.status_code in (429, 500, 529): time.sleep(20 * (intento + 1)); continue
        raise RuntimeError(f'API {r.status_code}: {r.text[:300]}')
    raise RuntimeError('API sin respuesta')


def json_de(txt):
    m = re.search(r'\{.*\}', txt, re.S)
    if not m: raise ValueError('la IA no devolvió JSON')
    return json.loads(m.group(0))


SYS = 'Eres miembro de la comisión que elabora la PAU (selectividad) en España. Eres riguroso y respondes SOLO con JSON válido.'


def p_ponente(cc, mat, temas, referencias, evitar=''):
    top = '\n'.join(f'- {t["nombre"]}: probabilidad {round(t["p"] * 100)} % (salió {t["veces"]} de {t["de"]} veces)' for t in temas)
    refs = '\n\n'.join(f'--- EXAMEN REAL {r["anio"]} ({r["conv"]}) ---\n{r["texto"][:7000]}' for r in referencias)
    return f"""Redacta un examen ORIGINAL de «{mat}» para la PAU 2027 de {cc}, con el mismo formato, número de preguntas, puntuación, duración (90 min) y grado de optatividad que los exámenes reales que te doy. Debe ser el examen «más probable»: reparte las preguntas según estas probabilidades de tema, priorizando los más probables sin dejar fuera la estructura habitual:
{top}
No copies enunciados reales: mismos tipos de tarea, datos y contextos nuevos. Incluye el enfoque competencial (situaciones contextualizadas) del modelo vigente desde 2025.
Cada pregunta debe tener UNA solución inequívoca (en cálculo, datos que den resultados limpios y comprobables).{evitar}
Devuelve SOLO este JSON:
{{"titulo":"…","duracion_min":90,"instrucciones":"…","preguntas":[{{"n":"1","tema":"id del tema","puntos":2.5,"tipo":"calculo|abierta","enunciado":"texto completo (usa LaTeX entre $…$ para fórmulas)"}}]}}
Ids de tema válidos: {', '.join(t['id'] for t in temas)}

{refs}"""


def p_resolutor(mat, preg, calculo, variante):
    extra = ('\nAdemás escribe "codigo": un programa Python 3 con sympy (sin entrada ni red) que calcule DESDE LOS DATOS del enunciado los resultados finales y los imprima con print(json.dumps([...])) como lista de números en el orden en que se piden.'
             if calculo else '\nEn "claves" pon de 3 a 8 afirmaciones concretas que una respuesta correcta debe contener.')
    return f"""Resuelve esta pregunta de la PAU de «{mat}» como lo haría la comisión correctora, paso a paso y con la nota de corrección. {variante}
Devuelve SOLO JSON: {{"solucion":"desarrollo completo en Markdown (LaTeX entre $…$)","resultado":"resultado final en una línea","numeros":[resultados finales como números, en orden]{',"codigo":"…"' if calculo else ',"claves":["…"]'},"criterios":"cómo se reparten los puntos"}}{extra}

PREGUNTA ({preg['puntos']} puntos):
{preg['enunciado']}"""


def ejecuta(codigo, timeout=30):
    """Ejecuta el código sympy de un resolutor en un proceso aparte y devuelve la lista de números que imprime."""
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / 'sol.py'
        f.write_text('import json\n' + codigo, encoding='utf-8')
        try:
            r = subprocess.run([sys.executable, '-I', str(f)], capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return None
        lineas = [l for l in r.stdout.strip().splitlines() if l.strip().startswith('[')]
        try:
            return [float(complex(x).real) if not isinstance(x, (int, float)) else float(x) for x in json.loads(lineas[-1])] if lineas else None
        except Exception:
            return None


def iguales(a, b, tol=1e-3):
    if a is None or b is None or len(a) != len(b) or not a: return False
    return all(abs(x - y) <= tol * max(1, abs(x), abs(y)) for x, y in zip(a, b))


def verifica_calculo(sols):
    """sols: resoluciones con 'numeros' y 'codigo'. Una resolución es «coherente» si su código reproduce sus números.
    Devuelve el índice de la resolución ganadora si al menos dos coherentes coinciden; si no, None."""
    coh = []
    for i, s in enumerate(sols):
        out = ejecuta(s.get('codigo', '')) if s.get('codigo') else None
        nums = [float(x) for x in s.get('numeros', []) if isinstance(x, (int, float))]
        s['_codigo_ok'] = iguales(out, nums)
        if s['_codigo_ok']: coh.append(i)
    for i in coh:
        for j in coh:
            if j > i and iguales(sols[i]['numeros'], sols[j]['numeros']): return i
    return None


def p_tribunal(mat, preg, sols):
    bloques = '\n\n'.join(f'--- RESOLUCIÓN {chr(65 + i)} ---\n{s["solucion"]}\nClaves: {s.get("claves")}' for i, s in enumerate(sols))
    return f"""Eres el tribunal de la PAU de «{mat}». Compara las resoluciones independientes de esta pregunta. Decide si coinciden en lo esencial y si alguna contiene un error de contenido (dato falso, fecha, autor, concepto mal explicado).
Devuelve SOLO JSON: {{"coinciden":true|false,"errores":["…"],"mejor":"A|B|ninguna"}}

PREGUNTA: {preg['enunciado']}

{bloques}"""


def resuelve(llm, mat, preg):
    calc = preg.get('tipo') == 'calculo'
    variantes = ['', 'Resuélvela por un método distinto al más habitual si existe y comprueba el resultado al final.', 'Sé especialmente cuidadoso con los signos, las unidades y los casos particulares.']
    sols = [json_de(llm(SYS, p_resolutor(mat, preg, calc, variantes[k]), temperatura=0.2 + 0.3 * k)) for k in range(2)]
    if calc:
        g = verifica_calculo(sols)
        if g is None:
            sols.append(json_de(llm(SYS, p_resolutor(mat, preg, calc, variantes[2]), temperatura=0.6)))
            g = verifica_calculo(sols)
        return (sols[g], 'codigo', len(sols)) if g is not None else (None, None, len(sols))
    t = json_de(llm(SYS, p_tribunal(mat, preg, sols), temperatura=0))
    if t.get('coinciden') and not t.get('errores') and t.get('mejor') in ('A', 'B'):
        return sols[ord(t['mejor']) - 65], 'consenso', len(sols)
    return None, None, len(sols)


def genera_uno(llm, cid, cc_nombre, mid, reg, referencias):
    mat = reg['nombre']
    temas = reg['temas']
    descartes = []
    for ronda in range(3):
        evitar = ('\nNo repitas estos planteamientos, que se descartaron por ambiguos: ' + ' | '.join(descartes)) if descartes else ''
        ex = json_de(llm(SYS, p_ponente(cc_nombre, mat, temas, referencias, evitar), temperatura=0.7, max_tokens=12000))
        preguntas, fallo = [], False
        for p in ex['preguntas']:
            sol, nivel, n = resuelve(llm, mat, p)
            if not sol:
                descartes.append(p['enunciado'][:160]); fallo = True; break
            preguntas.append({**p, 'solucion': sol['solucion'], 'resultado': sol.get('resultado', ''), 'criterios': sol.get('criterios', ''), 'verificacion': nivel, 'resoluciones': n})
        if not fallo:
            return {'ccaa': cid, 'materia': mid, 'titulo': ex.get('titulo', ''), 'duracion_min': ex.get('duracion_min', 90), 'instrucciones': ex.get('instrucciones', ''),
                    'preguntas': preguntas, 'generado': time.strftime('%Y-%m-%d'), 'modelo': MODELO, 'rondas': ronda + 1,
                    'temas_base': [{'id': t['id'], 'p': t['p']} for t in temas[:6]], 'referencias': [r['url'] for r in referencias]}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ccaa'); ap.add_argument('--materia'); ap.add_argument('--max', type=int, default=20); ap.add_argument('--forzar', action='store_true')
    a = ap.parse_args()
    if not PROVEEDOR:
        print('Sin OPENAI_API_KEY: no se generan exámenes (añádela en Settings → Secrets and variables → Actions).'); return
    llm = llm_openai if PROVEEDOR == 'openai' else llm_anthropic
    print(f'Proveedor: {PROVEEDOR} · modelo: {MODELO}')
    pred = json.loads((R / 'data' / 'predicciones.json').read_text(encoding='utf-8'))
    corpus = {d['url']: d for d in json.loads((R / 'data' / 'corpus.json').read_text(encoding='utf-8'))['documentos']}
    od = R / 'data' / 'examenes'; od.mkdir(parents=True, exist_ok=True)
    hechos = 0
    for cid, c in pred['ccaa'].items():
        if a.ccaa and cid != a.ccaa: continue
        for mid, reg in c['materias'].items():
            if a.materia and mid != a.materia: continue
            f = od / f'{cid}__{mid}.json'
            if not reg.get('temas') or (f.exists() and not a.forzar) or hechos >= a.max: continue
            refs = []
            for e in sorted(reg['examenes'], key=lambda e: (e['anio'], e['conv'] == 'ord'), reverse=True)[:2]:
                d = corpus.get(e['url'])
                if d and (R / d['txt']).exists(): refs.append({**e, 'texto': (R / d['txt']).read_text(encoding='utf-8', errors='ignore')})
            print(f'· {c["nombre"]} · {reg["nombre"]}', flush=True)
            try:
                ex = genera_uno(llm, cid, c['nombre'], mid, reg, refs)
            except Exception as e:
                print(f'  error: {e}'); continue
            if ex:
                f.write_text(json.dumps(ex, ensure_ascii=False, indent=1), encoding='utf-8'); hechos += 1
                print(f'  ✓ {len(ex["preguntas"])} preguntas verificadas')
            else:
                print('  ✗ no se alcanzó consenso: no se publica')
    idx = sorted(p.stem for p in od.glob('*__*.json'))
    (od / 'index.json').write_text(json.dumps(idx), encoding='utf-8')
    print(f'✓ {hechos} exámenes nuevos; {len(idx)} en total')


if __name__ == '__main__':
    main()
