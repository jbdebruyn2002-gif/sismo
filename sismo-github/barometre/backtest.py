"""Test sur le passé : le score baissait-il avant et pendant les crises connues ?

Le score de chaque mois est calculé uniquement avec les données disponibles à ce moment
(fenêtre de normalisation glissante, délais de publication). Les dates des épisodes sont
fixées à l'avance dans config.EPISODES, et non choisies d'après le score.

Limite à citer : FRED fournit les séries révisées (PIB, inflation). Un vrai test en temps réel
utiliserait les données telles que publiées à l'époque (base ALFRED).
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from .config import ALERT_THRESHOLD, EPISODES, LEAD_MONTHS


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, 2)


def _month(s: str) -> pd.Timestamp:
    return pd.Timestamp(s + "-01") + pd.offsets.MonthEnd(0)


def episode_stats(comp: pd.Series, equal: pd.Series, ep: dict) -> dict:
    start, end = _month(ep["start"]), _month(ep["end"])
    before_t = start - pd.offsets.MonthEnd(LEAD_MONTHS)
    out = dict(name=ep["name"], short=ep["short"], start=start.date().isoformat(), end=end.date().isoformat(),
               source=ep["source"], covered=False)
    during = comp.loc[start:end].dropna()
    if during.empty or pd.isna(comp.get(before_t)):
        return out
    lead_window = comp.loc[before_t:start]
    below = lead_window[lead_window < ALERT_THRESHOLD]
    lead = None
    if len(below):
        first = below.index[0]
        lead = (start.year - first.year) * 12 + (start.month - first.month)
    eq_during = equal.loc[start:end].dropna()
    t_min = during.idxmin()
    out.update(
        covered=True,
        score_before=_f(comp.loc[before_t]),
        score_start=_f(comp.loc[start]),
        score_min=_f(during.min()),
        min_date=t_min.date().isoformat(),
        drop=_f(during.min() - comp.loc[before_t]),
        lead_months=lead,
        signaled=lead is not None,
        eq_before=_f(equal.get(before_t)),
        eq_min=_f(eq_during.min()) if len(eq_during) else None,
    )
    return out


def run(comp: pd.Series, equal: pd.Series, episodes: list[dict] = EPISODES) -> dict:
    comp = comp.dropna()
    equal = equal.reindex(comp.index)
    if comp.empty:
        return dict(available=False)
    eps = [episode_stats(comp, equal, e) for e in episodes]

    # Mois « en crise » = pendant un épisode ; « zone d'alerte utile » = pendant ou dans les LEAD_MONTHS avant.
    in_crisis = pd.Series(False, index=comp.index)
    useful = pd.Series(False, index=comp.index)
    for e in episodes:
        s, t = _month(e["start"]), _month(e["end"])
        in_crisis |= (comp.index >= s) & (comp.index <= t)
        useful |= (comp.index >= s - pd.offsets.MonthEnd(LEAD_MONTHS)) & (comp.index <= t)
    alert = comp < ALERT_THRESHOLD
    calm = ~useful
    covered = [e for e in eps if e["covered"]]
    summary = dict(
        months=int(len(comp)),
        first=comp.index[0].date().isoformat(),
        mean_crisis=_f(comp[in_crisis].mean()) if in_crisis.any() else None,
        mean_calm=_f(comp[calm].mean()) if calm.any() else None,
        alert_share_crisis=_f(100 * alert[in_crisis].mean()) if in_crisis.any() else None,
        false_alert_share=_f(100 * alert[calm].mean()) if calm.any() else None,
        episodes_covered=len(covered),
        episodes_signaled=sum(1 for e in covered if e["signaled"]),
        threshold=ALERT_THRESHOLD, lead_months=LEAD_MONTHS,
    )
    history = [[t.date().isoformat(), _f(comp.loc[t]), _f(equal.loc[t])] for t in comp.index]
    return dict(available=True, summary=summary, episodes=eps, history=history, commentary=commentary(summary, eps))


def commentary(sm: dict, eps: list[dict]) -> list[str]:
    out = []
    cov = [e for e in eps if e["covered"]]
    if not cov:
        return ["Historique trop court : aucun épisode de crise n'est couvert par le score."]
    out.append(f"{sm['episodes_signaled']} épisode(s) sur {sm['episodes_covered']} couverts ont été précédés d'un score "
               f"sous {sm['threshold']} dans les {sm['lead_months']} mois avant leur début.")
    if sm["mean_crisis"] is not None and sm["mean_calm"] is not None:
        out.append(f"Score moyen pendant les crises : {sm['mean_crisis']:.0f}/100, contre {sm['mean_calm']:.0f}/100 "
                   f"en période calme (écart {sm['mean_crisis'] - sm['mean_calm']:+.0f} points).")
    if sm["false_alert_share"] is not None:
        out.append(f"Fausses alertes : le score est sous {sm['threshold']} pendant {sm['false_alert_share']:.0f} % "
                   f"des mois calmes (loin de toute crise).")
    worst = min(cov, key=lambda e: e["score_min"])
    out.append(f"Point le plus bas atteint pendant une crise : {worst['name']}, {worst['score_min']:.0f}/100.")
    missed = [e["short"] for e in cov if not e["signaled"]]
    if missed:
        out.append("Non signalés à l'avance : " + ", ".join(missed) + " (le score a pu baisser pendant l'épisode seulement).")
    uncovered = [e["short"] for e in eps if not e["covered"]]
    if uncovered:
        out.append("Hors de l'historique disponible : " + ", ".join(uncovered) + ".")
    return out
