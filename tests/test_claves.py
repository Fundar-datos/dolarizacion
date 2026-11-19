from monitor import claves


def _payload(i1=47.7, i0=46.9):
    return {
        "headline": {"date": "2026-11-19", "indice": i1, "indice_7d": i0},
        "ipd": {
            "components": [
                {"key": "reservas", "cambio_semana": -2.0},
                {"key": "vol_ccl", "cambio_semana": 0.8},
            ],
            "blocks": {
                "cambiaria": {"label": "Presión cambiaria", "indice_last": 44, "indice_7d": 43},
                "dolarizacion": {"label": "Dolarización de portafolios", "indice_last": 26, "indice_7d": 29},
                "extranjerizacion": {"label": "Extranjerización de portafolios", "indice_last": 68, "indice_7d": 65},
            },
        },
    }


def test_claves_automaticas(tmp_path):
    c = claves.generar(_payload(45.0, 48.0), dir_=tmp_path)
    assert c["origen"] == "automatico" and c["fecha_txt"] == "19 de noviembre"
    tit = [i["titular"] for i in c["items"]]
    assert tit[0] == "Se amplía el alivio sobre el peso."
    assert tit[1] == "Las reservas subieron."  # bajó el índice: lo explica la suba de reservas
    assert any("demanda de cobertura" in t for t in tit)
    assert any("activos argentinos" in t for t in tit)
    assert 3 <= len(c["items"]) <= 4


def test_claves_editoriales(tmp_path):
    (tmp_path / "2026-11-17.md").write_text("<!-- nota -->\n**Se modera la presión.** El índice bajó.\n\n**Segunda.** Texto\nen dos líneas.\n", encoding="utf-8")
    (tmp_path / "2026-11-01.md").write_text("**Vieja.** No va.\n", encoding="utf-8")
    c = claves.generar(_payload(), dir_=tmp_path)
    assert c["origen"] == "editorial" and c["fecha"] == "2026-11-17"
    assert c["items"] == [{"titular": "Se modera la presión.", "bajada": "El índice bajó."},
                          {"titular": "Segunda.", "bajada": "Texto en dos líneas."}]
