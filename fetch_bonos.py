"""
Fetching completo de Bonos y Letras desde la API de PPI.

Salida: output/bonos_tir.parquet  (consumido por bonos_report.py)

Categorías:
  hard_dollar  — bonos en USD (cotización USD MEP, sufijo D)
  cer          — ajustados por CER/UVA (pesos, TIR real)
  dolar_link   — ajustados por dólar oficial (pesos, TIR en USD teórico)
  ars_fija     — tasa fija en pesos (bonos + letras)
  ars_badlar   — tasa variable BADLAR (pesos)
  dual         — ajustan por CER y dólar-link simultáneamente

Uso:
    python fetch_bonos.py              # todos
    python fetch_bonos.py --limit 10   # solo 10, para testear rápido
    python fetch_bonos.py --resume     # retomar si se interrumpió
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from py_ppi_arg import PPI

load_dotenv(Path(__file__).parent / ".env")

ROOT       = Path(__file__).parent
OUT_DIR    = ROOT / "output"
CHECKPOINT = OUT_DIR / "_bonos_checkpoint.jsonl"

# Prefijos que cubren el universo de bonos y letras argentinos
SEARCH_TERMS = [
    # Soberanos hard dollar
    "AL", "GD", "AE", "AA",
    # CER / UVA
    "TX", "PR", "DICP", "CUAP",
    # Dólar-link
    "TV", "TDA", "T2V", "T3V",
    # Letras (LECAP, LEDES)
    "LEDE", "LECAP", "S1", "S2", "S3", "S4", "S5", "S6",
    # Provinciales
    "BPY", "PBA", "CO2", "NQ", "SF", "ME", "LP", "EN",
    # Corporativos / cuasi-soberanos
    "YPF", "NDT", "YPFD",
]

# moneda_id 22013 = USD MEP billete (sufijo D) → hard dollar
# moneda_id 10000 = Pesos → CER, dólar-link, ARS fija, BADLAR
TARGET_MONEDAS = {22013, 10000}


# ── clasificación ─────────────────────────────────────────────────────────────

def _classify(td: dict, item: dict, moneda_id: int) -> str:
    if moneda_id == 22013:
        return "hard_dollar"
    ajusta_cer = bool(td.get("ajustaPorCER"))
    dolar_link = bool(td.get("dolarLink"))
    if ajusta_cer and dolar_link:
        return "dual"
    if ajusta_cer:
        return "cer"
    if dolar_link:
        return "dolar_link"
    if item.get("esBonoBadlar"):
        return "ars_badlar"
    return "ars_fija"


def _quote_market(moneda_id: int) -> str:
    if moneda_id == 22013:
        return "USD MEP"
    if moneda_id == 10001:
        return "USD CCL"
    if moneda_id == 10000:
        return "ARS"
    return "OTRO"


# ── checkpoint ────────────────────────────────────────────────────────────────

def _load_checkpoint() -> tuple[set[int], list[dict]]:
    if not CHECKPOINT.exists():
        return set(), []
    done_ids, rows = set(), []
    for line in CHECKPOINT.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            done_ids.add(row["id"])
            rows.append(row)
    return done_ids, rows


def _append_checkpoint(row: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")


# ── fetching principal ────────────────────────────────────────────────────────

def fetch(limit: int | None = None, resume: bool = False) -> pd.DataFrame:
    app = PPI(
        user=os.environ["PPI_USER"],
        password=os.environ["PPI_PASSWORD"],
        remember_device=True,
    )
    print("Auth OK.")

    # ── Recolectar universo ───────────────────────────────────────────────────
    seen_ids: set = set()
    all_items: list[dict] = []

    for term in SEARCH_TERMS:
        try:
            payload = app.search_tickers(short_ticker=term).get("payload") or []
            for item in payload:
                ti_id    = (item.get("tipoItem") or {}).get("id")
                moneda_id = (item.get("moneda")   or {}).get("id")
                item_id  = item.get("id")
                if (
                    ti_id in {100, "100", 110, "110"}
                    and moneda_id in TARGET_MONEDAS
                    and item.get("operable24")
                    and item_id not in seen_ids
                ):
                    seen_ids.add(item_id)
                    all_items.append(item)
        except Exception as e:
            print(f"  ERROR buscando '{term}': {e}")

    print(f"Universo: {len(all_items)} ítems (USD MEP + ARS, operable24)")
    print("Por moneda:", dict(Counter(
        _quote_market((i.get("moneda") or {}).get("id")) for i in all_items
    )))

    # ── Checkpoint ────────────────────────────────────────────────────────────
    done_ids, checkpoint_rows = set(), []
    if resume and CHECKPOINT.exists():
        done_ids, checkpoint_rows = _load_checkpoint()
        print(f"Retomando: {len(done_ids)} ya procesados")

    today     = date.today()
    date_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    date_to   = today.strftime("%Y-%m-%d")
    iterable  = all_items[:limit] if limit else all_items

    rows   = list(checkpoint_rows)
    errors = 0
    t0     = time.time()
    skipped = 0

    for n, item in enumerate(iterable, 1):
        sid       = item["id"]
        ticker    = item.get("ticker")
        descripcion = item.get("descripcion")
        moneda_id = (item.get("moneda") or {}).get("id")

        if sid in done_ids:
            skipped += 1
            continue

        try:
            td_resp = app.get_technical_data_bonds(
                settlement=app.settlements.T2, item_id=str(sid)
            )
            td = td_resp.get("payload") or {}

            flujos = td.get("flujosDeFondosTeoricos") or []
            if not flujos:
                continue

            # La API calcula la TIR directamente en datosDeMercado
            dm  = td.get("datosDeMercado") or {}
            tir = dm.get("tir")
            if tir is None:
                continue

            # Precio actual y volumen
            hist = app.get_historic_data(
                item_id=str(sid),
                settlement=app.settlements.T2,
                date_from=date_from,
                date_to=date_to,
            ).get("payload") or []
            if not hist:
                continue

            last  = hist[-1]
            price = last.get("ultOperado") or last.get("cierreAnterior")
            if not price or price <= 0:
                continue

            last_with_vol = next(
                (h for h in reversed(hist) if (h.get("volumen") or 0) > 0), None
            )
            volumen = last_with_vol["volumen"] if last_with_vol else 0

            categoria = _classify(td, item, moneda_id)

            row = {
                "id":                  sid,
                "ticker":              ticker,
                "descripcion":         descripcion,
                "categoria":           categoria,
                "isin":                td.get("isin"),
                "emisor":              td.get("emisor"),
                "legislacion":         td.get("legislacion"),
                "es_ley_local":        td.get("esLeyLocal"),
                "ajusta_cer":          td.get("ajustaPorCER", False),
                "dolar_link":          td.get("dolarLink", False),
                "es_badlar":           item.get("esBonoBadlar", False),
                "tasa_renta_anual":    td.get("tasaRentaAnual"),
                "texto_intereses":     td.get("intereses"),     # descripción del cupón
                "texto_amortizacion":  td.get("amortizacion"),  # descripción amortización
                "modified_duration":   dm.get("modifiedDuration"),
                "paridad":             dm.get("paridad"),
                "valor_tecnico":       dm.get("valorTecnico"),
                "valor_residual":      dm.get("valorResidual"),
                "intereses_corridos":  dm.get("interesesCorridos"),
                "fechaVencimiento":    td.get("fechaVencimiento"),
                "moneda_cotizacion":   _quote_market(moneda_id),
                "lamina_minima":       td.get("laminaMinima") or item.get("laminaMinima"),
                "price":               price,
                "price_date":          last.get("fechaCotizacion"),
                "volumen":             volumen,
                "tir":                 tir,
                "tir_pct":             tir * 100,
                "flujos":              flujos,
            }
            rows.append(row)
            _append_checkpoint(row)

        except KeyboardInterrupt:
            print(f"\n\nInterrumpido en {n}/{len(iterable)}. Checkpoint: {len(rows)} bonds.")
            print("Retomá con: python fetch_bonos.py --resume")
            sys.exit(0)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR {ticker}: {e}")

        if n % 50 == 0:
            elapsed   = time.time() - t0
            rate      = (n - skipped) / elapsed if elapsed > 0 else 0
            remaining = (len(iterable) - n) / rate if rate > 0 else 0
            print(
                f"  {n:>4}/{len(iterable)}  guardados: {len(rows):>3}  "
                f"errores: {errors}  ~{remaining/60:.0f} min restantes"
            )

    print(f"\nFinal: {len(rows)} bonds con TIR (de {len(iterable) - skipped} procesados, {errors} errores)")
    df = _build_df(rows)

    if CHECKPOINT.exists() and not limit:
        CHECKPOINT.unlink()
        print("Checkpoint eliminado.")

    return df


def _build_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["fechaVencimiento"] = pd.to_datetime(
        df["fechaVencimiento"], errors="coerce", utc=True
    ).dt.tz_convert(None)
    df["price_date"] = pd.to_datetime(
        df["price_date"], errors="coerce", utc=True
    ).dt.tz_convert(None)
    df = df.dropna(subset=["fechaVencimiento", "tir_pct"])
    min_vto = pd.Timestamp.now().normalize() + pd.Timedelta(days=30)
    df = df[df["fechaVencimiento"] >= min_vto]
    df = df.sort_values(["categoria", "fechaVencimiento"]).reset_index(drop=True)

    print(f"\nCategoría:         {df['categoria'].value_counts().to_dict()}")
    print(f"Moneda cotización: {df['moneda_cotizacion'].value_counts().to_dict()}")

    tir_stats = df.groupby("categoria")["tir_pct"].describe()[["min", "mean", "max"]].round(2)
    print(f"\nTIR por categoría:\n{tir_stats.to_string()}")

    return df


def save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df_save = df.copy()
    df_save["flujos"] = df_save["flujos"].apply(json.dumps)
    df_save.to_parquet(path, index=False)
    print(f"\nGuardado: {path.resolve()}  ({len(df_save)} filas, {path.stat().st_size/1024:.0f} KB)")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",  type=int,  default=None, help="Limitar a N bonds")
    parser.add_argument("--resume", action="store_true",      help="Retomar desde checkpoint")
    parser.add_argument("--out",    type=str,  default=None,  help="Ruta de salida del parquet")
    args = parser.parse_args()

    df  = fetch(limit=args.limit, resume=args.resume)
    out = Path(args.out) if args.out else OUT_DIR / "bonos_tir.parquet"
    save(df, out)
