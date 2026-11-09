"""Données SIMULÉES pour tester le moteur et voir le tableau de bord sans connexion.

Ces données sont inventées : ne jamais les présenter comme des données récupérées.
Le fichier généré porte `demo: true` et la page affiche un bandeau d'avertissement.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def make_raw(as_of: date, seed: int = 7, years: int = 36) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(as_of)
    start = end - pd.DateOffset(years=years)
    bd = pd.bdate_range(start, end)

    def ar(n, mean, sd, phi=0.97):
        x = np.empty(n)
        x[0] = mean
        for k in range(1, n):
            x[k] = mean + phi * (x[k - 1] - mean) + rng.normal(0, sd)
        return x

    q = pd.date_range(start, end, freq="QS")
    gdp = 20000 * np.cumprod(1 + rng.normal(0.005, 0.006, len(q)))
    mo = pd.date_range(start, end, freq="MS")
    cpi = 230 * np.cumprod(1 + np.clip(rng.normal(0.0025, 0.0025, len(mo)), -0.004, 0.012))
    spx = 2000 * np.cumprod(1 + rng.normal(0.0004, 0.011, len(bd)))
    vix = np.clip(ar(len(bd), 18, 1.1, 0.985), 9, 70)
    curve = ar(len(bd), 0.6, 0.04, 0.995)
    oil = 70 * np.exp(ar(len(bd), 0, 0.017, 0.9995))
    wk = pd.date_range(start, end, freq="W-FRI")
    nfci = ar(len(wk), -0.3, 0.05, 0.97)
    usd = 100 * np.cumprod(1 + rng.normal(0.0001, 0.003, len(bd)))
    ea_gdp = 2e6 * np.cumprod(1 + rng.normal(0.0035, 0.005, len(q)))
    hicp = 70 * np.cumprod(1 + np.clip(rng.normal(0.0017, 0.002, len(mo)), -0.004, 0.01))
    de10 = ar(len(mo), 2.5, 0.15, 0.98)
    it10 = de10 + np.clip(ar(len(mo), 1.5, 0.2, 0.95), 0, 6)
    ez3m = de10 - np.clip(ar(len(mo), 1.2, 0.15, 0.95), -1, 4)
    jp_gdp = 5e5 * np.cumprod(1 + rng.normal(0.002, 0.006, len(q)))
    jp_cpi = 95 * np.cumprod(1 + np.clip(rng.normal(0.0005, 0.002, len(mo)), -0.005, 0.01))
    nikkei = 15000 * np.cumprod(1 + rng.normal(0.0002, 0.013, len(bd)))
    jp10 = np.clip(ar(len(mo), 0.8, 0.08, 0.98), -0.3, 3)
    jp3m = jp10 - np.clip(ar(len(mo), 0.6, 0.08, 0.95), -0.5, 2)
    cny = 7 * np.cumprod(1 + rng.normal(0, 0.0015, len(bd)))
    return {
        "CLVMNACSCAB1GQEA": pd.Series(ea_gdp, index=q),
        "CP0000EZCCM086NEST": pd.Series(hicp, index=mo),
        "IRLTLT01ITM156N": pd.Series(it10, index=mo),
        "IRLTLT01DEM156N": pd.Series(de10, index=mo),
        "ECBDFR": pd.Series(ez3m, index=mo),
        "JPNRGDPEXP": pd.Series(jp_gdp, index=q),
        "NIKKEI225": pd.Series(nikkei, index=bd),
        "IRLTLT01JPM156N": pd.Series(jp10, index=mo),
        "IR3TIB01JPM156N": pd.Series(jp3m, index=mo),
        "DEXCHUS": pd.Series(cny, index=bd),
        "GDPC1": pd.Series(gdp, index=q),
        "CPIAUCSL": pd.Series(cpi, index=mo),
        "SP500": pd.Series(spx, index=bd),
        "VIXCLS": pd.Series(vix, index=bd),
        "T10Y2Y": pd.Series(curve, index=bd),
        "DCOILBRENTEU": pd.Series(oil, index=bd),
        "NFCI": pd.Series(nfci, index=wk),
        "DTWEXBGS": pd.Series(usd, index=bd),
    }
