"""Point d'entrée : collecte les données, calcule le score et écrit la page web.

    python run.py                 données réelles (FRED), met à jour web/data.js et dist/barometre.html
    python run.py --offline       réutilise les fichiers de data/raw/ sans réseau
    python run.py --files         lit les CSV déjà téléchargés dans data/raw/ (voir lancer-barometre.command)
    python run.py --demo          DONNÉES SIMULÉES, pour voir la page sans connexion (bandeau d'avertissement)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from barometre import collect, demo, resume
from barometre.config import (CATALOG, MIN_MONTHS, MIN_WEIGHT_SHARE, REGIMES, WINDOW_MONTHS, ZONE_IDS,
                              episodes_for, indicators_for, zone_info)
from barometre.scoring import compute

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DIST = ROOT / "dist"


def build_single_file(data_js: str) -> Path:
    """Un seul fichier HTML autonome (page + données) : à déposer tel quel sur Netlify ou à remettre."""
    html = (WEB / "index.html").read_text(encoding="utf-8")
    tag = '<script src="data.js"></script>'
    if tag not in html:
        raise ValueError("web/index.html doit contenir " + tag)
    DIST.mkdir(exist_ok=True)
    out = DIST / "barometre.html"
    out.write_text(html.replace(tag, "<script>\n" + data_js + "\n</script>"), encoding="utf-8")
    return out


SITE = ROOT / "site"


def build_site(single_file: Path) -> Path:
    """Dossier site/ à déposer tel quel sur Netlify (app.netlify.com/drop) : page + manifeste + icônes + hors connexion."""
    import shutil
    SITE.mkdir(exist_ok=True)
    shutil.copyfile(single_file, SITE / "index.html")
    for f in (WEB / "pwa").iterdir():
        if f.is_file():
            shutil.copyfile(f, SITE / f.name)
    (SITE / "_headers").write_text("/sw.js\n  Cache-Control: no-cache\n/index.html\n  Cache-Control: no-cache\n"
                                   "/manifest.webmanifest\n  Content-Type: application/manifest+json\n", encoding="utf-8")
    return SITE


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", metavar="FICHIER",
                    help="fichier JSON {identifiant: texte CSV FRED} téléchargé depuis un navigateur ; écrit data/raw/ puis calcule")
    ap.add_argument("--demo", action="store_true", help="données simulées (jamais à présenter comme réelles)")
    ap.add_argument("--offline", action="store_true", help="n'utilise que data/raw/ (signalé comme copie locale)")
    ap.add_argument("--files", action="store_true",
                    help="utilise les CSV FRED que vous venez de télécharger dans data/raw/ (ex. avec curl) comme données fraîches")
    ap.add_argument("--as-of", help="date de calcul AAAA-MM-JJ (par défaut : aujourd'hui)")
    args = ap.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    if args.json:
        bundle = json.loads(Path(args.json).read_text(encoding="utf-8"))
        collect.RAW_DIR.mkdir(parents=True, exist_ok=True)
        for sid, text in bundle.items():
            if isinstance(text, str) and text.lstrip().lower().startswith("observation_date"):
                (collect.RAW_DIR / f"{sid}.csv").write_text(text, encoding="utf-8")
        print(f"{len(bundle)} séries lues dans {args.json}, écrites dans data/raw/.")
        args.files = True
    if args.demo:
        raw = demo.make_raw(as_of)
        status = {sid: "démonstration (données simulées)" for sid in collect.series_ids(CATALOG)}
    else:
        print("Statut des séries :", flush=True)
        raw, status = collect.collect_all(offline=args.offline, local_files=args.files)
    zones = []
    for zid in ZONE_IDS:
        info = zone_info(zid)
        try:
            res = compute(raw, as_of, indicators_for(zid), episodes=episodes_for(zid))
        except ValueError as e:
            print(f"\n{info['label']} : calcul impossible ({e})", file=sys.stderr)
            continue
        res.update(id=zid, label=info["label"], hash=info["hash"],
                   weights_why=info["weights_why"], limits=info["limits"])
        res["summary"] = resume.build(res, info["label"])
        zones.append(res)
        c = res["composite"]
        print(f"\n{info['label']} — score au {res['as_of']} : {c['score']:.0f}/100 ({c['label']})"
              + ("   [DONNÉES SIMULÉES]" if args.demo else ""))
        for i in res["indicators"]:
            print(f"  {i['label'][:52]:<52} " + (f"{i['score']:5.1f}  poids {i['weight_effective'] * 100:4.1f} %  "
                  f"contribution {i['contribution']:+5.1f}" if i["available"] else "indisponible"))
    if not zones:
        print("\nAucune zone calculable.", file=sys.stderr)
        return 1

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "demo": bool(args.demo),
        "sources": status,
        "window_months": WINDOW_MONTHS, "min_months": MIN_MONTHS, "min_weight_share": MIN_WEIGHT_SHARE,
        "regimes": [{"from": a, "to": b, "label": l, "kind": k} for a, b, l, k in REGIMES],
    }
    payload = {"zones": zones, "meta": meta}
    data_js = "window.BAROMETRE = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"
    WEB.mkdir(exist_ok=True)
    (WEB / "data.js").write_text(data_js, encoding="utf-8")
    if (WEB / "index.html").exists():
        single = build_single_file(data_js)
        print("\nFichier unique écrit :", single)
        print("Dossier à déposer sur Netlify :", build_site(single))
    return 0


if __name__ == "__main__":
    sys.exit(main())
