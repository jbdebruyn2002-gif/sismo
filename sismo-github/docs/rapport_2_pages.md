# Sismo, baromètre macro-financier — trame du rapport (2 pages max)

*À réécrire avec vos mots : vous devez pouvoir défendre chaque choix.*

## 1. Objectif et périmètre
Nom : **Sismo**, en référence au sismographe, qui détecte les secousses avant qu'elles ne frappent ; c'est ce que vérifie le test sur le passé.
Un score 0-100 qui résume les conditions macro-financières actuelles (favorable / défavorable pour les actifs risqués), calculé pour trois zones (États-Unis, Europe, Asie) et pour le monde (moyenne pondérée des trois). 16 indicateurs.

## 2. Indicateurs, sources et collecte
| Indicateur | Série FRED | Normalisation | Poids par zone (É.-U. / Europe / Asie) |
|---|---|---|---|
| PIB réel États-Unis | GDPC1 | minmax | 15 % / – / – |
| Inflation États-Unis | CPIAUCSL | cible 2 % | 10 % / – / – |
| S&P 500 | SP500 | zscore | 15 % / – / – |
| Courbe États-Unis (10 ans − 2 ans) | T10Y2Y | minmax | 15 % / – / – |
| Conditions financières (NFCI) | NFCI | zscore inversé | 15 % / – / – |
| PIB réel zone euro | CLVMNACSCAB1GQEA | minmax | – / 20 % / – |
| Inflation zone euro (IPCH) | CP0000EZCCM086NEST | cible 2 % | – / 15 % / – |
| Écart Italie − Allemagne 10 ans | IRLTLT01ITM156N − IRLTLT01DEM156N | zscore inversé | – / 20 % / – |
| Courbe zone euro (Bund 10 ans − taux de dépôt BCE) | IRLTLT01DEM156N − ECBDFR | minmax | – / 20 % / – |
| PIB réel Japon | JPNRGDPEXP | minmax | – / – / 20 % |
| Nikkei 225 | NIKKEI225 | zscore | – / – / 25 % |
| Courbe Japon (10 ans − 3 mois) | IRLTLT01JPM156N − IR3TIB01JPM156N | minmax | – / – / 10 % |
| Yuan contre dollar | DEXCHUS | zscore inversé | – / – / 15 % |
| VIX (mondial) | VIXCLS | minmax inversé | 15 % / 15 % / 15 % |
| Pétrole Brent (mondial) | DCOILBRENTEU | cible 0 % | 5 % / 10 % / 10 % |
| Dollar (mondial, proxy des flux) | DTWEXBGS | zscore inversé | 10 % / – / 5 % |

Vue Monde : États-Unis 45 %, Europe 30 %, Asie 25 %.

Données téléchargées le 2 novembre 2026 depuis FRED (18 séries). Règle de fraîcheur : une série arrêtée est exclue (inflation japonaise arrêtée en juin 2021 ; taux 3 mois zone euro remplacé par le taux de dépôt BCE). Collecte automatique des CSV publics FRED (`collect.py`), copie locale dans `data/raw/`, actualisation quotidienne (GitHub Actions).

## 3. Méthode
- Mise au pas mensuel et délai de publication (PIB +3 mois, inflation +1) : pas de regard dans le futur.
- Transformation : variation sur 12 mois ou niveau.
- Normalisation sur 120 mois glissants : Min-Max (percentiles 2 %/98 %), Z-score (50 + 20z), distance à une cible (inflation 2 %). Inversion pour les risques (VIX, NFCI, dollar).
- Agrégation : moyenne pondérée ; poids manquants redistribués ; score non publié si moins de 60 % du poids disponible.
- Contribution = poids × (score − 50) ; leur somme = score global − 50.

## 4. Justification des poids
États-Unis : marché (actions, VIX, courbe, NFCI) 15 % chacun, réactifs et prospectifs ; PIB 15 %, fondamental mais en retard ; inflation et dollar 10 %, indirects ; pétrole 5 %. Europe : croissance, écart Italie-Allemagne et courbe 20 % chacun (signaux propres à la zone euro) ; inflation 15 % ; VIX 15 %, faute d'indice européen gratuit ; pétrole 10 %, l'Europe étant importatrice. Asie : Nikkei 25 % ; PIB japonais 20 % ; yuan et VIX 15 % ; courbe japonaise et pétrole 10 % ; dollar 5 % (pas d'inflation : séries arrêtées sur FRED). Monde : 45/30/25, proche du poids des zones dans la capitalisation boursière mondiale. Test de robustesse à poids égaux affiché pour chaque zone.

## 5. Résultats et lecture
*(Insérer capture du tableau de bord réel et les phrases de « Lecture du jour ».)*
Indicateurs les plus lourds aujourd'hui : *(à remplir avec les contributions réelles)*. Signaux : *(à remplir)*.

### Échelle d'alerte sismique (0 à 4)
Le verdict combine le niveau du score et sa vitesse de baisse sur 3 mois (base : ≥65 → 0, 50-65 → 1, 35-50 → 2, <35 → 3 ; chute ≥10 pts → +2, 5-10 pts → +1, hausse ≥5 pts → −1). Justification : une dégradation rapide est un signal en soi, même quand le niveau reste correct. Résultat (Monde, données réelles) : niveau ≥3 pendant 62 % des mois de crise contre 7 % des mois calmes, soit deux fois moins de fausses alertes que la règle « score sous 50 » (17 %), et 5 crises sur 6 précédées d'une alerte.

### Test sur le passé
Six épisodes datés à l'avance (récessions NBER 2001, 2008, 2020 ; baisses du S&P 500 de 2011 et 2022 ; krach chinois de 2015), chaque zone n'étant testée que sur les épisodes qui la concernent. Pour chacun : score 12 mois avant, plus bas pendant l'épisode, signal anticipé (score sous 50 dans les 12 mois précédents). Résultats réels : *(à remplir depuis la section « Test sur le passé » : crises signalées x/5, score moyen en crise vs en période calme, taux de fausses alertes)*. Le même calcul à poids égaux montre si la conclusion dépend de la pondération.

## 6. Limites
Pas d'indice boursier européen ni de données chinoises (hors yuan) à jour sur FRED ; Asie réduite au Japon et à la Chine ; émergents non couverts ; dollar = proxy imparfait des flux de capitaux ; pondération en partie subjective ; descriptif, non prédictif ; pas un conseil en investissement. Test sur le passé : séries révisées et non publiées à l'époque (un test strict utiliserait ALFRED) ; six épisodes seulement ; dollar disponible à partir de 2006 et S&P 500 sur FRED sur environ 10 ans, poids redistribué avant.

## 7. Lien
URL de déploiement : *(à compléter)*
