"""Las claves de la semana: tres o cuatro mensajes cortos (un titular y una
bajada) que abren el tablero, para entender en 30 segundos qué pasó.

Por defecto se escriben solas con los datos (cuánto cambió el índice en la
semana, qué componente lo movió más y qué subíndice está más lejos de 50).
Si hay un texto editorial en reportes/claves/AAAA-MM-DD.md de los últimos 7
días, se usa ese: cada clave es un párrafo que empieza con el titular en
negrita, por ejemplo

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
    n = abs(round(v)) if abs(v) >= 0.95 else round(abs(v), 1)
    txt = _n(n, 0 if isinstance(n, int) else 1)
    return f"{txt} {'punto' if txt == '1' else 'puntos'}"


def _tramo(v: float) -> str:
    for desde, hasta, _, label in config.INDICE_TRAMOS:
        if desde <= v < hasta:
            return label.lower()
    return ""


def _fecha(d: str) -> str:
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
             "septiembre", "octubre", "noviembre", "diciembre"]
    t = date.fromisoformat(d)
    return f"{t.day} de {meses[t.month - 1]}"


def editoriales(hasta: str, dir_: Path | None = None) -> tuple[str, list[dict]] | None:
    """El texto editorial más reciente de los 7 días anteriores a `hasta`."""
    d = dir_ or CLAVES_DIR
    if not d.exists():
        return None
    tope = date.fromisoformat(hasta)
    for f in sorted(d.glob("????-??-??.md"), reverse=True):
        try:
            fd = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if not (tope - timedelta(days=7) < fd <= tope):
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


def _automaticas(payload: dict) -> list[dict]:
    from .report import APENDICE_AR  # textos de cada componente

    h = payload["headline"]
    i1, i0 = h.get("indice"), h.get("indice_7d")
    if i1 is None:
        return []
    items = []
    d = None if i0 is None else i1 - i0
    tramo = _tramo(i1)
    if d is None or abs(d) < 1:
        tit = "La presión sobre el peso se mantiene estable"
        baj = f"El índice quedó en {_n(i1, 0)}/100 ({tramo}), casi igual que una semana atrás."
    elif d < 0:
        tit = "Se modera la presión sobre el peso" if i1 >= 50 else "Se amplía el alivio sobre el peso"
        baj = f"El índice bajó {_puntos(d)} en la semana y quedó en {_n(i1, 0)}/100 ({tramo})."
    else:
        tit = "Aumenta la presión sobre el peso" if i1 > 50 else "Se achica el alivio sobre el peso"
        baj = f"El índice subió {_puntos(d)} en la semana y quedó en {_n(i1, 0)}/100 ({tramo})."
    items.append({"titular": tit + ".", "bajada": baj})

    # Lo que más movió el índice: en la dirección del cambio, si fue claro.
    comps = [c for c in payload["ipd"]["components"] if c.get("cambio_semana") is not None]
    if d is not None and abs(d) >= 0.5:
        comps = [c for c in comps if c["cambio_semana"] * d > 0] or comps
    if comps:
        c = max(comps, key=lambda c: abs(c["cambio_semana"]))
        v = c["cambio_semana"]
        textos = APENDICE_AR.get(c["key"])
        if textos and abs(v) >= 0.3:
            frase = textos[1] if v > 0 else textos[2]
            tit, _, resto = frase.partition(":")
            tit = tit.rstrip(".") + "."
            resto = resto.strip()
            resto = (resto[:1].upper() + resto[1:]) if resto else ""
            mov = f"Fue lo que más movió el índice en la semana: {_puntos(v)} {'a la suba' if v > 0 else 'a la baja'}."
            items.append({"titular": tit, "bajada": (resto + " " if resto else "") + mov})

    # Los subíndices más lejos de 50 (el segundo, sólo si está del otro lado).
    bl = [(k, b) for k, b in payload["ipd"]["blocks"].items() if b.get("indice_last") is not None and k in SUBINDICE]
    bl.sort(key=lambda kb: -abs(kb[1]["indice_last"] - 50))
    elegidos = bl[:1]
    if len(bl) > 1:
        otro = next(((k, b) for k, b in bl[1:] if (b["indice_last"] - 50) * (bl[0][1]["indice_last"] - 50) < 0
                     and abs(b["indice_last"] - 50) >= 10), None)
        if otro:
            elegidos.append(otro)
    for k, b in elegidos:
        v1, v0 = b["indice_last"], b.get("indice_7d")
        tit = SUBINDICE[k][0 if v1 >= 50 else 1]
        cambio = ("" if v0 is None or abs(v1 - v0) < 0.5
                  else f", {_puntos(v1 - v0)} {'más' if v1 > v0 else 'menos'} que la semana anterior")
        items.append({"titular": tit + ".",
                      "bajada": f"El subíndice de {b['label'].lower()} quedó en {_n(v1, 0)}/100{cambio}.",
                      "ayuda": f"Sigue {QUE_MIDE[k]}."})
    return items


def generar(payload: dict, dir_: Path | None = None) -> dict:
    fecha = payload["headline"].get("date") or ""
    ed = editoriales(fecha, dir_) if fecha else None
    if ed:
        f, items = ed
        return {"fecha": f, "fecha_txt": _fecha(f), "origen": "editorial", "items": items}
    return {"fecha": fecha, "fecha_txt": _fecha(fecha) if fecha else "", "origen": "automatico",
            "items": _automaticas(payload)}
