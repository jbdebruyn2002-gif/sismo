# Sismo · baromètre macro-financier

*Comme un sismographe, Sismo cherche à détecter les secousses des marchés avant la crise.*

Score de 0 à 100 des conditions macro-financières, au choix pour les **États-Unis**, l'**Europe**, l'**Asie** (Japon, Corée, Inde, Chine),
les **Émergents** ou le **Monde** (moyenne des quatre). 26 indicateurs issus de FRED (données ouvertes, sans clé d'API).
Dans la page, le sélecteur « Zone » change le score, les cartes, les contributions et le test sur le passé.
En haut de page, le bloc **En bref** résume la zone en phrases simples (ce qui aide, ce qui inquiète, à surveiller) ; le bouton « Vue simple / Vue complète » masque ou affiche le détail.
Liens directs : `#monde`, `#etats-unis`, `#europe`, `#asie`, `#emergents` à la fin de l'adresse.

## Mise à jour automatique (recommandé)
FRED bloque son fichier CSV quand il est demandé par un programme. La voie fiable est l'**API officielle FRED** :
1. Clé gratuite : créer un compte sur fredaccount.stlouisfed.org, puis « API Keys » → « Request API Key ».
2. Sur son ordinateur : `export FRED_API_KEY=...` ou fichier `.fred_api_key` à la racine (jamais publié), puis `python run.py`.
3. Automatique chaque jour : dépôt GitHub contenant ce projet + secret `FRED_API_KEY`
   (Settings → Secrets and variables → Actions). Le workflow `.github/workflows/refresh.yml` recalcule
   tous les matins et enregistre le dossier `site/`. Netlify, relié au dépôt (dossier publié : `site`,
   aucune commande de build), republie la page automatiquement.

## Récupérer les vraies données (sans clé)
FRED bloque les téléchargements automatiques (curl, Python) depuis certains ordinateurs : la connexion reste sans réponse.
Deux solutions :
1. `lancer-barometre.command` (double-clic sur Mac) : télécharge avec curl puis calcule. Fonctionne si FRED répond.
2. Sinon, télécharger les séries depuis un navigateur (fichier `fred-donnees-barometre.json`, un objet {identifiant: texte CSV}),
   puis : `python run.py --json chemin/vers/fred-donnees-barometre.json`.

## Utiliser
    pip install -r requirements.txt
    python run.py            # données réelles -> web/data.js et dist/barometre.html
    python run.py --offline  # réutilise data/raw/ sans réseau
    python run.py --demo     # DONNÉES SIMULÉES (bandeau d'avertissement affiché)
    python -m pytest -q tests

Ouvrir `dist/barometre.html` : fichier unique, autonome (c'est le livrable HTML).

## Installer Sismo comme une application
`python run.py` génère le dossier `site/` : page + manifeste + icônes + fonctionnement hors connexion.
1. Glisser le dossier `site/` sur app.netlify.com/drop : Netlify donne une adresse publique en https.
2. Mac : ouvrir l'adresse dans Safari, menu Fichier → Ajouter au Dock (ou Chrome : icône « Installer » dans la barre d'adresse).
3. iPhone / Android : ouvrir l'adresse, Partager → Sur l'écran d'accueil (ou « Installer l'application »).

## Mettre en ligne (URL)
- **Netlify** : glisser le dossier `site/` (après `python run.py`) sur app.netlify.com/drop, ou relier le dépôt (`netlify.toml` fourni).
- **Vercel** : importer le dépôt (`vercel.json` fourni).
- **Mise à jour automatique** : `.github/workflows/refresh.yml` relance la collecte chaque jour ouvré et commit les données ; Netlify/Vercel redéploient à chaque commit.

## Organisation
- `barometre/config.py` : catalogue des indicateurs, zones et poids par zone (`ZONES`, `GLOBAL_MIX`), méthodes de normalisation, crises du test sur le passé, justifications. **Tout se règle ici.**
- `barometre/collect.py` : téléchargement FRED, copie locale dans `data/raw/`.
- `barometre/scoring.py` : mensualisation (délai de publication), normalisation sans regard dans le futur, score pondéré, contributions.
- `barometre/resume.py` : résumé « En bref » en phrases simples (règles fixes, à partir des chiffres ; phrases de chaque indicateur dans `config.py`, clés `plain_good` et `plain_bad`).
- `barometre/alerte.py` : échelle d'alerte 0-4 (niveau du score + vitesse de baisse sur 3 mois).
- `barometre/notify.py` : avis par e-mail (ticket GitHub) quand le niveau d'alerte d'une zone change.
- `barometre/robustesse.py` : solidité des seuils (9 variantes) et comparaison avec des règles naïves (VIX > 25, courbe inversée, score < 50).
- `barometre/backtest.py` : test sur le passé (score avant et pendant les crises listées dans `config.EPISODES`, fausses alertes).
- `web/index.html` : tableau de bord (SVG sans bibliothèque).

## Points à vérifier au premier lancement réel
Les 18 séries FRED ont été téléchargées et vérifiées le 2 novembre 2026.
- États-Unis : GDPC1, CPIAUCSL, SP500, T10Y2Y, NFCI.
- Monde : VIXCLS, DCOILBRENTEU, DTWEXBGS.
- Zone euro : CLVMNACSCAB1GQEA (PIB), CP0000EZCCM086NEST (IPCH), IRLTLT01ITM156N − IRLTLT01DEM156N (écart Italie-Allemagne), IRLTLT01DEM156N − ECBDFR (courbe : Bund 10 ans moins taux de dépôt BCE).
- Asie : JPNRGDPEXP (PIB Japon), NIKKEI225, IRLTLT01JPM156N − IR3TIB01JPM156N (courbe Japon), DEXCHUS (yuan).

Le premier `python run.py` affiche le statut de chaque série ; un statut « indisponible » viendra alors du réseau, pas de l'identifiant. Règle de fraîcheur (`MAX_AGE_MONTHS` dans `config.py`) : une série dont la dernière donnée est trop ancienne est exclue et son poids redistribué. C'est pourquoi l'inflation japonaise (arrêtée en juin 2021) et le taux à 3 mois de la zone euro (arrêté en janvier 2026) ont été retirés. Les séries de l'OCDE (taux) sont des moyennes mensuelles publiées avec environ un mois de retard. La série S&P 500 de FRED ne couvre qu'environ 10 ans.
