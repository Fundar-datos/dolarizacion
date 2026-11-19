from monitor import claves


def _semana(i1=47.7, i0=46.9):
    return {
        "i1": i1, "i0": i0,
        "componentes": {"reservas": -2.0, "vol_ccl": 0.8},
        "bloques": {
            "cambiaria": {"label": "Presión cambiaria", "v1": 44, "v0": 43},
            "dolarizacion": {"label": "Dolarización de portafolios", "v1": 26, "v0": 29},
            "extranjerizacion": {"label": "Extranjerización de portafolios", "v1": 68, "v0": 65},
        },
    }


def test_claves_automaticas(tmp_path):
    c = claves.generar("2026-11-13", _semana(45.0, 48.0), dir_=tmp_path)
    assert c["origen"] == "automatico" and c["semana_txt"] == "9 al 13 de noviembre"
    tit = [i["titular"] for i in c["items"]]
    assert tit[0] == "Se amplía el alivio sobre el peso."
    assert tit[1] == "Las reservas subieron."  # bajó el índice: lo explica la suba de reservas
    assert any("demanda de cobertura" in t for t in tit)
    assert any("activos argentinos" in t for t in tit)
    assert 3 <= len(c["items"]) <= 4


def test_etiqueta_semana_entre_meses():
    assert claves.etiqueta_semana("2026-10-02") == "28 de septiembre al 2 de octubre"


def test_claves_editoriales(tmp_path):
    (tmp_path / "2026-11-15.md").write_text("<!-- nota -->\n**Se modera la presión.** El índice bajó.\n\n**Segunda.** Texto\nen dos líneas.\n", encoding="utf-8")
    (tmp_path / "2026-11-06.md").write_text("**De la semana anterior.** No va.\n", encoding="utf-8")
    c = claves.generar("2026-11-13", _semana(), dir_=tmp_path)
    assert c["origen"] == "editorial" and c["fecha"] == "2026-11-13"
    assert c["items"] == [{"titular": "Se modera la presión.", "bajada": "El índice bajó."},
                          {"titular": "Segunda.", "bajada": "Texto en dos líneas."}]
