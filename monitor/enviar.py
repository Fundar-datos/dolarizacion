"""Envío por email de las claves de la semana del Dolarómetro (SMTP).

    python -m monitor.enviar                  # a REPORTE_PARA
    python -m monitor.enviar --para a@x.com   # prueba a otra lista
    python -m monitor.enviar --dry-run        # arma el mail y lo guarda, sin enviar

Variables de entorno (en GitHub, secretos del repositorio):
  SMTP_USER       cuenta que envía (p. ej. elibman@fund.ar)
  SMTP_PASSWORD   contraseña de aplicación de esa cuenta
  REPORTE_PARA    destinatarios separados por coma
  SMTP_HOST       por defecto smtp.gmail.com (Google Workspace)
  SMTP_PORT       por defecto 587 (STARTTLS)

El mail sale de data/monitor.json: las claves de la última semana cerrada, el
índice y los subíndices al viernes, el texto de la semana si lo hay
(reportes/textos/AAAA-MM-DD.md) y un enlace al tablero. No lleva adjuntos.
Los destinatarios van en copia oculta para no exponer la lista.
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

TABLERO = "https://elibman36.github.io/dolarizacion/"
LOGO = Path(__file__).parent / "assets" / "logo_fundar_blanco.png"
INK, INK2, MUTED, PAGE, SURFACE, VERDE = "#161615", "#606060", "#8C8B86", "#ECEAE3", "#F4F3EE", "#1F6B4E"
SUBE, BAJA = "#C4505A", "#2E8A66"


def _n(v: float, dec: int = 0) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _tramo(v: float) -> str:
    for desde, hasta, _, label in config.INDICE_TRAMOS:
        if desde <= v < hasta:
            return label
    return ""


def _cambio(v1, v0) -> tuple[str, str]:
    """Texto y color del cambio en la semana."""
    if v1 is None or v0 is None:
        return "", INK2
    d = v1 - v0
    if abs(d) < 0.05:
        return "sin cambios", INK2
    return f"{'↑' if d > 0 else '↓'} {_n(abs(d), 1)} pts", SUBE if d > 0 else BAJA


def _texto_plano(t: str) -> str:
    t = t.replace("</p>", "\n\n").replace("</li>", "\n").replace("<li>", "- ").replace("</h3>", "\n")
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def armar_mensaje(remitente: str, para: list[str], datos: Path | None = None) -> EmailMessage:
    d = json.loads((datos or config.OUTPUT_JSON).read_text(encoding="utf-8"))
    cl = d.get("claves") or {}
    if not cl.get("items"):
        raise SystemExit("No hay claves de la semana en los datos: corré monitor.build.")
    semana = cl.get("semana_txt") or cl.get("fecha", "")
    i1, i0 = cl.get("indice"), cl.get("indice_previo")
    camb, col = _cambio(i1, i0)

    m = EmailMessage()
    m["Subject"] = f"Dolarómetro · Las claves de la semana del {semana}"
    m["From"] = remitente
    m["To"] = remitente
    m["Bcc"] = ", ".join(para)

    plano = [f"DOLARÓMETRO · LAS CLAVES DE LA SEMANA DEL {semana.upper()}", ""]
    for it in cl["items"]:
        plano += [f"• {it['titular']}", f"  {it['bajada']}", ""]
    if i1 is not None:
        plano.append(f"Índice de Dolarización al cierre del viernes: {_n(i1, 1)}/100 ({_tramo(i1).lower()}), {camb} en la semana.")
    for b in (cl.get("bloques") or {}).values():
        if b.get("v1") is not None:
            plano.append(f"- {b['label']}: {_n(b['v1'], 1)}/100 ({_cambio(b['v1'], b.get('v0'))[0]})")
    if cl.get("texto"):
        plano += ["", "LA SEMANA", "", _texto_plano(cl["texto"])]
    plano += ["", f"El tablero, actualizado todos los días: {TABLERO}", "", "Fundar · fund.ar"]
    m.set_content("\n".join(plano))

    logo_cid = make_msgid(domain="fund.ar")
    claves_html = "".join(
        f"<tr><td style='padding:14px 0 12px;border-top:2px solid {INK}'>"
        f"<div style='font-size:17px;font-weight:700;line-height:1.3;color:{INK}'>{html.escape(it['titular'])}</div>"
        f"<div style='font-size:15px;line-height:1.45;color:{INK2};margin-top:4px'>{html.escape(it['bajada'])}</div></td></tr>"
        for it in cl["items"])
    subs = "".join(
        f"<td style='padding:10px 12px 0 0;vertical-align:top;width:33%'>"
        f"<div style='font-size:12px;color:{INK2}'>{html.escape(b['label'])}</div>"
        f"<div style='font-size:20px;font-weight:700;color:{INK}'>{_n(b['v1'], 1)}</div>"
        f"<div style='font-size:12px;font-weight:600;color:{_cambio(b['v1'], b.get('v0'))[1]}'>{_cambio(b['v1'], b.get('v0'))[0]}</div></td>"
        for b in (cl.get("bloques") or {}).values() if b.get("v1") is not None)
    indice = "" if i1 is None else (
        f"<tr><td style='padding:18px 0 4px;border-top:1px solid #D9D6CC'>"
        f"<div style='font-size:12px;color:{MUTED};text-transform:uppercase;letter-spacing:.1em'>Índice de Dolarización · cierre del viernes</div>"
        f"<div style='margin-top:4px'><span style='font-size:40px;font-weight:700;color:{INK}'>{_n(i1, 1)}</span>"
        f"<span style='font-size:15px;color:{MUTED}'>/100</span>"
        f"&nbsp;&nbsp;<span style='font-size:15px;font-weight:700;color:{col}'>{camb}</span>"
        f"&nbsp;<span style='font-size:13px;color:{INK2}'>respecto del viernes anterior · {html.escape(_tramo(i1))}</span></div>"
        f"<div style='font-size:12px;color:{MUTED};margin-top:2px'>0 = alivio · 50 = neutral · 100 = presión</div>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>{subs}</tr></table></td></tr>")
    texto = "" if not cl.get("texto") else (
        f"<tr><td style='padding:20px 0 0;border-top:1px solid #D9D6CC'>"
        f"<div style='font-size:12px;color:{VERDE};font-weight:700;text-transform:uppercase;letter-spacing:.1em'>La semana</div>"
        f"<div style='font-size:15px;line-height:1.55;color:#3A3A38'>{cl['texto']}</div></td></tr>")
    cuerpo = f"""<!doctype html><html lang="es"><body style="margin:0;padding:0;background:{PAGE}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif">
<tr><td style="background:{INK};border-radius:10px 10px 0 0;padding:20px 24px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
  <td><img src="cid:{logo_cid[1:-1]}" alt="Fundar" width="84" style="display:block;border:0"></td>
  <td align="right" style="color:#F2F2F2;font-size:20px;font-weight:700">Dolarómetro<div style="color:#BDBDBD;font-size:12px;font-weight:400">Presión cambiaria y demanda de cobertura</div></td>
  </tr></table></td></tr>
<tr><td style="background:{SURFACE};padding:22px 24px 24px;border-radius:0 0 10px 10px">
  <div style="font-size:12px;color:{MUTED};text-transform:uppercase;letter-spacing:.12em">Las claves de la semana | {html.escape(semana)}</div>
  <div style="font-size:26px;font-weight:700;font-style:italic;color:{INK};margin:4px 0 14px">El dólar, bajo la lupa</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{claves_html}{indice}{texto}
  <tr><td style="padding:24px 0 4px" align="left">
    <a href="{TABLERO}" style="display:inline-block;background:{INK};color:#F2F2F2;text-decoration:none;font-weight:700;font-size:15px;padding:12px 20px;border-radius:99px">Ver el Dolarómetro ↗</a>
    <div style="font-size:12px;color:{MUTED};margin-top:10px">El tablero se actualiza todos los días, con los 14 indicadores, sus gráficos y los datos para descargar.</div>
  </td></tr></table>
</td></tr>
<tr><td style="padding:14px 4px;font-size:12px;color:{MUTED}">Un proyecto de <b style="color:{INK}">Fundar</b> · fund.ar</td></tr>
</table></td></tr></table></body></html>"""
    m.add_alternative(cuerpo, subtype="html")
    if LOGO.exists():
        m.get_payload()[1].add_related(LOGO.read_bytes(), maintype="image", subtype="png", cid=logo_cid)
    return m


def enviar(m: EmailMessage, usuario: str, clave: str, host: str = "smtp.gmail.com", puerto: int = 587) -> None:
    with smtplib.SMTP(host, puerto, timeout=60) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(usuario, clave)
        s.send_message(m)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--para", help="destinatarios separados por coma (por defecto, REPORTE_PARA)")
    ap.add_argument("--dry-run", action="store_true", help="no envía: guarda el mail en reportes/ultimo.eml")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    usuario = os.environ.get("SMTP_USER", "")
    para = [x.strip() for x in (a.para or os.environ.get("REPORTE_PARA", "")).split(",") if x.strip()]
    if not para:
        raise SystemExit("Faltan destinatarios (--para o REPORTE_PARA).")
    m = armar_mensaje(usuario or "monitor@localhost", para)
    if a.dry_run:
        destino = config.ROOT / "reportes" / "ultimo.eml"
        destino.write_bytes(bytes(m))
        log.info("Mail armado (sin enviar): %s", destino)
        return
    clave = os.environ.get("SMTP_PASSWORD", "")
    if not usuario or not clave:
        raise SystemExit("Faltan SMTP_USER o SMTP_PASSWORD.")
    enviar(m, usuario, clave, os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "587")))
    log.info("Claves de la semana enviadas a %d destinatarios.", len(para))


if __name__ == "__main__":
    main()
