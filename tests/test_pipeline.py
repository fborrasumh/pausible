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

def test_arreglos_de_clasificacion():
    A = range(2022, 2027)
    # Liferay: el último segmento es un UUID; el nombre útil va antes
    u = 'https://universitats.gva.es/documents/389338055/389340489/HFIL+Juny+2024.pdf/15adf656-7c63-d005-fb6f-35efeb82dd11?t=1781007398048'
    assert crawl.fichero_de(u) == 'HFIL+Juny+2024.pdf'
    assert crawl.clasifica(u, {'texto': '', 'contexto': ''}, A)[:3] == ('filosofia', 2024, 'ord')
    u = 'https://www.um.es/documents/1/2/EBAU2022-JULIO+207+MATEM%C3%81TICAS+APLIC+CCSS+resuelto.pdf/fd8f212e-7268-247e-d655-34198bf0511a'
    assert crawl.clasifica(u, {'texto': 'EBAU2022-julio examen resuelto', 'contexto': ''}, A) == ('matccss', 2022, 'ext', 'examen')
    # «Examen i correcció» de Cataluña es un examen
    assert crawl.tipo_de('pau_mate.pdf', 'Examen i Correcció - Tribunal Ordinari') == 'examen'
    assert crawl.tipo_de('Criteris_correccio_mate.pdf', '') == 'criterios'
    # abreviaturas solo como palabra entera
    assert crawl.materia_abrev('pau_quim_2025_ord.pdf') == 'quimica' and crawl.materia_abrev('matematica') is None
    # mayores de 25 / PAP fuera
    assert crawl.NO_PAU.search(crawl.norm('Examenes PAU mayores 25_45_años_2025.pdf')) and crawl.NO_PAU.search(crawl.norm('Criteris_correccio_PAP_CCIRC_S1_cat_2022.pdf'))
    assert not crawl.NO_PAU.search(crawl.norm('pau_mate_2025.pdf'))
    # año heredado del título de la página
    assert crawl.clasifica('https://ciug.gal/x/20.pdf', {'texto': 'Exame', 'contexto': '', 'titulo': 'Exames PAU 2025'}, A)[1] == 2025
    # Galicia: plantilla y materia desde la cabecera del texto
    urls = list(crawl.candidatos_plantilla({'url': 'https://ciug.gal/PDF/{anio}/{prueba}/{conv}/exames/{cod}.pdf', 'prueba': ['PAU'], 'conv': ['ordinaria'], 'cod': '01-03,90'}, [2025]))
    assert urls == ['https://ciug.gal/PDF/2025/PAU/ordinaria/exames/%s.pdf' % c for c in ('01', '02', '03', '90')]
    d = crawl.completa_con_texto({'materia': None, 'conv': 'ord', 'anio': 2025, 'tipo': 'examen'}, 'PAU\nConvocatoria ordinaria 2025\nMATEMÁTICAS II\nCÓDIGO 20', A)
    assert d['materia'] == 'matematicas2'

def test_zip_drive_y_gestores():
    import io, zipfile, tempfile
    assert crawl.es_pdf('https://www.ucm.es/file/fisica-20') and crawl.es_pdf('https://x.es/examanes/sel_2025_biologia.zip')
    assert crawl.descarga_directa('https://drive.google.com/file/d/AbC_1-x/view?usp=drive_link') == 'https://drive.google.com/uc?export=download&id=AbC_1-x'
    assert crawl.conv_de('Reserva 2') == 'ext' and crawl.conv_de('Junio') == 'ord'
    pdf = open(next(crawl.R.glob('tests/*.pdf')), 'rb').read() if list(crawl.R.glob('tests/*.pdf')) else b'%PDF-1.4\n%%EOF'
    b = io.BytesIO(); z = zipfile.ZipFile(b, 'w'); z.writestr('Junio.pdf', pdf); z.writestr('Reserva_1.pdf', pdf); z.writestr('Criterios_Junio.pdf', pdf); z.writestr('nota.txt', 'x'); z.close()
    d = {'id': 'x', 'ccaa': 'andalucia', 'materia': 'biologia', 'anio': 2025, 'conv': 'nd', 'tipo': 'examen', 'url': 'https://x.es/sel_2025_biologia.zip', 'txt': '', 'chars': 0}
    with tempfile.TemporaryDirectory() as t:
        viejo = crawl.R; crawl.R = __import__('pathlib').Path(t)
        try: out = crawl.desde_zip(d, 'andalucia/biologia/2025_nd_examen_x', b.getvalue(), range(2022, 2027), lambda m: None)
        finally: crawl.R = viejo
    assert sorted((o['conv'], o['tipo']) for o in out) == [('ext', 'examen'), ('ord', 'criterios'), ('ord', 'examen')], out
    assert all(o['materia'] == 'biologia' and o['url'].startswith(d['url'] + '#') for o in out)

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
