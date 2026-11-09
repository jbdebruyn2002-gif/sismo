from datetime import date

import pandas as pd
import pytest

from barometre import collect, config, demo
from barometre.scoring import compute, source_series

AS_OF = date(2026, 11, 2)


@pytest.fixture(scope="module")
def results():
    raw = demo.make_raw(AS_OF)
    return {z: compute(raw, AS_OF, config.indicators_for(z), episodes=config.episodes_for(z)) for z in config.ZONE_IDS}


def test_each_zone_weights_sum_to_one():
    for z in config.ZONE_IDS:
        assert sum(i["weight"] for i in config.indicators_for(z)) == pytest.approx(1.0)


def test_each_zone_has_own_indicators():
    assert {i["zone"] for i in config.indicators_for("eu")} >= {"Zone euro"}
    assert {i["zone"] for i in config.indicators_for("asia")} >= {"Japon", "Chine"}
    assert all(i["zone"] != "Zone euro" for i in config.indicators_for("us"))
    # indicateurs propres à la zone affichés avant les indicateurs mondiaux
    zones = [i["zone"] for i in config.indicators_for("eu")]
    assert zones.index("Monde") > zones.index("Zone euro")


def test_global_is_mix_of_zone_scores(results):
    expected = sum(config.GLOBAL_MIX[z] * results[z]["composite"]["score"] for z in config.GLOBAL_MIX)
    assert results["global"]["composite"]["score"] == pytest.approx(expected, abs=0.05)


def test_episodes_filtered_by_zone(results):
    shorts = lambda z: {e["short"] for e in results[z]["backtest"]["episodes"]}
    assert "2015" in shorts("asia") and "2015" not in shorts("us")
    assert "2001" in shorts("us") and "2001" not in shorts("eu")


def test_spread_is_difference_of_two_series():
    idx = pd.date_range("2020-01-01", periods=3, freq="MS")
    raw = {"A": pd.Series([5.0, 6.0, 7.0], index=idx), "B": pd.Series([2.0, 2.5, 3.0], index=idx)}
    s = source_series(raw, {"series": "A", "minus": "B"})
    assert list(s.values) == [3.0, 3.5, 4.0]
    assert source_series({"A": raw["A"]}, {"series": "A", "minus": "B"}) is None   # une jambe manquante


def test_collect_downloads_both_legs_of_a_spread():
    ids = collect.series_ids(config.CATALOG)
    assert "IRLTLT01ITM156N" in ids and "IRLTLT01DEM156N" in ids and "ECBDFR" in ids
    assert len(ids) == len(set(ids))


def test_stale_series_is_excluded():
    from barometre.scoring import stale_reason
    idx = pd.date_range("2015-01-01", "2021-06-01", freq="MS")
    old = pd.Series(range(len(idx)), index=idx, dtype=float)
    assert stale_reason(old, {"freq": "mensuelle"}, AS_OF) is not None
    fresh = pd.Series([1.0], index=[pd.Timestamp("2026-09-01")])
    assert stale_reason(fresh, {"freq": "mensuelle"}, AS_OF) is None


def test_spread_of_monthly_and_daily_series_uses_monthly_means():
    m = pd.Series([3.0, 3.2], index=pd.date_range("2026-01-01", periods=2, freq="MS"))
    d = pd.Series([2.0] * 31 + [2.5] * 28, index=pd.date_range("2026-01-01", periods=59, freq="D"))
    s = source_series({"A": m, "B": d}, {"series": "A", "minus": "B"})
    assert list(s.round(6).values) == [1.0, 0.7]
