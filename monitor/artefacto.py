"""Arma la versión del monitor que se publica como página de claude.ai.

Toma index.html y los datos, y deja en --salida:

- monitor-dolarizacion.html: el tablero (las descargas usan la capacidad de
  descargas de la página).
- data/monitor.json: los datos que se publican junto a la página.

Variantes: "ar" (índice publicado, promedio de 20 días) y "prom5" (versión
paralela con promedio de 5 días; correr antes `python -m monitor.prom5`).

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
    "prom5": {"data": "data/prom5", "titulo": "promedio de 5 días"},
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
        t = t.replace("<title>Dolarómetro</title>", f"<title>Dolarómetro ({v['titulo'].split()[-2]} días)</title>", 1)
        t = t.replace("<h1>Dolarómetro</h1>", f"<h1>Dolarómetro · {v['titulo']}</h1>", 1)
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
