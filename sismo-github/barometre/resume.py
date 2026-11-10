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


# Désignation courte de chaque indicateur, avec sa préposition (« dus au pétrole »).
SHORT = {
    "gdp": "à la croissance américaine", "cpi": "à l'inflation américaine", "equity": "à la Bourse américaine",
    "curve": "à la courbe des taux américaine", "stress": "aux conditions financières américaines",
    "vol": "à la volatilité (VIX)", "oil": "au pétrole", "usd": "au dollar",
    "ea_gdp": "à la croissance européenne", "ea_cpi": "à l'inflation européenne",
    "ea_spread": "à l'écart de taux Italie-Allemagne", "ea_curve": "à la courbe des taux européenne",
    "jp_gdp": "à la croissance japonaise", "nikkei": "à la Bourse de Tokyo",
    "jp_curve": "à la courbe des taux japonaise", "cny": "au yuan",
    "de_equity": "à la Bourse allemande", "kr_equity": "à la Bourse coréenne", "in_equity": "à la Bourse indienne",
    "krw": "au won", "em_usd": "au dollar face aux devises émergentes", "em_vol": "à la volatilité émergente",
    "copper": "au cuivre", "brl": "au réal brésilien", "mxn": "au peso mexicain", "inr": "à la roupie",
}
MIN_MOVE = 0.3   # en dessous, une contribution à la variation n'est pas citée


def _fr(v: float) -> str:
    return f"{v:+.1f}".replace(".", ",").replace("-", "−")


def move_sentence(total: Optional[float], drivers: list[dict]) -> Optional[str]:
    """« −9 points en 3 mois, dont −2,7 dus au pétrole et −2,1 à la Bourse de Tokyo. »"""
    if total is None or not drivers:
        return None
    same = [d for d in drivers if abs(d["points"]) >= MIN_MOVE and (d["points"] < 0) == (total < 0)]
    same.sort(key=lambda d: -abs(d["points"]))
    if abs(total) < 0.5 or not same:
        return f"Le score est stable sur 3 mois ({_fr(total)} point)."
    parts = [f"{_fr(d['points'])} dus {SHORT.get(d['id'], 'à ' + d['label'])}" for d in same[:3]]
    lst = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " et " + parts[-1]
    verb = "perdus" if total < 0 else "gagnés"
    n = abs(total)
    return f"{n:.0f} point{'s' if round(n) > 1 else ''} {verb} en 3 mois, dont {lst}."


def verdict_sentence(zone: str, score: float, d3: Optional[float], al: dict) -> str:
    """Verdict tranché : niveau d'alerte, puis niveau et vitesse du score en clair."""
    sc = round(score)
    pts = "" if d3 is None else f"{abs(d3):.0f} point{'s' if abs(round(d3)) > 1 else ''}"
    head = f"{zone} : {al['label'].lower()} (niveau {al['level']} sur 4)."
    if d3 is None:
        body = f"Score de {sc}/100."
    elif sc >= 50 and d3 <= -5:
        body = f"Les conditions restent favorables ({sc}/100) mais se dégradent vite : {pts} perdus en 3 mois."
    elif sc < 50 and d3 <= -5:
        body = f"Les conditions sont devenues défavorables ({sc}/100) et continuent de se dégrader : {pts} perdus en 3 mois."
    elif sc < 50 and d3 >= 5:
        body = f"Les conditions restent défavorables ({sc}/100) mais s'améliorent : {pts} gagnés en 3 mois."
    elif sc < 50:
        body = f"Les conditions sont défavorables ({sc}/100) et ne s'améliorent pas."
    elif d3 >= 5:
        body = f"Les conditions sont favorables ({sc}/100) et s'améliorent : {pts} gagnés en 3 mois."
    else:
        body = f"Les conditions sont favorables ({sc}/100) et stables."
    return f"{head} {body}"


def build(res: dict, zone_label: str) -> dict:
    c = res["composite"]
    avail = [i for i in res["indicators"] if i["available"]]
    word, direction = trend(c.get("change_3m"))
    verdict = VERDICT.get(c["label"], c["label"].lower())
    al = c.get("alert")
    headline = verdict_sentence(zone_label, c["score"], c.get("change_3m"), al) if al else f"{zone_label} : {verdict}, {word} sur 3 mois."

    helps = sorted([i for i in avail if i["contribution"] > MIN_CONTRIB], key=lambda i: -i["contribution"])[:3]
    hurts = sorted([i for i in avail if i["contribution"] < -MIN_CONTRIB], key=lambda i: i["contribution"])[:3]
    falling = [i for i in avail if i.get("change_3m") is not None and i["change_3m"] < -DROP_ALERT]
    falling.sort(key=lambda i: i["change_3m"])

    watch = [dict(id=i["id"], text=f"{i['label']} : {abs(i['change_3m']):.0f} points perdus en 3 mois") for i in falling[:2]]

    bt = res.get("backtest") or {}
    reliability = None
    if bt.get("available") and bt["summary"]["episodes_covered"]:
        sm = bt["summary"]
        if sm.get("alert_share_crisis_lvl") is not None:
            reliability = (f"Sur le passé, le niveau Alerte (3 ou plus) a été atteint pendant {sm['alert_share_crisis_lvl']:.0f} % "
                           f"des mois de crise, contre {sm['alert_false_share_lvl']:.0f} % des mois calmes, et il a précédé "
                           f"{sm['episodes_alerted']} des {sm['episodes_covered']} crises testées.")
        else:
            reliability = (f"Sur le passé, ce score est passé sous {sm['threshold']} avant {sm['episodes_signaled']} des "
                           f"{sm['episodes_covered']} crises testées, avec {sm['false_alert_share']:.0f} % de fausses alertes.")

    return dict(
        headline=headline, verdict=_cap(verdict), trend=word, direction=direction,
        meaning=al["meaning"] if al else None,
        move=move_sentence(c.get("change_3m"), c.get("drivers_3m") or []),
        drivers=[d for d in (c.get("drivers_3m") or []) if abs(d["points"]) >= MIN_MOVE],
        helps=[dict(id=i["id"], text=_cap(i["plain_good"] or i["label"]), points=round(i["contribution"], 1)) for i in helps],
        hurts=[dict(id=i["id"], text=_cap(i["plain_bad"] or i["label"]), points=round(i["contribution"], 1)) for i in hurts],
        watch=watch, reliability=reliability,
    )
