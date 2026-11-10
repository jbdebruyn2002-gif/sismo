"""Avis de changement d'alerte : compare l'ancien et le nouveau web/data.js.

    python -m barometre.notify ANCIEN_data.js NOUVEAU_data.js DOSSIER_SORTIE [SITE_URL]

Si le niveau d'alerte d'au moins une zone a changé, écrit DOSSIER_SORTIE/titre.txt et DOSSIER_SORTIE/message.md
(utilisés par GitHub Actions pour ouvrir un ticket, ce qui envoie un e-mail au propriétaire du dépôt).
Sinon, n'écrit rien. Code de sortie toujours 0 : un avis manqué ne doit jamais bloquer la mise à jour du site.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional


def load(path: Path) -> Optional[dict]:
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text.split("=", 1)[1].strip().rstrip(";"))
    except (OSError, ValueError, IndexError):
        return None


def levels(data: Optional[dict]) -> dict:
    out = {}
    for z in (data or {}).get("zones", []):
        al = (z.get("composite") or {}).get("alert")
        if al:
            out[z["id"]] = (al["level"], al["label"], z["label"])
    return out


def changes(old: Optional[dict], new: Optional[dict]) -> list[dict]:
    before, after = levels(old), levels(new)
    res = []
    for zid, (lv, lab, zone) in after.items():
        if zid in before and before[zid][0] != lv:
            res.append(dict(id=zid, zone=zone, old=before[zid][0], old_label=before[zid][1], new=lv, new_label=lab))
    return res


def message(chg: list[dict], new: dict, site: str = "") -> tuple[str, str]:
    up = [c for c in chg if c["new"] > c["old"]]
    main = max(chg, key=lambda c: c["new"])
    verb = "passe en" if main["new"] > main["old"] else "redescend en"
    title = f"Sismo : {main['zone']} {verb} {main['new_label'].lower()} ({main['new']}/4)"
    if len(chg) > 1:
        title += f" et {len(chg) - 1} autre(s) changement(s)"
    zones = {z["id"]: z for z in new.get("zones", [])}
    lines = [f"Changement de niveau d'alerte au {new['zones'][0].get('as_of', '')} :", ""]
    for c in sorted(chg, key=lambda c: -c["new"]):
        arrow = "▲" if c["new"] > c["old"] else "▼"
        z = zones[c["id"]]
        s = z.get("summary") or {}
        lines.append(f"- **{c['zone']}** {arrow} {c['old_label']} ({c['old']}/4) → **{c['new_label']} ({c['new']}/4)**, "
                     f"score {round(z['composite']['score'])}/100")
        if s.get("move"):
            lines.append(f"  - {s['move']}")
    if up:
        lines += ["", "Rappel : sur le passé, le niveau 3 ou plus a accompagné la plupart des crises, avec environ 7 % de fausses alertes."]
    if site:
        lines += ["", f"Voir le détail : {site}"]
    lines += ["", "_Avis envoyé automatiquement par la mise à jour quotidienne de Sismo. Fermez ce ticket une fois lu._"]
    return title, "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 0
    old, new = load(Path(argv[0])), load(Path(argv[1]))
    out = Path(argv[2])
    site = argv[3] if len(argv) > 3 else ""
    if not old or not new:
        print("Avis : pas d'ancienne version à comparer, rien à signaler.")
        return 0
    chg = changes(old, new)
    if not chg:
        print("Avis : aucun niveau d'alerte n'a changé.")
        return 0
    title, body = message(chg, new, site)
    out.mkdir(parents=True, exist_ok=True)
    (out / "titre.txt").write_text(title, encoding="utf-8")
    (out / "message.md").write_text(body, encoding="utf-8")
    print("Avis :", title)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
