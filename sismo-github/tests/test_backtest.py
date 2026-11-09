from datetime import date

import pandas as pd

from barometre import backtest, demo
from barometre.scoring import ME, compute

EP = [dict(name="Crise test", short="T", start="2010-01", end="2010-06", source="test")]


def series(values, start="2008-01-31"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=ME), dtype=float)


def test_signal_detected_with_lead_time():
    # 60 partout, puis sous 50 à partir de 2009-07 : 6 mois avant le début de la crise (2010-01)
    v = [60.0] * 18 + [45.0] * 30
    s = series(v)
    res = backtest.run(s, s, EP)
    e = res["episodes"][0]
    assert e["covered"] and e["signaled"]
    assert e["lead_months"] == 6
    assert e["score_min"] == 45.0
    assert e["score_before"] == 60.0       # 12 mois avant : 2009-01
    assert e["drop"] == -15.0


def test_no_signal_when_score_stays_high():
    s = series([70.0] * 48)
    e = backtest.run(s, s, EP)["episodes"][0]
    assert e["covered"] and not e["signaled"] and e["lead_months"] is None


def test_episode_outside_history_is_not_covered():
    s = series([60.0] * 12, start="2015-01-31")
    res = backtest.run(s, s, EP)
    assert res["episodes"][0]["covered"] is False
    assert res["summary"]["episodes_covered"] == 0
    assert "Historique trop court" in res["commentary"][0]


def test_false_alerts_counted_only_far_from_crises():
    v = [40.0] * 6 + [70.0] * 42            # alertes en 2008 seulement, hors de la zone d'anticipation
    s = series(v)
    sm = backtest.run(s, s, EP)["summary"]
    assert sm["false_alert_share"] > 0
    assert sm["alert_share_crisis"] == 0


def test_compute_includes_full_history_backtest():
    res = compute(demo.make_raw(date(2026, 11, 2)), date(2026, 11, 2))
    bt = res["backtest"]
    assert bt["available"]
    assert len(bt["history"]) > len(res["composite"]["history"])   # tout l'historique, pas seulement 6 ans
    assert bt["history"][-1][1] == round(res["composite"]["score"], 2)
    assert {e["short"] for e in bt["episodes"]} >= {"2008", "2020"}
