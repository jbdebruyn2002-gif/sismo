from datetime import date

from barometre import config, demo, resume
from barometre.scoring import compute

AS_OF = date(2026, 11, 2)


def fake(score=60.0, label="Plutôt favorable", change=None, inds=None):
    return {"composite": {"score": score, "label": label, "change_3m": change},
            "indicators": inds or [], "backtest": {"available": False}}


def ind(i, contrib, ch=0.0):
    return dict(id=i, label=i.upper(), available=True, contribution=contrib, change_3m=ch,
                plain_good=f"{i} va bien", plain_bad=f"{i} va mal")


def test_trend_words():
    assert resume.trend(5)[1] == "up" and resume.trend(-5)[1] == "down" and resume.trend(1)[1] == "flat"
    assert resume.trend(None)[0] == "évolution inconnue"


def test_helps_and_hurts_sorted_and_limited():
    s = resume.build(fake(inds=[ind("a", 3), ind("b", 5), ind("c", 0.2), ind("d", -4), ind("e", -1), ind("f", 2), ind("g", 1)]), "Europe")
    assert [h["id"] for h in s["helps"]] == ["b", "a", "f"]          # 3 maximum, du plus fort au plus faible
    assert [h["id"] for h in s["hurts"]] == ["d", "e"]
    assert s["helps"][0]["text"] == "B va bien" and s["hurts"][0]["text"] == "D va mal"
    assert all(h["id"] != "c" for h in s["helps"])                    # contribution trop faible : pas citée


def test_headline_and_watch():
    s = resume.build(fake(label="Prudent", change=-6, inds=[ind("a", -1, ch=-25), ind("b", 1, ch=-4)]), "Asie")
    assert s["headline"] == "Asie : conditions fragiles, prudence, en dégradation sur 3 mois."
    assert [w["id"] for w in s["watch"]] == ["a"]


def test_real_zones_produce_summary():
    raw = demo.make_raw(AS_OF)
    for z in config.ZONE_IDS:
        res = compute(raw, AS_OF, config.indicators_for(z), episodes=config.episodes_for(z))
        s = resume.build(res, config.zone_info(z)["label"])
        assert s["headline"].startswith(config.zone_info(z)["label"])
        assert s["reliability"] and "crises testées" in s["reliability"]
        assert all(i["plain_good"] and i["plain_bad"] for i in res["indicators"])
