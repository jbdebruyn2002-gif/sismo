"""Résumé « En bref » : ce que dit le baromètre, en phrases simples, à partir des chiffres calculés.

Règles fixes (pas d'intelligence artificielle) : chaque phrase se retrouve dans les chiffres de la page.
"""
from __future__ import annotations

from typing import Optional

VERDICT = {
    "Défavorable": "conditions défavorables",
    "Prudent": "conditions fragiles, prudence",
    "Plutôt favorable": "conditions plutôt favorables",
    "Favorable": "conditions favorables",
}
TREND_POINTS = 3      # au-delà de ± 3 points sur 3 mois, on parle d'amélioration ou de dégradation
DROP_ALERT = 10       # un indicateur qui perd plus de 10 points en 3 mois est « à surveiller »
MIN_CONTRIB = 0.5     # contribution minimale (en points) pour être cité


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def trend(change_3m: Optional[float]) -> tuple[str, str]:
    """(mot, sens) : sens = up / down / flat."""
    if change_3m is None:
        return "évolution inconnue", "flat"
    if change_3m > TREND_POINTS:
        return "en amélioration", "up"
    if change_3m < -TREND_POINTS:
        return "en dégradation", "down"
    return "stables", "flat"


def build(res: dict, zone_label: str) -> dict:
    c = res["composite"]
    avail = [i for i in res["indicators"] if i["available"]]
    word, direction = trend(c.get("change_3m"))
    verdict = VERDICT.get(c["label"], c["label"].lower())
    headline = f"{zone_label} : {verdict}, {word} sur 3 mois."

    helps = sorted([i for i in avail if i["contribution"] > MIN_CONTRIB], key=lambda i: -i["contribution"])[:3]
    hurts = sorted([i for i in avail if i["contribution"] < -MIN_CONTRIB], key=lambda i: i["contribution"])[:3]
    falling = [i for i in avail if i.get("change_3m") is not None and i["change_3m"] < -DROP_ALERT]
    falling.sort(key=lambda i: i["change_3m"])

    watch = [dict(id=i["id"], text=f"{i['label']} : {abs(i['change_3m']):.0f} points perdus en 3 mois") for i in falling[:2]]

    bt = res.get("backtest") or {}
    reliability = None
    if bt.get("available") and bt["summary"]["episodes_covered"]:
        sm = bt["summary"]
        reliability = (f"Sur le passé, ce score est passé sous {sm['threshold']} avant {sm['episodes_signaled']} des "
                       f"{sm['episodes_covered']} crises testées, avec {sm['false_alert_share']:.0f} % de fausses alertes.")

    return dict(
        headline=headline, verdict=_cap(verdict), trend=word, direction=direction,
        helps=[dict(id=i["id"], text=_cap(i["plain_good"] or i["label"]), points=round(i["contribution"], 1)) for i in helps],
        hurts=[dict(id=i["id"], text=_cap(i["plain_bad"] or i["label"]), points=round(i["contribution"], 1)) for i in hurts],
        watch=watch, reliability=reliability,
    )
