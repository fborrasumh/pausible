"""Pruebas del pipeline sin red: clasificación de enlaces, predicción con validación ciega y filtro multiagente."""
import json, pathlib, sys
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'pipeline'))
import crawl, analiza, genera

def test_clasificacion():
    html = '''<h2>Matemáticas II</h2><table><tr><td>Convocatoria ordinaria 2024</td><td><a href="/doc/mat2_ord_2024.pdf">Examen</a></td>
    <td><a href="/doc/crit_mat2_2024.pdf">Criterios de corrección</a></td></tr></table>
    <h3>Historia del Arte</h3><a href="files/HArte-extraordinaria-2025.pdf">Extraordinaria 2025</a>
    <a href="x/Matematicas_Aplicadas_CCSS_II_junio_2023-24.pdf">Examen</a><a href="viejo/fisica_2019.pdf">Física 2019</a>'''
    L = crawl.enlaces(html)
    c = {h: crawl.clasifica(h, {'texto': t, 'contexto': ctx, 'pagina': ''}, range(2022, 2027)) for h, t, ctx in L}
    assert c['/doc/mat2_ord_2024.pdf'] == ('matematicas2', 2024, 'ord', 'examen'), c['/doc/mat2_ord_2024.pdf']
    assert c['/doc/crit_mat2_2024.pdf'][3] == 'criterios'
    assert c['files/HArte-extraordinaria-2025.pdf'][:3] == ('historiaarte', 2025, 'ext')
    assert c['x/Matematicas_Aplicadas_CCSS_II_junio_2023-24.pdf'][:3] == ('matccss', 2024, 'ord')
    assert c['viejo/fisica_2019.pdf'][1] is None          # fuera del periodo
    assert crawl.materia_de('Historia de la Filosofía') == 'filosofia' and crawl.materia_de('Historia de España') == 'historia'
    assert crawl.materia_de('Matemàtiques II') == 'matematicas2' and crawl.materia_de('Matemáticas Generales') == 'matgenerales'

def test_prediccion_y_validacion():
    temas = [{'id': 'a', 'nombre': 'A', 'kw': []}, {'id': 'b', 'nombre': 'B', 'kw': []}, {'id': 'c', 'nombre': 'C', 'kw': []}, {'id': 'd', 'nombre': 'D', 'kw': []}]
    H = lambda *ts: {t: 3 for t in ts}
    ex = [{'anio': 2022, 'conv': 'ord', 'hits': H('a', 'b')}, {'anio': 2023, 'conv': 'ord', 'hits': H('a', 'b')}, {'anio': 2024, 'conv': 'ord', 'hits': H('a', 'c')},
          {'anio': 2025, 'conv': 'ord', 'hits': H('a', 'b')}, {'anio': 2025, 'conv': 'ext', 'hits': H('b', 'c')}, {'anio': 2026, 'conv': 'ord', 'hits': H('a', 'b')}]
    p = analiza.predice(ex, temas)
    assert p['a'] > p['c'] > p['d'] and p['d'] == 0.05          # nunca cero
    v = analiza.validacion(ex, temas)
    assert v['anio'] == 2026 and v['k'] == 2 and v['aciertos'] == 2 and v['azar'] == 0.5
    assert analiza.confianza(len(ex), v) == 'alta'
    assert analiza.cuenta('El pH de la disolución; la phase', ['ph']) == 1          # raíz corta = palabra entera

def llm_falso(respuestas):
    def f(system, user, temperatura=0.3, max_tokens=0):
        for clave, r in respuestas:
            if clave in user: return r() if callable(r) else r
        raise AssertionError('prompt inesperado: ' + user[:80])
    return f

def test_multiagente_atrapa_al_resolutor_que_se_equivoca():
    examen = json.dumps({'titulo': 'T', 'preguntas': [{'n': '1', 'tema': 'integrales', 'puntos': 2.5, 'tipo': 'calculo', 'enunciado': 'Calcula la integral de 2x entre 0 y 3.'}]})
    bueno = json.dumps({'solucion': 'x^2 entre 0 y 3 = 9', 'resultado': '9', 'numeros': [9], 'codigo': 'import sympy as s\nx=s.symbols("x")\nprint(json.dumps([float(s.integrate(2*x,(x,0,3)))]))', 'criterios': ''})
    malo = json.dumps({'solucion': '= 6', 'resultado': '6', 'numeros': [6], 'codigo': 'print(json.dumps([6]))', 'criterios': ''})
    mentiroso = json.dumps({'solucion': '= 8', 'resultado': '8', 'numeros': [8], 'codigo': 'print(json.dumps([9]))', 'criterios': ''})   # su código no respalda lo que dice
    orden = iter([malo, mentiroso, bueno, bueno, bueno])
    llm = llm_falso([('Redacta un examen', examen), ('Resuelve esta pregunta', lambda: next(orden))])
    reg = {'nombre': 'Matemáticas II', 'temas': [{'id': 'integrales', 'nombre': 'Integrales', 'p': 0.8, 'veces': 4, 'de': 5}]}
    ex = genera.genera_uno(llm, 'madrid', 'Comunidad de Madrid', 'matematicas2', reg, [])
    # A=6 (código coherente), B=8 (incoherente) → no hay 2 coherentes que coincidan → C=9: tampoco (6≠9) → pregunta descartada y nueva ronda
    # 2.ª ronda: A=9, B=9 coherentes y coinciden → se publica con verificación por código
    assert ex and ex['preguntas'][0]['resultado'] == '9' and ex['preguntas'][0]['verificacion'] == 'codigo' and ex['rondas'] == 2

def test_abierta_sin_consenso_no_se_publica():
    examen = json.dumps({'preguntas': [{'n': '1', 'tema': 'kant', 'puntos': 3, 'tipo': 'abierta', 'enunciado': 'Explica el imperativo categórico.'}]})
    sol = json.dumps({'solucion': 'Kant…', 'claves': ['incondicionado'], 'criterios': ''})
    llm = llm_falso([('Redacta un examen', examen), ('Resuelve esta pregunta', sol), ('Eres el tribunal', json.dumps({'coinciden': False, 'errores': ['B atribuye la obra a Hume'], 'mejor': 'ninguna'}))])
    assert genera.genera_uno(llm, 'x', 'X', 'filosofia', {'nombre': 'Filosofía', 'temas': [{'id': 'kant', 'nombre': 'Kant', 'p': .5, 'veces': 1, 'de': 2}]}, []) is None

if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_'): f(); print('✓', n)
