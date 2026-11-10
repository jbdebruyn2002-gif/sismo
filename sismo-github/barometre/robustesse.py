"""Solidité de l'échelle d'alerte et comparaison avec des règles naïves.

Deux questions qu'un jury pose immédiatement :
1. Les résultats tiennent-ils si l'on décale les seuils ? On refait le test sur une grille :
   seuils de niveau décalés de −5, 0 et +5 points, seuils de vitesse plus ou moins sensibles.
2. Sismo fait-il mieux qu'une règle simple ? On applique les mêmes mesures à :
   « VIX au-dessus de 25 », « courbe des taux américaine inversée » et « score sous 50 ».

Mêmes épisodes, même fenêtre d'anticipation (12 mois), mêmes mois calmes que le test sur le passé.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from . import alerte

SHIFTS = (-5.0, 0.0, 5.0)
DROP_SETS = ((-8.0, -4.0), (-10.0, -5.0), (-12.0, -6.0))   # plus sensible / référence / moins sensible


def _m(s: str) -> pd.Timestamp:
    return pd.Timestamp(s + "-01") + pd.offsets.MonthEnd(0)


def masks(index: pd.DatetimeIndex, episodes: list[dict], lead: int):
    crisis = pd.Series(False, index=index)
    useful = pd.Series(False, index=index)
    for e in episodes:
        s, t = _m(e["start"]), _m(e["end"])
        crisis |= (index >= s) & (index <= t)
        useful |= (index >= s - pd.offsets.MonthEnd(lead)) & (index <= t)
    return crisis, ~useful


def evaluate(signal: pd.Series, episodes: list[dict], lead: int, covered_from: pd.Timestamp) -> dict:
    """Part des mois de crise signalés, part des mois calmes signalés (fausses alertes), crises annoncées."""
    sig = signal.dropna().astype(bool)
    sig = sig[sig.index >= covered_from]
    if sig.empty:
        return dict(crisis=None, false=None, alerted=0, covered=0)
    crisis, calm = masks(sig.index, episodes, lead)
    alerted = covered = 0
    for e in episodes:
        s = _m(e["start"])
        if s - pd.offsets.MonthEnd(lead) < sig.index[0]:
            continue
        covered += 1
        w = sig.loc[s - pd.offsets.MonthEnd(lead): s]
        alerted += int(bool(w.any()))
    r = lambda m: round(100 * float(sig[m].mean()), 1) if m.any() else None
    return dict(crisis=r(crisis), false=r(calm), alerted=alerted, covered=covered)


def run(comp: pd.Series, episodes: list[dict], lead: int, threshold: float,
        vix: Optional[pd.Series] = None, curve: Optional[pd.Series] = None) -> dict:
    comp = comp.dropna()
    if comp.empty:
        return {}
    start = comp.index[0]
    grid = []
    for sh in SHIFTS:
        cuts = tuple(c + sh for c in alerte.CUTS)
        for drops in DROP_SETS:
            lv = alerte.series(comp, cuts=cuts, drops=drops)
            res = evaluate(lv >= alerte.ALERT_FROM, episodes, lead, start)
            grid.append(dict(shift=sh, drops=list(drops), **res))
    ref = next(g for g in grid if g["shift"] == 0 and g["drops"] == [-10.0, -5.0])
    naive = [dict(name="Sismo : échelle d'alerte (niveau 3 ou plus)", **ref),
             dict(name=f"Sismo : score sous {threshold:.0f}", **evaluate(comp < threshold, episodes, lead, start))]
    if vix is not None and len(vix.dropna()):
        v = vix.reindex(comp.index)
        naive.append(dict(name="VIX au-dessus de 25 (moyenne du mois)", **evaluate(v.where(v.notna()) > 25, episodes, lead, start)))
    if curve is not None and len(curve.dropna()):
        c = curve.reindex(comp.index)
        naive.append(dict(name="Courbe des taux américaine inversée (10 ans < 2 ans)", **evaluate(c.where(c.notna()) < 0, episodes, lead, start)))
    fs = [g["false"] for g in grid if g["false"] is not None]
    cs = [g["crisis"] for g in grid if g["crisis"] is not None]
    al = [g["alerted"] for g in grid]
    summary = dict(false_min=min(fs) if fs else None, false_max=max(fs) if fs else None,
                   crisis_min=min(cs) if cs else None, crisis_max=max(cs) if cs else None,
                   alerted_min=min(al), alerted_max=max(al), covered=ref["covered"])
    return dict(grid=grid, naive=naive, summary=summary)


def sentence(rb: dict) -> Optional[str]:
    if not rb or not rb.get("summary"):
        return None
    s = rb["summary"]
    return (f"Solidité : en décalant les seuils de niveau de ±5 points et en rendant la règle de vitesse plus ou moins "
            f"sensible (9 variantes), les fausses alertes restent entre {s['false_min']:.0f} et {s['false_max']:.0f} %, "
            f"et entre {s['alerted_min']} et {s['alerted_max']} crises sur {s['covered']} restent annoncées.")
