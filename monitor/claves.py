"""Las claves de la semana: tres o cuatro mensajes cortos (un titular y una
bajada) que abren el tablero y forman el mail semanal, para entender en 30
segundos qué pasó.

Son de la última semana cerrada (de lunes a viernes, contra el viernes
anterior): el tablero cambia todos los días, pero las claves quedan fijas
hasta el viernes siguiente. Por defecto se escriben solas con los datos
(cuánto cambió el índice, qué componente lo movió más y qué subíndice está
más lejos de 50). Si hay un texto editorial en reportes/claves/AAAA-MM-DD.md
(la fecha del viernes de la semana, o un día hasta el jueves siguiente), se
usa ese: cada clave es un párrafo que empieza con el titular en negrita, por
ejemplo

    **Se modera la presión sobre el peso.** El índice bajó 3 puntos en la semana.

Los comentarios <!-- ... --> no se publican.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from . import config

CLAVES_DIR = config.ROOT / "reportes" / "claves"

# Titulares por subíndice, según esté arriba (presión) o abajo (alivio) de 50.
SUBINDICE = {
    "cambiaria": ("Sigue la tensión en el mercado de cambios", "El mercado de cambios, sin tensión"),
    "dolarizacion": ("Persiste la demanda de cobertura en dólares", "Baja la demanda de cobertura en dólares"),
    "extranjerizacion": ("Sigue la desconfianza en los activos argentinos", "Mejora la confianza en los activos argentinos"),
}
QUE_MIDE = {
    "cambiaria": "el tipo de cambio, las reservas, la tasa en pesos, la brecha y la intervención del BCRA",
    "dolarizacion": "los futuros de dólar, los depósitos en dólares, las compras de los ahorristas y el dólar linked",
    "extranjerizacion": "el canje, la volatilidad del CCL y el riesgo país",
}


def _n(v: float, dec: int = 0) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _puntos(v: float) -> str:
    n = round(abs(v), 1)
    txt = _n(n, 0) if n == int(n) else _n(n, 1)
    return f"{txt} {'punto' if txt == '1' else 'puntos'}"


def _tramo(v: float) -> str:
    for desde, hasta, _, label in config.INDICE_TRAMOS:
        if desde <= v < hasta:
            return label.lower()
    return ""


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha(d: str) -> str:
    t = date.fromisoformat(d)
    return f"{t.day} de {MESES[t.month - 1]}"


def etiqueta_semana(viernes: str) -> str:
    """"9 al 13 de noviembre" (o "27 de octubre al 1 de noviembre")."""
    v = date.fromisoformat(viernes)
    lu = v - timedelta(days=4)
    if lu.month == v.month:
        return f"{lu.day} al {v.day} de {MESES[v.month - 1]}"
    return f"{lu.day} de {MESES[lu.month - 1]} al {v.day} de {MESES[v.month - 1]}"


def editoriales(viernes: str, dir_: Path | None = None) -> tuple[str, list[dict]] | None:
    """El texto editorial de la semana que cierra `viernes`: un archivo con
    fecha entre ese viernes y el jueves siguiente."""
    d = dir_ or CLAVES_DIR
    if not d.exists():
        return None
    v = date.fromisoformat(viernes)
    for f in sorted(d.glob("????-??-??.md"), reverse=True):
        try:
            fd = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if not (v <= fd <= v + timedelta(days=6)):
            continue
        txt = re.sub(r"<!--.*?-->", "", f.read_text(encoding="utf-8"), flags=re.S).strip()
        items = []
        for b in re.split(r"\n\s*\n", txt):
            b = " ".join(l.strip() for l in b.splitlines() if l.strip())
            m = re.match(r"\*\*(.+?)\*\*\s*(.*)", b)
            if m:
                items.append({"titular": m.group(1).strip(), "bajada": m.group(2).strip()})
        if items:
            return f.stem, items
    return None


def _automaticas(semana: dict) -> list[dict]:
    """`semana`: {"i1", "i0": índice al viernes y al viernes anterior,
    "componentes": {clave: aporte al cambio en la semana},
    "bloques": {clave: {"label", "v1", "v0"}}}."""
    from .report import APENDICE_AR  # textos de cada componente

    i1, i0 = semana.get("i1"), semana.get("i0")
    if i1 is None:
        return []
    items = []
    d = None if i0 is None else i1 - i0
    tramo = _tramo(i1)
    if d is None or abs(d) < 1:
        tit = "La presión sobre el peso se mantiene estable"
        baj = f"El índice cerró la semana en {_n(i1, 0)}/100 ({tramo}), casi igual que el viernes anterior."
    elif d < 0:
        tit = "Se modera la presión sobre el peso" if i1 >= 50 else "Se amplía el alivio sobre el peso"
        baj = f"El índice bajó {_puntos(d)} en la semana y cerró en {_n(i1, 0)}/100 ({tramo})."
    else:
        tit = "Aumenta la presión sobre el peso" if i1 > 50 else "Se achica el alivio sobre el peso"
        baj = f"El índice subió {_puntos(d)} en la semana y cerró en {_n(i1, 0)}/100 ({tramo})."
    items.append({"titular": tit + ".", "bajada": baj})

    # Lo que más movió el índice: en la dirección del cambio, si fue claro.
    comps = [(k, v) for k, v in (semana.get("componentes") or {}).items() if v is not None and v == v]
    if d is not None and abs(d) >= 0.5:
        comps = [(k, v) for k, v in comps if v * d > 0] or comps
    if comps:
        clave, v = max(comps, key=lambda kv: abs(kv[1]))
        textos = APENDICE_AR.get(clave)
        if textos and abs(v) >= 0.3:
            frase = textos[1] if v > 0 else textos[2]
            tit, _, resto = frase.partition(":")
            tit = tit.rstrip(".") + "."
            resto = resto.strip()
            resto = (resto[:1].upper() + resto[1:]) if resto else ""
            mov = f"Fue lo que más movió el índice en la semana: {_puntos(v)} {'a la suba' if v > 0 else 'a la baja'}."
            items.append({"titular": tit, "bajada": (resto + " " if resto else "") + mov})

    # Los subíndices más lejos de 50 (el segundo, sólo si está del otro lado).
    bl = [(k, b) for k, b in (semana.get("bloques") or {}).items() if b.get("v1") is not None and b["v1"] == b["v1"] and k in SUBINDICE]
    bl.sort(key=lambda kb: -abs(kb[1]["v1"] - 50))
    elegidos = bl[:1]
    if len(bl) > 1:
        otro = next(((k, b) for k, b in bl[1:] if (b["v1"] - 50) * (bl[0][1]["v1"] - 50) < 0
                     and abs(b["v1"] - 50) >= 10), None)
        if otro:
            elegidos.append(otro)
    for k, b in elegidos:
        v1, v0 = b["v1"], b.get("v0")
        tit = SUBINDICE[k][0 if v1 >= 50 else 1]
        cambio = ("" if v0 is None or v0 != v0 or abs(v1 - v0) < 0.5
                  else f", {_puntos(v1 - v0)} {'más' if v1 > v0 else 'menos'} que la semana anterior")
        items.append({"titular": tit + ".",
                      "bajada": f"El subíndice de {b['label'].lower()} cerró en {_n(v1, 0)}/100{cambio}.",
                      "ayuda": f"Sigue {QUE_MIDE[k]}."})
    return items


def generar(viernes: str, semana: dict, dir_: Path | None = None, texto: str = "") -> dict:
    """Las claves de la semana que cierra `viernes` (AAAA-MM-DD). `texto`: el
    racconto de la semana en HTML, si lo hay."""
    base = {"fecha": viernes, "semana_txt": etiqueta_semana(viernes), "fecha_txt": _fecha(viernes),
            "indice": semana.get("i1"), "indice_previo": semana.get("i0"),
            "bloques": semana.get("bloques") or {}, "texto": texto}
    ed = editoriales(viernes, dir_)
    if ed:
        return {**base, "origen": "editorial", "items": ed[1]}
    return {**base, "origen": "automatico", "items": _automaticas(semana)}
