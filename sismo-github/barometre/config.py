"""Choix du baromètre : indicateurs, sources, zones, normalisation et pondérations.

Tout ce qui se discute dans le rapport est ici. Modifier ce fichier suffit à changer le baromètre.
Les identifiants de séries sont ceux de FRED (Federal Reserve Bank of St. Louis), accessibles sans clé.
Identifiants vérifiés sur FRED le 2 novembre 2026 ; `python run.py` signale toute série injoignable.
`minus` = série soustraite à `series` (pour un écart de taux).
`plain_good` / `plain_bad` : phrases simples utilisées dans le résumé « En bref ».
"""

# Fenêtre d'historique servant à normaliser (en mois) et minimum pour calculer un score.
WINDOW_MONTHS = 120
MIN_MONTHS = 36

# Seuils de lecture du score (sur 100).
REGIMES = [
    (0, 35, "Défavorable", "critical"),
    (35, 50, "Prudent", "warning"),
    (50, 65, "Plutôt favorable", "good"),
    (65, 101, "Favorable", "good"),
]

# Fraîcheur : une série dont la dernière donnée est plus ancienne que ce délai (en mois) est considérée
# comme arrêtée ; l'indicateur est alors exclu et son poids redistribué (au lieu de prolonger une vieille valeur).
MAX_AGE_MONTHS = {"quotidienne": 2, "hebdomadaire": 2, "mensuelle": 5, "trimestrielle": 8}

# Part minimale du poids total qui doit être disponible pour publier un score.
MIN_WEIGHT_SHARE = 0.6

# Méthodes de normalisation (toutes ramènent l'indicateur sur 0-100, 100 = situation la plus favorable) :
#   minmax : (x - bas) / (haut - bas), bornes = percentiles 2 % et 98 % de la fenêtre (limite l'effet des valeurs extrêmes)
#   zscore : 50 + 20 * (x - moyenne) / écart-type de la fenêtre ; z = ±2,5 correspond aux bornes 0 et 100
#   target : 100 - 100 * |x - cible| / tolérance ; 100 sur la cible, 0 à une distance égale à la tolérance
# invert=True retourne l'échelle quand une valeur haute est mauvaise (volatilité, stress, écart de taux, devise qui chute).

# ---------------------------------------------------------------- catalogue des indicateurs
CATALOG = [
    # ---- États-Unis
    dict(
        id="gdp", label="Croissance du PIB réel (États-Unis)", zone="États-Unis", family="Croissance",
        series="GDPC1", source="FRED (BEA)", unit="% sur 1 an", freq="trimestrielle",
        transform="pct12", agg="last", lag_months=3, method="minmax", invert=False,
        why="Mesure l'activité réelle, donc les bénéfices des entreprises. Publié avec retard (trimestriel).",
        norm_why="Min-Max : une croissance plus forte est toujours meilleure ; les percentiles écartent la chute du Covid.",
        plain_good="la croissance américaine est plus forte que d'habitude", plain_bad="la croissance américaine est plus faible que d'habitude",
    ),
    dict(
        id="cpi", label="Inflation (IPC, États-Unis)", zone="États-Unis", family="Inflation",
        series="CPIAUCSL", source="FRED (BLS)", unit="% sur 1 an", freq="mensuelle",
        transform="pct12", agg="last", lag_months=1, method="target", target=2.0, tolerance=4.0, invert=False,
        why="Une inflation proche de 2 % (cible de la Fed) est la plus favorable : trop haute elle fait monter les taux, trop basse elle révèle une demande faible.",
        norm_why="Cible 2 % : le score baisse de 25 points par point d'écart, et atteint 0 à 6 % ou à -2 %.",
        plain_good="l'inflation américaine est proche de 2 %", plain_bad="l'inflation américaine s'éloigne de la cible de 2 %",
    ),
    dict(
        id="equity", label="Marché actions (S&P 500)", zone="États-Unis", family="Marchés financiers",
        series="SP500", source="FRED (S&P Dow Jones Indices)", unit="% sur 1 an", freq="quotidienne",
        transform="pct12", agg="last", lag_months=0, method="zscore", invert=False,
        why="Les marchés anticipent l'avenir : la performance sur 12 mois résume l'appétit pour le risque.",
        norm_why="Z-score : une hausse n'est forte que par rapport à l'histoire récente de l'indice.",
        plain_good="la Bourse américaine fait mieux que d'habitude sur un an", plain_bad="la Bourse américaine fait moins bien que d'habitude sur un an",
    ),
    dict(
        id="curve", label="Courbe des taux (États-Unis, 10 ans − 2 ans)", zone="États-Unis", family="Taux",
        series="T10Y2Y", source="FRED (Fed de St. Louis)", unit="points de %", freq="quotidienne",
        transform="level", agg="last", lag_months=0, method="minmax", invert=False,
        why="Une courbe inversée (écart négatif) a précédé la plupart des récessions américaines.",
        norm_why="Min-Max : plus la courbe est pentue, plus le score est élevé.",
        plain_good="la courbe des taux américaine est plus pentue que d'habitude", plain_bad="la courbe des taux américaine est plus plate que d'habitude, un signal de ralentissement",
    ),
    dict(
        id="stress", label="Conditions financières (NFCI)", zone="États-Unis", family="Risque",
        series="NFCI", source="FRED (Fed de Chicago)", unit="indice (0 = moyenne)", freq="hebdomadaire",
        transform="level", agg="last", lag_months=0, method="zscore", invert=True,
        why="Synthétise le crédit, le levier et le risque sur 105 indicateurs. Positif : conditions plus tendues que la moyenne.",
        norm_why="Z-score inversé : des conditions plus tendues que d'habitude font baisser le score.",
        plain_good="le crédit circule plus facilement que d'habitude aux États-Unis", plain_bad="les conditions de crédit sont plus tendues que d'habitude aux États-Unis",
    ),
    # ---- Monde (communs à plusieurs zones)
    dict(
        id="vol", label="Volatilité implicite (VIX)", zone="Monde", family="Volatilité",
        series="VIXCLS", source="FRED (CBOE)", unit="points", freq="quotidienne",
        transform="level", agg="mean", lag_months=0, method="minmax", invert=True,
        why="Mesure la nervosité des investisseurs. Calculé sur le S&P 500, mais sert de baromètre mondial de l'aversion au risque : il bondit dans toutes les crises.",
        norm_why="Min-Max inversé : volatilité basse = score élevé. Moyenne mensuelle pour lisser les pics d'un jour.",
        plain_good="les marchés sont plus calmes que d'habitude", plain_bad="les marchés sont plus nerveux que d'habitude",
    ),
    dict(
        id="oil", label="Pétrole (Brent)", zone="Monde", family="Matières premières",
        series="DCOILBRENTEU", source="FRED (EIA)", unit="% sur 1 an", freq="quotidienne",
        transform="pct12", agg="last", lag_months=0, method="target", target=0.0, tolerance=50.0, invert=False,
        why="Une flambée alimente l'inflation, un effondrement signale une demande faible : la stabilité est la plus favorable. Effet indirect.",
        norm_why="Cible 0 % de variation : le score atteint 0 à ±50 % sur un an.",
        plain_good="le prix du pétrole est assez stable sur un an", plain_bad="le prix du pétrole a fortement varié sur un an",
    ),
    dict(
        id="usd", label="Dollar américain (proxy des flux de capitaux)", zone="Monde", family="Flux de capitaux",
        series="DTWEXBGS", source="FRED (Réserve fédérale)", unit="% sur 1 an", freq="quotidienne",
        transform="pct12", agg="last", lag_months=0, method="zscore", invert=True,
        why="Un dollar qui s'apprécie vite signale des capitaux qui cherchent la sécurité et resserre les conditions financières mondiales. Proxy : il n'existe pas de série gratuite directe sur les flux.",
        norm_why="Z-score inversé : une forte appréciation du dollar fait baisser le score.",
        plain_good="le dollar ne monte pas plus vite que d'habitude", plain_bad="le dollar monte plus vite que d'habitude : les capitaux se replient vers la sécurité",
    ),
    # ---- Zone euro
    dict(
        id="ea_gdp", label="Croissance du PIB réel (zone euro)", zone="Zone euro", family="Croissance",
        series="CLVMNACSCAB1GQEA", source="FRED (Eurostat)", unit="% sur 1 an", freq="trimestrielle",
        transform="pct12", agg="last", lag_months=3, method="minmax", invert=False,
        why="L'activité de la zone euro, premier débouché des entreprises françaises. Composition variable : la zone telle qu'elle était à chaque date.",
        norm_why="Min-Max, comme le PIB américain : une croissance plus forte est toujours meilleure.",
        plain_good="la croissance européenne est plus forte que d'habitude", plain_bad="la croissance européenne est plus faible que d'habitude",
    ),
    dict(
        id="ea_cpi", label="Inflation (IPCH, zone euro)", zone="Zone euro", family="Inflation",
        series="CP0000EZCCM086NEST", source="FRED (Eurostat)", unit="% sur 1 an", freq="mensuelle",
        transform="pct12", agg="last", lag_months=1, method="target", target=2.0, tolerance=4.0, invert=False,
        why="L'indice des prix harmonisé que vise la BCE. Proche de 2 %, il laisse la BCE neutre ; loin de 2 %, il annonce un resserrement ou une demande faible.",
        norm_why="Cible 2 %, cible officielle de la BCE : même règle que pour l'inflation américaine.",
        plain_good="l'inflation européenne est proche de 2 %", plain_bad="l'inflation européenne s'éloigne de la cible de 2 %",
    ),
    dict(
        id="ea_spread", label="Écart de taux Italie − Allemagne (10 ans)", zone="Zone euro", family="Risque",
        series="IRLTLT01ITM156N", minus="IRLTLT01DEM156N", source="FRED (OCDE)", unit="points de %", freq="mensuelle",
        transform="level", agg="last", lag_months=1, method="zscore", invert=True,
        why="Mesure le risque de fragmentation de la zone euro : l'écart s'envole quand les investisseurs doutent de la dette italienne (plus de 5 points en 2011-2012).",
        norm_why="Z-score inversé : un écart plus large que d'habitude fait baisser le score.",
        plain_good="l'écart de taux Italie-Allemagne est plus faible que d'habitude", plain_bad="l'écart de taux Italie-Allemagne est plus large que d'habitude : tensions dans la zone euro",
    ),
    dict(
        id="ea_curve", label="Courbe des taux (zone euro, Bund 10 ans − taux de dépôt BCE)", zone="Zone euro", family="Taux",
        series="IRLTLT01DEM156N", minus="ECBDFR", source="FRED (OCDE, BCE)", unit="points de %", freq="mensuelle",
        transform="level", agg="last", lag_months=1, method="minmax", invert=False,
        why="Même logique que la courbe américaine : une courbe plate ou inversée signale une politique monétaire restrictive et un risque de récession.",
        norm_why="Min-Max : plus la courbe est pentue, plus le score est élevé. Taux allemand 10 ans (moyenne mensuelle) moins taux de la facilité de dépôt de la BCE (moyenne mensuelle). Le taux à 3 mois de l'OCDE n'est plus mis à jour depuis janvier 2026.",
        plain_good="la courbe des taux européenne est plus pentue que d'habitude", plain_bad="la courbe des taux européenne est plus plate que d'habitude, un signal de ralentissement",
    ),
    # ---- Asie
    dict(
        id="jp_gdp", label="Croissance du PIB réel (Japon)", zone="Japon", family="Croissance",
        series="JPNRGDPEXP", source="FRED (Cabinet Office du Japon)", unit="% sur 1 an", freq="trimestrielle",
        transform="pct12", agg="last", lag_months=4, method="minmax", invert=False,
        why="Quatrième économie mondiale et principal marché développé d'Asie. Publié environ six semaines après la fin du trimestre.",
        norm_why="Min-Max : une croissance plus forte est toujours meilleure.",
        plain_good="la croissance japonaise est plus forte que d'habitude", plain_bad="la croissance japonaise est plus faible que d'habitude",
    ),
    dict(
        id="nikkei", label="Marché actions (Nikkei 225)", zone="Japon", family="Marchés financiers",
        series="NIKKEI225", source="FRED (Nikkei)", unit="% sur 1 an", freq="quotidienne",
        transform="pct12", agg="last", lag_months=0, method="zscore", invert=False,
        why="Principal indice boursier asiatique disponible en données ouvertes ; résume l'appétit pour le risque en Asie.",
        norm_why="Z-score : la performance sur 12 mois comparée à l'histoire récente de l'indice.",
        plain_good="la Bourse de Tokyo fait mieux que d'habitude sur un an", plain_bad="la Bourse de Tokyo fait moins bien que d'habitude sur un an",
    ),
    dict(
        id="jp_curve", label="Courbe des taux (Japon, 10 ans − 3 mois)", zone="Japon", family="Taux",
        series="IRLTLT01JPM156N", minus="IR3TIB01JPM156N", source="FRED (OCDE)", unit="points de %", freq="mensuelle",
        transform="level", agg="last", lag_months=1, method="minmax", invert=False,
        why="Pente de la courbe japonaise. Longtemps écrasée par la politique de contrôle des taux de la Banque du Japon : à lire avec prudence.",
        norm_why="Min-Max : plus la courbe est pentue, plus le score est élevé.",
        plain_good="la courbe des taux japonaise est plus pentue que d'habitude", plain_bad="la courbe des taux japonaise est plus plate que d'habitude",
    ),
    dict(
        id="cny", label="Yuan chinois (contre dollar)", zone="Chine", family="Flux de capitaux",
        series="DEXCHUS", source="FRED (Réserve fédérale)", unit="% sur 1 an", freq="quotidienne",
        transform="pct12", agg="last", lag_months=0, method="zscore", invert=True,
        why="Seul indicateur chinois à jour sur FRED. Une forte dépréciation du yuan accompagne les sorties de capitaux et les tensions sur l'économie chinoise (2015-2016).",
        norm_why="Z-score inversé : une hausse du nombre de yuans par dollar (yuan qui baisse) fait baisser le score.",
        plain_good="le yuan est plus solide que d'habitude face au dollar", plain_bad="le yuan faiblit plus que d'habitude : signe de sorties de capitaux de Chine",
    ),
]

# ---------------------------------------------------------------- zones et pondérations
# Dans chaque zone, les poids somment à 1. La vue « Monde » combine les trois zones.
ZONES = [
    dict(id="us", label="États-Unis", hash="etats-unis",
         weights=dict(gdp=0.15, cpi=0.10, equity=0.15, vol=0.15, curve=0.15, oil=0.05, stress=0.15, usd=0.10),
         weights_why="Indicateurs de marché, rapides et tournés vers l'avenir (actions, volatilité, conditions financières, courbe des taux) : 15 % chacun. PIB, fondamental mais publié en retard : 15 %. Inflation et dollar, plus indirects : 10 %. Pétrole : 5 %.",
         limits="Le dollar est un proxy imparfait des flux de capitaux. La série S&P 500 de FRED ne couvre qu'environ 10 ans."),
    dict(id="eu", label="Europe", hash="europe",
         weights=dict(ea_gdp=0.20, ea_cpi=0.15, ea_spread=0.20, ea_curve=0.20, vol=0.15, oil=0.10),
         weights_why="Croissance, écart de taux Italie-Allemagne et courbe des taux : 20 % chacun, ce sont les signaux propres à la zone euro. Inflation : 15 %. VIX, faute d'indice de volatilité européen gratuit : 15 %. Pétrole, dont l'Europe importe l'essentiel : 10 %.",
         limits="Pas d'indice boursier européen (Euro Stoxx) en données ouvertes sur FRED : le VIX américain sert de mesure du risque. Les taux OCDE sont des moyennes mensuelles, publiées avec environ un mois de retard."),
    dict(id="asia", label="Asie", hash="asie",
         weights=dict(jp_gdp=0.20, nikkei=0.25, jp_curve=0.10, cny=0.15, vol=0.15, oil=0.10, usd=0.05),
         weights_why="Nikkei : 25 %, seul indice boursier asiatique ouvert. Croissance japonaise : 20 %. Yuan et VIX : 15 % chacun. Courbe japonaise et pétrole (l'Asie est importatrice) : 10 %. Dollar fort, qui pèse sur les économies émergentes d'Asie : 5 %.",
         limits="Périmètre réduit au Japon et à la Chine. Pas d'inflation : la série japonaise de FRED (OCDE) s'arrête en juin 2021, et les séries chinoises en 2025. La Chine n'est représentée que par le yuan. La courbe japonaise a été contrôlée par la Banque du Japon de 2016 à 2024."),
]
# Poids de chaque zone dans la vue Monde (proches de leur part dans la capitalisation boursière mondiale et le PIB des pays développés).
GLOBAL_MIX = dict(us=0.45, eu=0.30, asia=0.25)
GLOBAL = dict(id="global", label="Monde", hash="monde",
              weights_why="Moyenne des trois zones : États-Unis 45 %, Europe 30 %, Asie 25 %. Le poids d'un indicateur commun (VIX, pétrole, dollar) est la somme de ses poids dans chaque zone.",
              limits="Le score mondial hérite des limites de chaque zone. Les pays émergents hors Chine ne sont pas couverts.")

# ---------------------------------------------------------------- test sur le passé
# Épisodes fixés AVANT de regarder le score (sinon le test serait biaisé).
# Récessions : dates officielles du NBER. Crises de marché : du sommet au creux de l'indice cité.
EPISODES = [
    dict(name="Récession de 2001 (bulle internet)", short="2001", start="2001-03", end="2001-11", source="NBER",
         zones=["global", "us"]),
    dict(name="Crise financière de 2008", short="2008", start="2007-12", end="2009-06", source="NBER",
         zones=["global", "us", "eu", "asia"]),
    dict(name="Crise de la dette en zone euro", short="2011", start="2011-05", end="2011-10", source="S&P 500, sommet au creux",
         zones=["global", "us", "eu", "asia"]),
    dict(name="Krach boursier chinois", short="2015", start="2015-06", end="2016-01", source="Shanghai Composite, sommet au creux",
         zones=["global", "asia"]),
    dict(name="Choc du Covid-19", short="2020", start="2020-02", end="2020-04", source="NBER",
         zones=["global", "us", "eu", "asia"]),
    dict(name="Hausse des taux de 2022", short="2022", start="2022-01", end="2022-10", source="S&P 500, sommet au creux",
         zones=["global", "us", "eu", "asia"]),
]
ALERT_THRESHOLD = 50   # sous ce score, le baromètre est considéré « en alerte »
LEAD_MONTHS = 12       # fenêtre d'anticipation examinée avant chaque épisode


# ---------------------------------------------------------------- outils
_BY_ID = {c["id"]: c for c in CATALOG}


def zone_weights(zone_id: str) -> dict:
    if zone_id == "global":
        out: dict = {}
        for z in ZONES:
            for k, w in z["weights"].items():
                out[k] = out.get(k, 0.0) + GLOBAL_MIX[z["id"]] * w
        return out
    return next(z for z in ZONES if z["id"] == zone_id)["weights"]


def indicators_for(zone_id: str) -> list[dict]:
    """Indicateurs d'une zone, dans l'ordre du catalogue, avec leur poids dans cette zone."""
    w = zone_weights(zone_id)
    out = [dict(c, weight=round(w[c["id"]], 6)) for c in CATALOG if c["id"] in w]
    if zone_id != "global":  # indicateurs propres à la zone d'abord, indicateurs mondiaux ensuite
        out.sort(key=lambda c: c["zone"] == "Monde")
    return out


def zone_info(zone_id: str) -> dict:
    return GLOBAL if zone_id == "global" else next(z for z in ZONES if z["id"] == zone_id)


def episodes_for(zone_id: str) -> list[dict]:
    return [e for e in EPISODES if zone_id in e["zones"]]


ZONE_IDS = ["global"] + [z["id"] for z in ZONES]


def check_config() -> None:
    ids = [c["id"] for c in CATALOG]
    if len(set(ids)) != len(ids):
        raise ValueError("Identifiants d'indicateurs en double.")
    for c in CATALOG:
        if c["method"] not in ("minmax", "zscore", "target"):
            raise ValueError(f"Méthode inconnue pour {c['id']}")
        if c["method"] == "target" and ("target" not in c or "tolerance" not in c):
            raise ValueError(f"{c['id']} : une cible exige target et tolerance.")
    if abs(sum(GLOBAL_MIX.values()) - 1) > 1e-9:
        raise ValueError("Les poids des zones (GLOBAL_MIX) doivent sommer à 1.")
    for z in ZONE_IDS:
        w = zone_weights(z)
        unknown = set(w) - set(_BY_ID)
        if unknown:
            raise ValueError(f"Zone {z} : indicateurs inconnus {unknown}")
        if abs(sum(w.values()) - 1.0) > 1e-9:
            raise ValueError(f"Zone {z} : les poids doivent sommer à 1 (actuellement {sum(w.values())}).")


check_config()

# Compatibilité : la vue par défaut est la vue Monde.
INDICATORS = indicators_for("global")
