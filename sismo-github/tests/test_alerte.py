import pandas as pd

from barometre import alerte, resume


def test_levels_combine_score_and_speed():
    assert alerte.level(70, 0) == 0
    assert alerte.level(58, -9) == 2      # favorable mais chute de 5 à 10 points
    assert alerte.level(62, -13) == 3     # favorable mais chute rapide
    assert alerte.level(47, -8) == 3
    assert alerte.level(30, -15) == 4     # borné à 4
    assert alerte.level(55, 8) == 0       # remontée nette
    assert alerte.level(None, 0) is None
    assert alerte.level(60, None) == 1


def test_series_uses_three_month_change():
    s = pd.Series([70, 70, 70, 58], index=pd.date_range("2020-01-31", periods=4, freq="ME"), dtype=float)
    lv = alerte.series(s)
    assert lv.iloc[-1] == 3               # 58 (base 1) et −12 en 3 mois (+2)


def test_verdict_sentence_is_clear():
    al = alerte.describe(3)
    t = resume.verdict_sentence("Asie", 62.0, -13.0, al)
    assert t.startswith("Asie : alerte (niveau 3 sur 4).") and "13 points perdus" in t
    t2 = resume.verdict_sentence("États-Unis", 44.0, -8.0, alerte.describe(3))
    assert "devenues défavorables" in t2
