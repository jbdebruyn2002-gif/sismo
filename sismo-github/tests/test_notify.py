import json

from barometre import notify


def data(levels: dict) -> dict:
    labels = ["Calme", "Secousses légères", "Vigilance", "Alerte", "Séisme"]
    return {"zones": [{"id": z, "label": z.upper(), "as_of": "2026-11-10",
                       "composite": {"score": 50.0, "alert": {"level": lv, "label": labels[lv]}},
                       "summary": {"move": "9 points perdus en 3 mois, dont −2,7 dus au pétrole."}}
                      for z, lv in levels.items()]}


def write(path, d):
    path.write_text("window.BAROMETRE = " + json.dumps(d, ensure_ascii=False) + ";", encoding="utf-8")


def test_no_message_when_levels_unchanged(tmp_path):
    write(tmp_path / "a.js", data({"global": 2, "us": 3}))
    write(tmp_path / "b.js", data({"global": 2, "us": 3}))
    notify.main([str(tmp_path / "a.js"), str(tmp_path / "b.js"), str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()


def test_message_on_level_change(tmp_path):
    write(tmp_path / "a.js", data({"global": 2, "us": 3, "eu": 2}))
    write(tmp_path / "b.js", data({"global": 3, "us": 4, "eu": 2}))
    notify.main([str(tmp_path / "a.js"), str(tmp_path / "b.js"), str(tmp_path / "out"), "https://exemple.netlify.app"])
    title = (tmp_path / "out" / "titre.txt").read_text(encoding="utf-8")
    body = (tmp_path / "out" / "message.md").read_text(encoding="utf-8")
    assert title == "Sismo : US passe en séisme (4/4) et 1 autre(s) changement(s)"
    assert "Alerte (3/4) → **Séisme (4/4)**" in body and "dus au pétrole" in body and "exemple.netlify.app" in body
    assert "EU" not in body


def test_missing_old_file_is_harmless(tmp_path):
    write(tmp_path / "b.js", data({"global": 3}))
    assert notify.main([str(tmp_path / "absent.js"), str(tmp_path / "b.js"), str(tmp_path / "out")]) == 0
    assert not (tmp_path / "out").exists()
