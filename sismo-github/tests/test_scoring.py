from datetime import date

import numpy as np
import pandas as pd
import pytest

from barometre import config, demo, scoring
from barometre.scoring import ME, compute, normalize, regime, to_monthly, transform

AS_OF = date(2026, 11, 2)


def monthly(values, start="2012-01-31"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=ME))


# ---------------------------------------------------------------- configuration
def test_weights_sum_to_one_and_config_valid():
    config.check_config()
    assert sum(i["weight"] for i in config.INDICATORS) == pytest.approx(1.0)
    assert len(config.INDICATORS) >= 5            # exigence du sujet
    assert len({i["family"] for i in config.INDICATORS}) >= 5


# ---------------------------------------------------------------- normalisation
def test_minmax_in_range_and_monotone():
    x = monthly(np.linspace(0, 10, 100))
    s = normalize(x, {"method": "minmax"})
    assert s.dropna().between(0, 100).all()
    assert s.dropna().iloc[-1] > 95                       # nouveau plus haut = score proche de 100
    assert s.dropna().is_monotonic_increasing or s.dropna().iloc[-1] >= s.dropna().iloc[0]


def test_minmax_invert_flips_scale():
    x = monthly(np.linspace(0, 10, 100))
    a = normalize(x, {"method": "minmax"})
    b = normalize(x, {"method": "minmax", "invert": True})
    assert (a + b).dropna().eq(100).all()


def test_zscore_centered_on_50_and_clipped():
    rng = np.random.default_rng(1)
    x = monthly(rng.normal(5, 2, 120))
    s = normalize(x, {"method": "zscore"}).dropna()
    assert s.between(0, 100).all() and 35 < s.mean() < 65
    spike = monthly(list(rng.normal(0, 1, 100)) + [50.0])
    assert normalize(spike, {"method": "zscore"}).iloc[-1] == 100


def test_target_method():
    cfg = {"method": "target", "target": 2.0, "tolerance": 4.0}
    s = normalize(monthly([2.0, 3.0, 6.0, 10.0, -2.0, 0.0]), cfg)
    assert list(s.round(6)) == [100.0, 75.0, 0.0, 0.0, 0.0, 50.0]
    assert normalize(monthly([3.0]), {**cfg, "invert": True}).iloc[0] == 75      # invert est ignoré pour une cible


def test_normalization_does_not_look_ahead():
    """Le score d'un mois ne change pas quand on ajoute des mois futurs."""
    rng = np.random.default_rng(3)
    full = monthly(rng.normal(0, 1, 150).cumsum())
    cfg = {"method": "zscore"}
    assert normalize(full, cfg).iloc[99] == pytest.approx(normalize(full.iloc[:100], cfg).iloc[99])
    cfg = {"method": "minmax"}
    assert normalize(full, cfg).iloc[99] == pytest.approx(normalize(full.iloc[:100], cfg).iloc[99])


def test_too_little_history_gives_no_score():
    assert normalize(monthly(np.arange(20.0)), {"method": "zscore"}).isna().all()


# ---------------------------------------------------------------- mise au pas mensuel
def test_publication_lag_blocks_unpublished_data():
    q = pd.Series([100.0, 101.0, 102.0], index=pd.to_datetime(["2026-01-01", "2026-04-01", "2026-07-01"]))
    m = to_monthly(q, {"lag_months": 3, "agg": "last"}, AS_OF)
    # le PIB du T3 (daté 1er juillet) n'est disponible que fin octobre ; celui du T2 depuis fin juillet
    assert m.loc["2026-09-30"] == 101.0
    assert m.loc["2026-10-31"] == 102.0
    assert m.loc["2026-11-30"] == 102.0
    q2 = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-01-01", "2026-04-01"]))
    assert to_monthly(q2, {"lag_months": 3, "agg": "last"}, AS_OF).loc["2026-10-31"] == 101.0


def test_monthly_aggregation_and_ffill():
    d = pd.Series([1.0, 3.0, 10.0], index=pd.to_datetime(["2026-08-03", "2026-08-20", "2026-10-05"]))
    assert to_monthly(d, {"agg": "mean"}, AS_OF).loc["2026-08-31"] == 2.0
    assert to_monthly(d, {"agg": "last"}, AS_OF).loc["2026-09-30"] == 3.0       # mois sans donnée : report


def test_pct12():
    m = monthly(np.arange(1.0, 30.0))
    assert transform(m, {"transform": "pct12"}).iloc[12] == pytest.approx((13 / 1 - 1) * 100)


# ---------------------------------------------------------------- score global
@pytest.fixture(scope="module")
def result():
    return compute(demo.make_raw(AS_OF), AS_OF)


def test_composite_is_between_0_and_100_and_labelled(result):
    c = result["composite"]
    assert 0 <= c["score"] <= 100
    assert c["label"] == regime(c["score"])[0]
    assert c["history"] and all(0 <= h[1] <= 100 for h in c["history"])
    assert c["history"][-1][0] == AS_OF.isoformat()


def test_contributions_add_up_to_score_minus_50(result):
    inds = [i for i in result["indicators"] if i["available"]]
    assert sum(i["contribution"] for i in inds) == pytest.approx(result["composite"]["score"] - 50, abs=0.05)
    assert sum(i["weight_effective"] for i in inds) == pytest.approx(1.0, abs=0.01)


def test_composite_equals_weighted_mean(result):
    inds = [i for i in result["indicators"] if i["available"]]
    expected = sum(i["weight_effective"] * i["score"] for i in inds)
    assert result["composite"]["score"] == pytest.approx(expected, abs=0.05)


def test_missing_indicator_redistributes_weight():
    raw = demo.make_raw(AS_OF)
    del raw["DCOILBRENTEU"]
    res = compute(raw, AS_OF)
    oil = next(i for i in res["indicators"] if i["id"] == "oil")
    assert oil["available"] is False and oil["contribution"] is None
    assert sum(i["weight_effective"] for i in res["indicators"] if i["available"]) == pytest.approx(1.0, abs=0.01)
    assert any("Pétrole" in line for line in res["commentary"])


def test_too_many_missing_indicators_gives_error():
    raw = demo.make_raw(AS_OF)
    for k in ("SP500", "VIXCLS", "NFCI", "GDPC1", "T10Y2Y"):
        del raw[k]
    with pytest.raises(ValueError):
        compute(raw, AS_OF, config.indicators_for("us"))


def test_no_data_gives_error():
    with pytest.raises(ValueError):
        compute({}, AS_OF)


def test_good_conditions_score_higher_than_bad():
    good, bad = demo.make_raw(AS_OF, seed=1), demo.make_raw(AS_OF, seed=1)
    good["VIXCLS"] = good["VIXCLS"] * 0 + np.linspace(30, 11, len(good["VIXCLS"]))     # volatilité qui s'apaise
    bad["VIXCLS"] = bad["VIXCLS"] * 0 + np.linspace(11, 45, len(bad["VIXCLS"]))        # volatilité qui explose
    g = next(i for i in compute(good, AS_OF)["indicators"] if i["id"] == "vol")["score"]
    b = next(i for i in compute(bad, AS_OF)["indicators"] if i["id"] == "vol")["score"]
    assert g > 80 and b < 20


def test_result_is_json_serializable(result):
    import json
    json.dumps(result)


def test_regime_boundaries():
    assert regime(0)[0] == "Défavorable" and regime(34.9)[0] == "Défavorable"
    assert regime(35)[0] == "Prudent" and regime(50)[0] == "Plutôt favorable" and regime(65)[0] == "Favorable"
    assert regime(100)[0] == "Favorable"


def test_commentary_mentions_robustness_and_drivers(result):
    text = " ".join(result["commentary"])
    assert "Score global" in text and "poids égaux" in text and "Poids le plus élevé" in text


def test_drivers_sum_exactly_to_three_month_change():
    from barometre import config
    res = compute(demo.make_raw(date(2026, 11, 2)), date(2026, 11, 2), config.indicators_for("global"))
    c = res["composite"]
    assert c["drivers_3m"]
    assert abs(sum(d["points"] for d in c["drivers_3m"]) - c["change_3m"]) < 0.05
    assert len(c["history"][-1]) == 4 and c["history"][-1][3] in range(5)
