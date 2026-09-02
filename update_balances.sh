#!/bin/bash
# Reconstruye la base consolidada de balances CNV (scrap-cnv) a partir de lo ya
# scrapeado, y la copia a este repo como balance_data_html.pkl para on_report.py.
#
# No scrapea nada nuevo -- eso lo hacen 2_report_data.py / 3_balance_data.py en
# scrap-cnv. Este script solo hace el merge final (4_db_creation.py) y la copia.
set -euo pipefail

SCRAP_CNV_DIR="/c/Users/marti/OneDrive/Desktop/scrap-cnv"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$REPO_DIR/balance_data_html.pkl"

echo "Reconstruyendo db/cnv_balance_data.pkl en scrap-cnv..."
(cd "$SCRAP_CNV_DIR" && python 4_db_creation.py)

echo "Copiando a $DEST..."
cp "$SCRAP_CNV_DIR/db/cnv_balance_data.pkl" "$DEST"

python - "$DEST" <<'PYEOF'
import sys
import pandas as pd

df = pd.read_pickle(sys.argv[1])
df["close_date"] = pd.to_datetime(df["close_date"], errors="coerce")
print(f"  {len(df):,} filas | {df['company'].nunique()} empresas | balance mas reciente: {df['close_date'].max().date()}")
PYEOF

echo "OK -- ahora corre: python explore/on_report.py"
