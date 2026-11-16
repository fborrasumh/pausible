#!/usr/bin/env python3
"""Mete KaTeX (fórmulas LaTeX) dentro del HTML de la app: JS + mhchem (química) + CSS con las fuentes en base64.
Así las fórmulas se ven igual sin red y sin cargar nada de fuera (la CSP no lo permitiría).
Uso:  npm i katex@0.16  &&  python3 tools/vendor_katex.py /ruta/node_modules/katex"""
import base64, pathlib, re, sys
K = pathlib.Path(sys.argv[1]) / 'dist'
R = pathlib.Path(__file__).resolve().parent.parent
js = (K / 'katex.min.js').read_text(encoding='utf-8') + '\n' + (K / 'contrib' / 'mhchem.min.js').read_text(encoding='utf-8') + '\n'
(R / 'src' / 'katex.js').write_text('/* KaTeX 0.16 (MIT) + mhchem — https://katex.org */\n' + js, encoding='utf-8')
css = (K / 'katex.min.css').read_text(encoding='utf-8')
def fuente(m):
    f = K / 'fonts' / m.group(1)
    return 'url(data:font/woff2;base64,' + base64.b64encode(f.read_bytes()).decode() + ') format("woff2")'
css = re.sub(r'url\(fonts/([^)]+\.woff2)\) format\("woff2"\)', fuente, css)
css = re.sub(r',url\(fonts/[^)]+\.(woff|ttf)\) format\("(woff|truetype)"\)', '', css)
(R / 'src' / 'katex.css').write_text('/* KaTeX 0.16 (MIT) */\n' + css, encoding='utf-8')
print('src/katex.js', len(js) // 1024, 'KB · src/katex.css', len(css) // 1024, 'KB')
