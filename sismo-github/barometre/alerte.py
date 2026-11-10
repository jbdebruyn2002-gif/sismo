"""Échelle d'alerte sismique de Sismo : niveau 0 (calme) à 4 (séisme).

Le niveau combine deux informations, comme un sismographe qui regarde l'amplitude ET la secousse :
- le NIVEAU du score composite : plus il est bas, plus l'alerte est haute ;
- la VITESSE de dégradation : variation du score sur 3 mois ; une chute rapide relève l'alerte,
  une remontée nette la baisse.

Règle (fixée avant de regarder les résultats, puis vérifiée sur le test sur le passé) :
  base     : score ≥ 65 → 0 ; 50-65 → 1 ; 35-50 → 2 ; < 35 → 3
  vitesse  : chute de 10 points ou plus en 3 mois → +2 ; chute de 5 à 10 points → +1 ;
             hausse de 5 points ou plus → −1
  niveau   = base + vitesse, borné entre 0 et 4
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

LEVELS = [
    dict(level=0, label="Calme", kind="good",
         meaning="Rien à signaler : les conditions sont favorables et stables."),
    dict(level=1, label="Secousses légères", kind="good",
         meaning="Quelques secousses, rien d'inquiétant à ce stade."),
    dict(level=2, label="Vigilance", kind="warning",
         meaning="Situation à surveiller : un scénario de dégradation devient plausible."),
    dict(level=3, label="Alerte", kind="serious",
         meaning="Signal d'alerte : par le passé, ce niveau a accompagné ou précédé la plupart des crises, "
                 "avec environ 7 % de fausses alertes."),
    dict(level=4, label="Séisme", kind="critical",
         meaning="Niveau maximal : les conditions sont dégradées et se détériorent très vite. Par le passé, "
                 "ce niveau a été atteint dans l'année précédant presque toutes les crises testées, mais aussi lors de "
                 "fausses alertes (environ 3 % des mois calmes)."),
]
ALERT_FROM = 3          # niveau à partir duquel on parle d'« alerte » dans le test sur le passé
FAST_DROP, DROP = -10.0, -5.0
RISE = 5.0


CUTS = (65.0, 50.0, 35.0)


def level(score: Optional[float], change_3m: Optional[float], cuts: tuple = CUTS,
          drops: tuple = (FAST_DROP, DROP), rise: float = RISE) -> Optional[int]:
    """Niveau 0-4. `cuts` et `drops` ne servent à changer les seuils que pour le test de solidité."""
    if score is None or pd.isna(score):
        return None
    hi, mid, lo = cuts
    base = 0 if score >= hi else 1 if score >= mid else 2 if score >= lo else 3
    mom = 0
    if change_3m is not None and not pd.isna(change_3m):
        mom = 2 if change_3m <= drops[0] else 1 if change_3m <= drops[1] else (-1 if change_3m >= rise else 0)
    return int(max(0, min(4, base + mom)))


def describe(lvl: Optional[int]) -> Optional[dict]:
    return None if lvl is None else dict(LEVELS[lvl])


def series(comp: pd.Series, **kw) -> pd.Series:
    """Niveau d'alerte mois par mois, à partir de la série du score composite."""
    comp = comp.dropna()
    d3 = comp - comp.shift(3)
    return pd.Series([level(s, d, **kw) for s, d in zip(comp.values, d3.values)], index=comp.index, dtype="float")
