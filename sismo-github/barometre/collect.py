"""Collecte automatique des données de FRED.

Deux voies :
- avec une clé d'API FRED (gratuite) : API officielle api.stlouisfed.org, faite pour les programmes.
  C'est la voie à utiliser pour la mise à jour automatique : FRED bloque souvent les téléchargements
  du fichier CSV « graphique » quand ils ne viennent pas d'un navigateur.
  La clé est lue dans la variable d'environnement FRED_API_KEY, ou dans le fichier .fred_api_key
  à la racine du projet (ce fichier n'est jamais publié).
- sans clé : fichier CSV public fredgraph.csv.

Chaque téléchargement réussi est gardé dans data/raw/ (reproductibilité). Si FRED est injoignable,
la dernière copie locale est utilisée et le statut le signale : le tableau de bord n'affiche jamais
une donnée ancienne sans le dire.
"""
from __future__ import annotations

import io
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from .config import CATALOG

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd={start}"
API_URL = ("https://api.stlouisfed.org/fred/series/observations?series_id={id}&api_key={key}"
           "&file_type=json&observation_start={start}")
KEY_FILE = Path(__file__).resolve().parent.parent / ".fred_api_key"


def api_key() -> Optional[str]:
    """Clé d'API FRED : variable FRED_API_KEY, sinon fichier .fred_api_key. None si absente."""
    k = os.environ.get("FRED_API_KEY", "").strip()
    if not k and KEY_FILE.exists():
        k = KEY_FILE.read_text(encoding="utf-8").strip()
    return k or None


def api_json_to_csv(text: str, series_id: str) -> str:
    """Réponse JSON de l'API FRED -> texte CSV au format fredgraph (même cache, même lecture)."""
    try:
        d = json.loads(text)
    except ValueError:
        raise ValueError("réponse de l'API illisible (pas du JSON)")
    if "observations" not in d:
        msg = d.get("error_message") or "réponse sans observations"
        raise ValueError(f"API FRED : {msg}")
    lines = [f"observation_date,{series_id}"] + [f"{o['date']},{o['value']}" for o in d["observations"]]
    return "\n".join(lines) + "\n"


def download_csv(series_id: str, fetch: Callable[[str], str], start: str, key: Optional[str]) -> str:
    if key:
        try:
            return api_json_to_csv(fetch(API_URL.format(id=series_id, key=key, start=start)), series_id)
        except (OSError, ValueError) as e:  # la clé ne doit jamais apparaître dans un message publié
            raise type(e)(str(e).replace(key, "***")) from None
    return fetch(FRED_URL.format(id=series_id, start=start))
START = "1990-01-01"  # assez tôt pour que le score couvre les crises de 2001 et 2008
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"


def http_get(url: str, timeout: int = 30, retries: int = 2) -> str:
    last: Optional[Exception] = None
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/csv,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # réseau, blocage, délai dépassé
            last = e
            time.sleep(1.5 * (k + 1))
    raise OSError(str(last))


def parse_fred_csv(text: str) -> pd.Series:
    """CSV FRED -> série datée. Les valeurs manquantes (« . » ou vides) sont ignorées."""
    head = text.lstrip()[:200].lower()
    if "<html" in head or "<!doctype" in head or "," not in head:
        raise ValueError("réponse inattendue (page web au lieu d'un fichier CSV)")
    df = pd.read_csv(io.StringIO(text))
    if df.shape[1] < 2:
        raise ValueError("fichier CSV sans colonne de valeurs")
    dates = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s = pd.Series(values.values, index=dates).dropna()
    s = s[~s.index.isna()]
    if s.empty:
        raise ValueError("aucune observation exploitable")
    return s.sort_index()


def _read_cache(path: Path) -> Optional[pd.Series]:
    try:
        return parse_fred_csv(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fetch_series(series_id: str, fetch: Callable[[str], str] = http_get, cache_dir: Path = RAW_DIR,
                 start: str = START, offline: bool = False,
                 key: Optional[str] = None) -> tuple[Optional[pd.Series], str]:
    """(série, statut). Statut : « ok », « cache : ... » ou « indisponible : ... »."""
    cache = Path(cache_dir) / f"{series_id}.csv"
    err = "mode hors ligne" if offline else ""
    if not offline:
        try:
            text = download_csv(series_id, fetch, start, key)
            s = parse_fred_csv(text)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text, encoding="utf-8")
            via = ", API FRED" if key else ""
            return s, f"ok ({len(s)} observations, dernière : {s.index[-1].date().isoformat()}{via})"
        except (OSError, ValueError) as e:
            err = str(e)
    s = _read_cache(cache)
    if s is not None:
        return s, f"cache : copie du {s.index[-1].date().isoformat()} ({err})"
    return None, f"indisponible : {err}"


def series_ids(indicators: list[dict]) -> list[str]:
    """Toutes les séries à télécharger, y compris celles soustraites pour un écart (clé `minus`)."""
    out: list[str] = []
    for cfg in indicators:
        for sid in (cfg["series"], cfg.get("minus")):
            if sid and sid not in out:
                out.append(sid)
    return out


def read_local(series_id: str, cache_dir: Path = RAW_DIR) -> tuple[Optional[pd.Series], str]:
    """Fichier CSV FRED déjà téléchargé dans data/raw/ (par exemple avec curl) : traité comme une donnée fraîche."""
    s = _read_cache(Path(cache_dir) / f"{series_id}.csv")
    if s is None:
        return None, "indisponible : fichier absent ou illisible dans data/raw/"
    return s, f"ok ({len(s)} observations, dernière : {s.index[-1].date().isoformat()}, fichier téléchargé)"


def collect_all(indicators: list[dict] = CATALOG, fetch: Callable[[str], str] = http_get,
                cache_dir: Path = RAW_DIR, offline: bool = False,
                local_files: bool = False, key: Optional[str] = None,
                use_key: bool = True) -> tuple[dict[str, pd.Series], dict[str, str]]:
    raw, status = {}, {}
    if key is None and use_key and not local_files and not offline:
        key = api_key()
    if key:
        print("  (API officielle FRED, avec clé)", flush=True)
    for sid in series_ids(indicators):
        if local_files:
            s, st = read_local(sid, cache_dir)
        else:
            s, st = fetch_series(sid, fetch, cache_dir, offline=offline, key=key)
        print(f"  {sid:<20} {st}", flush=True)
        status[sid] = st
        if s is not None:
            raw[sid] = s
    return raw, status
