"""Arma la versión del monitor que se publica como página de claude.ai.

Toma index.html y los datos, y deja en --salida:

- monitor-dolarizacion.html: el tablero (las descargas usan la capacidad de
  descargas de la página).
- data/monitor.json: los datos que se publican junto a la página.

Variantes: "ar" (índice publicado, promedio de 20 días) y "prom5" (versión
paralela con promedio de 5 días; correr antes `python -m monitor.prom5`) y "dia"
(el dato de cada día como si se repitiera 20 días; antes `python -m monitor.dia`).

    python -m monitor.artefacto --variante ar --salida /ruta/artifact
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from . import config

VARIANTES = {
    "ar": {"data": "data", "titulo": None},
    "prom5": {"data": "data/prom5", "titulo": "promedio de 5 días", "corto": "5 días"},
    "dia": {"data": "data/dia", "titulo": "si el dato de hoy se repitiera 20 días", "corto": "dato del día",
            "aviso": ("<b>Versión paralela, para ver el efecto puntual de cada día.</b> El índice publicado promedia 20 días "
                      "hábiles. Acá cada día muestra dónde quedaría si los datos de ese día se repitieran los 19 días "
                      "siguientes: el índice sin promediar, en la misma escala que el publicado. Se mueve más y anticipa "
                      "hacia dónde tira el publicado si nada cambia. No es el índice publicado.")},
}


def armar(variante: str, salida: Path) -> Path:
    v = VARIANTES[variante]
    raiz = config.ROOT
    t = (raiz / "index.html").read_text(encoding="utf-8")
    # El visor arma su propio <head>: se publica desde el <title>, sin <html>/<head>/<body>.
    t = t[t.index("<title>"):]
    t = re.sub(r'<meta name="description"[^>]*>\n?', "", t)
    t = t.replace("</head>\n<body>\n", "")
    t = t.replace("</body>\n</html>", "")
    if v["titulo"]:
        t = t.replace("<title>Dolarómetro</title>", f"<title>Dolarómetro ({v['corto']})</title>", 1)
        t = t.replace("<h1>Dolarómetro</h1>", f"<h1>Dolarómetro · {v['titulo']}</h1>", 1)
    if v.get("aviso"):
        t = t.replace('<div id="banner" class="card empty"></div>',
                      '<div id="banner" class="card empty"></div>\n  <div class="card" style="margin-bottom:16px;border-left:4px solid #C6BF93;font-size:14px">'
                      + v["aviso"] + "</div>", 1)
    (salida / "data").mkdir(parents=True, exist_ok=True)
    pagina = salida / "monitor-dolarizacion.html"
    pagina.write_text(t, encoding="utf-8")
    shutil.copyfile(raiz / v["data"] / "monitor.json", salida / "data" / "monitor.json")
    return pagina


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variante", choices=sorted(VARIANTES), default="ar")
    ap.add_argument("--salida", required=True, type=Path)
    a = ap.parse_args()
    print(armar(a.variante, a.salida))


if __name__ == "__main__":
    main()
