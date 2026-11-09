#!/bin/bash
# Double-cliquez sur ce fichier pour récupérer les vraies données FRED et régénérer le baromètre.
cd "$(dirname "$0")" || exit 1
exec > >(tee lancer-log.txt) 2>&1
echo "=== Sismo · baromètre macro-financier : récupération des vraies données ==="
date
PY=$(command -v python3)
if [ -z "$PY" ]; then
  echo "Python 3 est introuvable. Installez-le depuis python.org, puis double-cliquez à nouveau sur ce fichier."
  read -r -p "Appuyez sur Entrée pour fermer." _; exit 1
fi
"$PY" --version
if [ ! -x .venv/bin/python ]; then
  echo "Création d'un environnement Python propre au projet (une seule fois)..."
  "$PY" -m venv .venv || { echo "Échec de la création de l'environnement."; read -r -p "Entrée pour fermer." _; exit 1; }
fi
VPY=.venv/bin/python
if ! "$VPY" -c "import pandas, numpy" 2>/dev/null; then
  echo "Installation des bibliothèques (une seule fois, environ une minute)..."
  "$VPY" -m pip install --upgrade pip
  if ! "$VPY" -m pip install -r requirements.txt; then
    echo "ÉCHEC de l'installation des bibliothèques. Dites-le à Claude."
    read -r -p "Entrée pour fermer." _; exit 1
  fi
fi
echo "Bibliothèques prêtes."

# --- Voie 1 : API officielle de FRED (clé gratuite), la plus fiable
if [ ! -s .fred_api_key ]; then
  echo ""
  echo "Clé d'API FRED : collez-la ici puis Entrée (ou Entrée seule pour passer)."
  read -r -p "> " KEY
  if [ -n "$KEY" ]; then printf "%s" "$KEY" > .fred_api_key; chmod 600 .fred_api_key; echo "Clé enregistrée dans .fred_api_key (jamais publiée)."; fi
fi
if [ -s .fred_api_key ]; then
  echo ""
  echo "Téléchargement par l'API officielle FRED et calcul..."
  "$VPY" -u run.py
  if [ -f dist/barometre.html ]; then open dist/barometre.html; fi
  echo ""
  echo "Terminé. Le dossier site/ est prêt à être déposé sur Netlify. Vous pouvez fermer cette fenêtre."
  exit 0
fi

# --- Voie 2 : sans clé, fichier CSV public (souvent bloqué par FRED)

mkdir -p data/raw
rm -f curl-erreurs.txt
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
IDS=$("$VPY" -c "from barometre import collect, config; print(' '.join(collect.series_ids(config.CATALOG)))")
echo ""
echo "Téléchargement des séries FRED (avec curl) :"
# Essaie deux adresses de FRED, avec un délai court : la page de données en texte, puis le fichier CSV.
get_one() {  # $1 = identifiant ; écrit data/raw/$1.csv ; renvoie 0 si réussi
  local id="$1" tmp="data/raw/$1.tmp"
  if curl -fsSL --http1.1 --connect-timeout 10 --max-time 40 -A "$UA" \
       -H "Accept: text/html,text/plain,*/*" -H "Accept-Language: fr-FR,fr;q=0.9,en;q=0.8" \
       -o "$tmp" "https://fred.stlouisfed.org/data/${id}.txt" 2>>curl-erreurs.txt \
     && grep -q "^DATE" "$tmp"; then
    awk -v id="$id" 'BEGIN{print "observation_date," id} f && NF>=2 {print $1 "," $2} /^DATE/{f=1}' "$tmp" > "data/raw/${id}.csv"
    rm -f "$tmp"; METHOD="texte"; return 0
  fi
  if curl -fsSL --http1.1 --connect-timeout 10 --max-time 40 -A "$UA" \
       -H "Accept: text/csv,text/plain,*/*" -H "Referer: https://fred.stlouisfed.org/series/${id}" \
       -o "$tmp" "https://fred.stlouisfed.org/graph/fredgraph.csv?id=${id}" 2>>curl-erreurs.txt \
     && head -c 300 "$tmp" | grep -q ","; then
    mv "$tmp" "data/raw/${id}.csv"; METHOD="csv"; return 0
  fi
  rm -f "$tmp"; return 1
}
n=0; ok=0; fails=0
for id in $IDS; do
  n=$((n+1)); printf "  %2d. %-20s " "$n" "$id"
  if get_one "$id"; then
    ok=$((ok+1)); fails=0
    echo "ok ($(($(wc -l < "data/raw/${id}.csv") - 1)) observations, $METHOD)"
  else
    fails=$((fails+1)); echo "ÉCHEC"
    if [ "$ok" -eq 0 ] && [ "$fails" -ge 2 ]; then
      echo "FRED ne répond pas aux deux premières séries : arrêt pour ne pas attendre inutilement."; break
    fi
  fi
done
echo "$ok / $n séries téléchargées."
if [ "$ok" -eq 0 ]; then
  echo "Aucune série n'a pu être téléchargée. Détail des erreurs dans curl-erreurs.txt."
  echo "Essayez depuis un autre réseau (partage de connexion du téléphone, par exemple)."
  read -r -p "Entrée pour fermer." _; exit 1
fi
echo ""
echo "Calcul du baromètre..."
"$VPY" -u run.py --files
if [ -f dist/barometre.html ]; then open dist/barometre.html; fi
echo ""
echo "Terminé. Vous pouvez fermer cette fenêtre."
