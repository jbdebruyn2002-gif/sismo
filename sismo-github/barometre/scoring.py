"""Du brut au score : mise au pas mensuel, transformation, normalisation, pondération, score global.

Principes :
- Pas de regard dans le futur : les séries publiées avec retard (PIB, inflation) ne sont utilisées
  qu'à partir de leur date de publication estimée (lag_months).
- La normalisation d'un mois n'utilise que l'historique jusqu'à ce mois (fenêtre glissante),
  ce qui rend le score comparable dans le temps sans réécrire le passé.
- Le score global est la moyenne pondérée des scores disponibles. Le poids des indicateurs absents
  est redistribué, et le score n'est publié que si assez de poids est disponible.
- Propriété utile : score global - 50 = somme des contributions (poids x (score - 50)).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from . import alerte, backtest
from .config import EPISODES, INDICATORS, MAX_AGE_MONTHS, MIN_MONTHS, MIN_WEIGHT_SHARE, REGIMES, WINDOW_MONTHS

try:  # pandas >= 2.2 utilise "ME" ; les versions plus anciennes "M"
    pd.date_range("2020-01-31", periods=1, freq="ME")
    ME = "ME"
except ValueError:
    ME = "M"


# ---------------------------------------------------------------- étapes
def to_monthly(raw: pd.Series, cfg: dict, as_of: date) -> pd.Series:
    """Série mensuelle (fin de mois) en tenant compte du délai de publication, prolongée jusqu'au mois de as_of."""
    s = raw.dropna().astype(float).copy()
    s.index = pd.DatetimeIndex(pd.to_datetime(s.index))
    as_of_ts = pd.Timestamp(as_of)
    s = s[s.index <= as_of_ts]
    end = as_of_ts + pd.offsets.MonthEnd(0)
    lag = int(cfg.get("lag_months", 0))
    if lag:
        s.index = s.index + pd.offsets.MonthEnd(0) + pd.offsets.MonthEnd(lag)
        s = s[s.index <= end]
    if s.empty:
        return pd.Series(dtype=float)
    m = getattr(s.resample(ME), cfg.get("agg", "last"))()
    grid = pd.date_range(m.index.min(), end, freq=ME)
    return m.reindex(grid).ffill()


def transform(m: pd.Series, cfg: dict) -> pd.Series:
    t = cfg["transform"]
    if t == "level":
        return m
    if t == "pct12":
        return (m / m.shift(12) - 1) * 100
    raise ValueError(f"Transformation inconnue : {t}")


def normalize(x: pd.Series, cfg: dict) -> pd.Series:
    """Ramène l'indicateur sur 0-100 (100 = favorable). La fenêtre ne contient que le passé et le présent."""
    method = cfg["method"]
    roll = x.rolling(WINDOW_MONTHS, min_periods=MIN_MONTHS)
    if method == "minmax":
        lo, hi = roll.quantile(0.02), roll.quantile(0.98)
        s = 100 * (x - lo) / (hi - lo).replace(0, np.nan)
    elif method == "zscore":
        s = 50 + 20 * (x - roll.mean()) / roll.std(ddof=0).replace(0, np.nan)
    elif method == "target":
        s = 100 - 100 * (x - cfg["target"]).abs() / cfg["tolerance"]
        s = s.where(x.notna())
    else:
        raise ValueError(f"Méthode inconnue : {method}")
    s = s.clip(0, 100)
    if cfg.get("invert") and method != "target":
        s = 100 - s
    return s


def regime(score: float) -> tuple[str, str]:
    for lo, hi, label, kind in REGIMES:
        if lo <= score < hi:
            return label, kind
    return REGIMES[-1][2], REGIMES[-1][3]


def _weighted(scores: pd.DataFrame, weights: pd.Series, min_share: float, total: float) -> pd.Series:
    """Moyenne pondérée des scores disponibles. `total` = poids de TOUS les indicateurs configurés :
    le score n'est publié que si les indicateurs présents en pèsent au moins min_share."""
    avail = scores.notna()
    wsum = avail.mul(weights, axis=1).sum(axis=1)
    out = scores.fillna(0).mul(weights, axis=1).sum(axis=1) / wsum.replace(0, np.nan)
    return out.where(wsum >= min_share * total)


def _clean(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, 4)


# ---------------------------------------------------------------- calcul complet
def source_series(raw: dict[str, pd.Series], cfg: dict) -> Optional[pd.Series]:
    """Série brute d'un indicateur ; pour un écart (clé `minus`), différence des deux séries aux dates communes."""
    r = raw.get(cfg["series"])
    if r is None:
        return None
    m = cfg.get("minus")
    if not m:
        return r
    r2 = raw.get(m)
    if r2 is None:
        return None
    a, b = r.dropna().astype(float), r2.dropna().astype(float)
    a.index, b.index = pd.DatetimeIndex(pd.to_datetime(a.index)), pd.DatetimeIndex(pd.to_datetime(b.index))
    # Moyennes mensuelles des deux jambes, datées du 1er du mois (comme les séries de l'OCDE) : les fréquences
    # peuvent différer (taux mensuel moins taux quotidien), la différence se fait mois par mois.
    a, b = a.resample("MS").mean(), b.resample("MS").mean()
    return (a - b).dropna()


def stale_reason(r: pd.Series, cfg: dict, as_of: date) -> Optional[str]:
    """Motif d'exclusion si la dernière donnée est trop ancienne pour la fréquence de la série, sinon None."""
    max_age = MAX_AGE_MONTHS.get(cfg.get("freq", ""), None)
    rr = r.dropna()
    if max_age is None or rr.empty:
        return None
    last = pd.Timestamp(pd.to_datetime(rr.index[-1]))
    t = pd.Timestamp(as_of)
    age = (t.year - last.year) * 12 + (t.month - last.month)
    if age > max_age:
        return f"dernière donnée du {last.date().isoformat()} : série arrêtée ou trop en retard (plus de {max_age} mois)"
    return None


def compute(raw: dict[str, pd.Series], as_of: date, indicators: Optional[list[dict]] = None,
            history_months: int = 72, episodes: Optional[list[dict]] = None) -> dict:
    """Calcule le baromètre. `raw` : {identifiant de série: série brute datée}. Renvoie un dictionnaire JSON-compatible."""
    indicators = indicators or INDICATORS
    episodes = EPISODES if episodes is None else episodes
    xs, scores, last_obs, why_out = {}, {}, {}, {}
    for cfg in indicators:
        r = source_series(raw, cfg)
        if r is None or len(r.dropna()) == 0:
            why_out[cfg["id"]] = "série non récupérée"
            continue
        reason = stale_reason(r, cfg, as_of)
        if reason:
            why_out[cfg["id"]] = reason
            continue
        m = to_monthly(r, cfg, as_of)
        if m.empty:
            continue
        x = transform(m, cfg)
        xs[cfg["id"]] = x
        scores[cfg["id"]] = normalize(x, cfg)
        rr = r.dropna()
        rr = rr[pd.DatetimeIndex(pd.to_datetime(rr.index)) <= pd.Timestamp(as_of)]
        last_obs[cfg["id"]] = (rr.index[-1], float(rr.iloc[-1])) if len(rr) else (None, None)

    ids = [c["id"] for c in indicators if c["id"] in scores]
    if not ids:
        raise ValueError("Aucune série exploitable : rien à calculer.")
    S = pd.DataFrame({i: scores[i] for i in ids}).sort_index()
    cfg_by = {c["id"]: c for c in indicators}
    W = pd.Series({i: cfg_by[i]["weight"] for i in ids})
    comp = _weighted(S, W, MIN_WEIGHT_SHARE, sum(c["weight"] for c in indicators))
    equal = _weighted(S, pd.Series(1.0, index=ids), MIN_WEIGHT_SHARE, float(len(indicators)))
    valid = comp.dropna()
    if valid.empty:
        raise ValueError("Historique insuffisant : aucun score global calculable (voir MIN_MONTHS).")
    t = valid.index[-1]
    pos = S.index.get_loc(t)

    def at(series: pd.Series, back: int):
        j = pos - back
        return _clean(series.iloc[j]) if j >= 0 else None

    avail_t = S.loc[t].notna()
    wsum_t = float((W * avail_t).sum())
    label, kind = regime(float(comp.loc[t]))
    as_of_iso = pd.Timestamp(as_of).date().isoformat()

    def lab(ts) -> str:  # le dernier point porte la date du jour, les autres la fin de mois
        return as_of_iso if ts == t else pd.Timestamp(ts).date().isoformat()

    inds = []
    for cfg in indicators:
        i = cfg["id"]
        base = {k: cfg[k] for k in ("id", "label", "zone", "family", "series", "source", "unit", "freq",
                                    "method", "invert", "weight", "why", "norm_why")}
        base["transform"] = cfg["transform"]
        base["plain_good"], base["plain_bad"] = cfg.get("plain_good", ""), cfg.get("plain_bad", "")
        base["series_ids"] = [x for x in (cfg["series"], cfg.get("minus")) if x]
        if cfg.get("minus"):
            base["series"] = f"{cfg['series']} − {cfg['minus']}"
        if cfg["method"] == "target":
            base["target"], base["tolerance"] = cfg["target"], cfg["tolerance"]
        if i not in S.columns or pd.isna(S.loc[t, i]):
            base.update(available=False, score=None, contribution=None, weight_effective=0.0,
                        unavailable_reason=why_out.get(i, "historique insuffisant pour calculer un score"))
            inds.append(base)
            continue
        s_t = float(S.loc[t, i])
        w_eff = cfg["weight"] / wsum_t
        obs_date, obs_val = last_obs[i]
        hist = []
        for ts in S.index[max(0, pos - history_months + 1): pos + 1]:
            hist.append([lab(ts), _clean(xs[i].get(ts)), _clean(S.loc[ts, i])])
        s3 = at(S[i], 3)
        base.update(
            available=True, score=round(s_t, 2), weight_effective=round(w_eff, 4),
            contribution=round(w_eff * (s_t - 50), 3),
            value=_clean(xs[i].loc[t]), last_obs=pd.Timestamp(obs_date).date().isoformat() if obs_date is not None else None,
            last_raw=_clean(obs_val), change_3m=_clean(s_t - s3) if s3 is not None else None, history=hist,
        )
        inds.append(base)

    ch = lambda b: (_clean(comp.loc[t] - comp.iloc[pos - b]) if pos - b >= 0 and not pd.isna(comp.iloc[pos - b]) else None)
    comp_hist = [[lab(ts), _clean(comp.loc[ts]), _clean(equal.loc[ts])]
                 for ts in S.index[max(0, pos - history_months + 1): pos + 1] if not pd.isna(comp.loc[ts])]
    result = {
        "as_of": as_of_iso,
        "composite": {
            "score": round(float(comp.loc[t]), 2), "label": label, "kind": kind,
            "change_1m": ch(1), "change_3m": ch(3), "change_12m": ch(12),
            "equal_weight_score": _clean(equal.loc[t]),
            "weight_available": round(wsum_t, 3), "history": comp_hist,
        },
        "indicators": inds,
    }
    lv = alerte.level(float(comp.loc[t]), ch(3))
    result["composite"]["alert"] = alerte.describe(lv)
    result["commentary"] = commentary(result)
    result["backtest"] = backtest.run(comp.loc[:t], equal.loc[:t], episodes)
    return result


# ---------------------------------------------------------------- lecture automatique
def commentary(res: dict) -> list[str]:
    """Phrases de lecture générées à partir des chiffres. À compléter et à discuter dans le rapport."""
    c = res["composite"]
    avail = [i for i in res["indicators"] if i["available"]]
    out = []
    s = f"Score global : {c['score']:.0f}/100, régime « {c['label']} »."
    if c["change_3m"] is not None:
        d = c["change_3m"]
        s += f" {'Hausse' if d > 0.5 else 'Baisse' if d < -0.5 else 'Stabilité'} de {abs(d):.0f} points sur 3 mois."
    out.append(s)
    pos = sorted([i for i in avail if i["contribution"] > 0.5], key=lambda i: -i["contribution"])[:3]
    neg = sorted([i for i in avail if i["contribution"] < -0.5], key=lambda i: i["contribution"])[:3]
    if pos:
        out.append("Soutiens : " + " ; ".join(f"{i['label']} ({i['contribution']:+.1f} pt)" for i in pos) + ".")
    if neg:
        out.append("Freins : " + " ; ".join(f"{i['label']} ({i['contribution']:+.1f} pt)" for i in neg) + ".")
    if avail:
        big_w = max(avail, key=lambda i: i["weight"])
        big_c = max(avail, key=lambda i: abs(i["contribution"]))
        out.append(f"Poids le plus élevé : {big_w['label']} ({big_w['weight'] * 100:.0f} %). "
                   f"Plus forte contribution aujourd'hui : {big_c['label']} ({big_c['contribution']:+.1f} pt).")
    eq = c.get("equal_weight_score")
    if eq is not None:
        d = c["score"] - eq
        out.append(f"Test de robustesse : à poids égaux, le score serait de {eq:.0f}/100 ({d:+.0f} point par rapport au choix de pondération).")
    miss = [i["label"] for i in res["indicators"] if not i["available"]]
    if miss:
        out.append("Indicateurs indisponibles (poids redistribué) : " + ", ".join(miss) + ".")
    return out
