"""
Descarga y parsea el REM (Relevamiento de Expectativas de Mercado) del BCRA.

Genera:
  output/rem_expectativas.parquet  — expectativas mensuales (última encuesta)
  output/rem_historico.parquet     — serie histórica de consensos (desde 2016)

Uso:
    python fetch_rem.py                  # usa el mes más reciente disponible
    python fetch_rem.py --mes may-2026   # slug del Excel en el sitio del BCRA
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT    = Path(__file__).parent
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(exist_ok=True)

BASE    = "https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/informes"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

# Meses en castellano → slug BCRA (ej. "mayo" → "may")
MES_SLUGS = {
    "enero": "ene", "febrero": "feb", "marzo": "mar", "abril": "abr",
    "mayo": "may", "junio": "jun", "julio": "jul", "agosto": "ago",
    "septiembre": "sep", "octubre": "oct", "noviembre": "nov", "diciembre": "dic",
}

# Abreviaturas de mes en orden calendario (índice 0 = enero), usadas para
# construir el slug BCRA (ej. mes 7 → "jul")
_MES_ABBR = ["ene", "feb", "mar", "abr", "may", "jun",
             "jul", "ago", "sep", "oct", "nov", "dic"]


# ── descarga ─────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 60) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    # BCRA devuelve 200 con HTML si el archivo no existe
    if b"<!DOCTYPE" in r.content[:20]:
        raise FileNotFoundError(f"Archivo no encontrado: {url}")
    return r


def find_latest_slug() -> str:
    """Detecta el slug del REM más reciente disponible, buscando hacia atrás
    mes a mes desde el mes actual (hasta 18 meses)."""
    today = date.today()
    year, month = today.year, today.month
    for _ in range(18):
        slug = f"{_MES_ABBR[month - 1]}-{year}"
        url = f"{BASE}/tablas-relevamiento-expectativas-mercado-{slug}.xlsx"
        try:
            _get(url, timeout=15)
            return slug
        except Exception:
            pass
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    raise RuntimeError("No se encontró ningún REM reciente en el BCRA.")


def download_tablas(slug: str) -> bytes:
    url = f"{BASE}/tablas-relevamiento-expectativas-mercado-{slug}.xlsx"
    print(f"  Descargando tablas: {url}")
    return _get(url).content


def download_historico() -> bytes:
    url = f"{BASE}/historico-relevamiento-expectativas-mercado.xlsx"
    print(f"  Descargando histórico: {url}")
    return _get(url, timeout=90).content


# ── parser tablas (expectativas mensuales) ────────────────────────────────────

# Variables de interés y sus prefijos de título en el XLSX
VARS_INTEREST = {
    "Precios minoristas (IPC nivel general": "ipc",
    "Tasa de interés (TAMAR)":               "tamar",
    "Tipo de cambio nominal":                "tc",
}


def _match_var(title: str) -> str | None:
    for prefix, code in VARS_INTEREST.items():
        if title.startswith(prefix):
            return code
    return None


def _parse_horizonte(val) -> tuple[str, pd.Timestamp | None]:
    """Devuelve (tipo, fecha). tipo: 'mensual' | 'anual' | 'prox12m' | 'prox24m' | 'otro'."""
    if pd.isna(val):
        return "otro", None
    s = str(val).strip()
    if s.startswith("próx. 12"):
        return "prox12m", None
    if s.startswith("próx. 24"):
        return "prox24m", None
    if re.fullmatch(r"\d{4}", s):
        return "anual", pd.Timestamp(f"{s}-12-31")
    try:
        ts = pd.to_datetime(val)
        return "mensual", ts.normalize()
    except Exception:
        return "otro", None


def parse_tablas(content: bytes, slug: str) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(content))
    raw = pd.read_excel(xls, sheet_name="Cuadros de resultados", header=None)

    rows = []
    current_var_code = None

    # Encontrar las filas "Período" — arranque de cada bloque de datos
    # La fila anterior (no vacía) es el título de la variable
    for row_idx, row in raw.iterrows():
        cell1 = str(row[1]).strip() if pd.notna(row[1]) else ""

        if cell1 == "Período":
            # Buscar el título de la variable en las filas anteriores
            for back in range(1, 5):
                prev = raw.iloc[row_idx - back, 1]
                if pd.notna(prev) and str(prev).strip():
                    current_var_code = _match_var(str(prev).strip())
                    break
            continue

        if current_var_code is None:
            continue

        if not cell1:
            continue

        tipo, fecha = _parse_horizonte(row[1])

        def _f(col: int) -> float | None:
            v = row[col]
            return float(v) if pd.notna(v) else None

        rows.append({
            "survey_slug":    slug,
            "variable":       current_var_code,
            "horizonte_raw":  cell1,
            "horizonte_tipo": tipo,
            "horizonte":      fecha,
            "referencia":     str(row[2]).strip() if pd.notna(row[2]) else None,
            "mediana":        _f(3),
            "promedio":       _f(4),
            "desvio":         _f(5),
            "maximo":         _f(6),
            "minimo":         _f(7),
            "p90":            _f(8),
            "p75":            _f(9),
            "p25":            _f(10),
            "p10":            _f(11),
            "n":              _f(12),
        })

    return pd.DataFrame(rows)


# ── parser histórico ──────────────────────────────────────────────────────────

# Variables a extraer del histórico (prefijo del título, código interno)
HIST_VARS = {
    "Precios minoristas (IPC nivel general; INDEC): var. % i.a. : Próx. 12 meses": "ipc_12m",
    "Precios minoristas (IPC nivel general; INDEC): var. % i.a. : 2026":            "ipc_2026",
    "Precios minoristas (IPC nivel general; INDEC): var. % i.a. : 2027":            "ipc_2027",
    "Tasa de interés (TAMAR): TNA; %: Próx. 12 meses":                              "tamar_12m",
    "Tasa de interés (TAMAR): TNA; %: 2026":                                        "tamar_2026",
    "Tipo de cambio nominal: $/USD: Próx. 12 meses":                                "tc_12m",
    "Tipo de cambio nominal: $/USD: 2026":                                           "tc_2026",
    "Tipo de cambio nominal: $/USD: 2027":                                           "tc_2027",
}

HIST_STATS = ["Mediana", "Promedio", "Desvío", "Percentil 75", "Percentil 25"]


def parse_historico(content: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(content))
    raw = pd.read_excel(xls, sheet_name="Indicadores Principales", header=None)

    # Columna 1 en fila 1 son las fechas de encuesta
    survey_dates = []
    for val in raw.iloc[1, 1:]:
        if pd.notna(val):
            survey_dates.append(pd.to_datetime(val).normalize())
        else:
            survey_dates.append(None)

    rows = []
    current_var = None

    for row_idx, row in raw.iterrows():
        cell0 = str(row[0]).strip() if pd.notna(row[0]) else ""

        if cell0 in HIST_VARS:
            current_var = HIST_VARS[cell0]
            continue

        if current_var is None or cell0 not in HIST_STATS:
            continue

        stat = cell0.lower().replace("é", "e").replace("ó", "o")
        stat = re.sub(r"percentil (\d+)", r"p\1", stat)

        for col_idx, val in enumerate(row[1:]):
            date = survey_dates[col_idx] if col_idx < len(survey_dates) else None
            if date is None or pd.isna(val):
                continue
            rows.append({
                "variable":    current_var,
                "stat":        stat,
                "survey_date": date,
                "valor":       float(val),
            })

    return pd.DataFrame(rows)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga REM del BCRA")
    parser.add_argument("--mes", default=None,
                        help="Slug del mes (ej: may-2026). Por defecto: detecta el más reciente.")
    args = parser.parse_args()

    if args.mes:
        slug = args.mes
    else:
        print("Buscando el REM más reciente disponible...")
        slug = find_latest_slug()
        print(f"  → Encontrado: {slug}")

    print("\n[1/2] Expectativas mensuales (tablas)...")
    tablas_bytes = download_tablas(slug)
    df_exp = parse_tablas(tablas_bytes, slug)
    out_exp = OUT_DIR / "rem_expectativas.parquet"
    df_exp.to_parquet(out_exp, index=False)
    print(f"  Guardado: {out_exp}  ({len(df_exp)} filas)")

    # Muestra resumen de datos obtenidos
    for var in ["ipc", "tamar", "tc"]:
        subset = df_exp[(df_exp["variable"] == var) & (df_exp["horizonte_tipo"] == "mensual")]
        if not subset.empty:
            print(f"  {var.upper()}: {len(subset)} meses — "
                  f"mediana {subset['mediana'].min():.2f} .. {subset['mediana'].max():.2f}"
                  f"  [{subset['referencia'].iloc[0]}]")

    print("\n[2/2] Histórico de expectativas...")
    hist_bytes = download_historico()
    df_hist = parse_historico(hist_bytes)
    out_hist = OUT_DIR / "rem_historico.parquet"
    df_hist.to_parquet(out_hist, index=False)
    print(f"  Guardado: {out_hist}  ({len(df_hist)} filas, "
          f"{df_hist['survey_date'].nunique()} fechas de encuesta)")

    print("\nOK — ahora corre: python rem_report.py")


if __name__ == "__main__":
    main()
